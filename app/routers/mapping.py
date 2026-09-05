from __future__ import annotations

import json
import os
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from psycopg2.extras import Json, RealDictCursor

from app.services.geo import validate_bbox, validate_coordinate
from app.services.geo_assistant import identify_intent, response
from app.services.notifications import create_notification
from app.services.routing import RoutingUnavailable, get_routing_provider
from core.policy import is_manager_role
from core.security import decode_token
from database import get_db_connection

router=APIRouter(prefix="/api/v1/geo",tags=["mapping"]);security=HTTPBearer()

def current_user(credentials:HTTPAuthorizationCredentials=Depends(security)):
    user=decode_token(credentials.credentials)
    if not user: raise HTTPException(401,"Token invalide ou expiré")
    return user

def manager(user=Depends(current_user)):
    if not is_manager_role(user.get("role","")): raise HTTPException(403,"Réservé aux gestionnaires")
    return user

class TourCreate(BaseModel):
    collector_id:int=Field(gt=0);occurrence_ids:list[int]=Field(min_length=1,max_length=50)
    planned_date:date;zone_id:Optional[int]=Field(default=None,gt=0);reason:Optional[str]=Field(default=None,max_length=1000)

class PositionCreate(BaseModel):
    lat:float=Field(ge=-90,le=90);lon:float=Field(ge=-180,le=180);accuracy_m:float=Field(ge=0,le=10000)

class IncidentCreate(BaseModel):
    category:str=Field(min_length=2,max_length=64);description:str=Field(min_length=2,max_length=2000);stop_id:Optional[int]=Field(default=None,gt=0)

class ZoneCreate(BaseModel):
    name:str=Field(min_length=2,max_length=120);zone_type:str=Field(default="operational",max_length=40)
    arrondissement:Optional[str]=Field(default=None,max_length=120);geometry:dict;reason:str=Field(min_length=2,max_length=1000)

class AssistantRequest(BaseModel):
    query:str=Field(default="",max_length=500);intent:Optional[str]=Field(default=None,max_length=64)
    resource_id:Optional[int]=Field(default=None,gt=0);zone_id:Optional[int]=Field(default=None,gt=0)
    lat:Optional[float]=Field(default=None,ge=-90,le=90);lon:Optional[float]=Field(default=None,ge=-180,le=180)

def _polygon(value:dict)->str:
    if value.get("type") != "Polygon":raise HTTPException(422,"Polygone GeoJSON obligatoire")
    raw=json.dumps(value,separators=(",",":"))
    if len(raw)>200000:raise HTTPException(413,"Zone trop complexe")
    return raw

def _bbox(south,west,north,east):
    try:return validate_bbox(south,west,north,east)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc

@router.get("/map-data")
def map_data(south:float=3.70,west:float=9.30,north:float=4.35,east:float=10.05,limit:int=Query(200,ge=1,le=500),user=Depends(current_user)):
    bounds=_bbox(south,west,north,east);envelope=bounds.as_envelope_params();conn=get_db_connection();cur=conn.cursor(cursor_factory=RealDictCursor);role=user["role"]
    if role=="citoyen":
        cur.execute("""SELECT id,'report' kind,status,severity label,ST_Y(geometry) lat,ST_X(geometry) lon FROM reports WHERE user_id=%s AND geometry&&ST_MakeEnvelope(%s,%s,%s,%s,4326) ORDER BY updated_at DESC LIMIT %s""",(user["user_id"],*envelope,limit));resources=cur.fetchall()
        cur.execute("""SELECT o.id,'collection' kind,o.status,'collecte' label,ST_Y(s.address_geometry) lat,ST_X(s.address_geometry) lon FROM collection_occurrences o JOIN domestic_subscriptions s ON s.id=o.subscription_id WHERE s.user_id=%s AND s.address_geometry&&ST_MakeEnvelope(%s,%s,%s,%s,4326) ORDER BY o.scheduled_for DESC LIMIT %s""",(user["user_id"],*envelope,limit));resources+=cur.fetchall()
    elif role=="agent":
        cur.execute("""SELECT id,'report' kind,status,severity label,ST_Y(geometry) lat,ST_X(geometry) lon FROM reports WHERE agent_id=%s AND status IN ('assigne','en_route','en_cours','verification_requise') AND geometry&&ST_MakeEnvelope(%s,%s,%s,%s,4326) ORDER BY updated_at DESC LIMIT %s""",(user["user_id"],*envelope,limit));resources=cur.fetchall()
    elif role=="ramasseur":
        cur.execute("""SELECT o.id,'collection' kind,o.status,'collecte' label,CASE WHEN o.status IN ('acceptee','en_route','arrivee','en_attente_confirmation') THEN ST_Y(s.address_geometry) END lat,CASE WHEN o.status IN ('acceptee','en_route','arrivee','en_attente_confirmation') THEN ST_X(s.address_geometry) END lon FROM collection_occurrences o JOIN domestic_subscriptions s ON s.id=o.subscription_id WHERE o.collector_id=%s AND o.status IN ('proposee','acceptee','en_route','arrivee','en_attente_confirmation') ORDER BY o.scheduled_for LIMIT %s""",(user["user_id"],limit));resources=cur.fetchall()
    elif is_manager_role(role):
        cur.execute("""SELECT id,'report' kind,status,severity label,ST_Y(geometry) lat,ST_X(geometry) lon FROM reports WHERE geometry&&ST_MakeEnvelope(%s,%s,%s,%s,4326) ORDER BY updated_at DESC LIMIT %s""",(*envelope,limit));resources=cur.fetchall()
    else: cur.close();conn.close();raise HTTPException(403,"Rôle non autorisé")
    cur.execute("""SELECT id,nom,zone_type,ST_AsGeoJSON(geometry)::json geometry FROM zones WHERE active=TRUE AND geometry IS NOT NULL AND geometry&&ST_MakeEnvelope(%s,%s,%s,%s,4326) ORDER BY id LIMIT 100""",envelope);zones=cur.fetchall()
    cur.close();conn.close();return {"resources":resources,"zones":zones,"bounds":{"south":south,"west":west,"north":north,"east":east}}

@router.get("/public-drop-points")
def public_drop_points(lat:float,lon:float,radius_m:int=Query(5000,ge=100,le=20000),limit:int=Query(20,ge=1,le=50),user=Depends(current_user)):
    try:validate_coordinate(lat,lon)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    conn=get_db_connection();cur=conn.cursor(cursor_factory=RealDictCursor);cur.execute("""SELECT id,nom,type_activite,arrondissement,ST_Y(geometry) lat,ST_X(geometry) lon,ST_Distance(geometry::geography,ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography) distance_m FROM points_collecte WHERE geometry IS NOT NULL AND ST_DWithin(geometry::geography,ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography,%s) ORDER BY distance_m LIMIT %s""",(lon,lat,lon,lat,radius_m,limit));rows=cur.fetchall();cur.close();conn.close();return rows

@router.post("/zones")
def create_zone(payload:ZoneCreate,user=Depends(manager)):
    encoded=_polygon(payload.geometry);conn=get_db_connection();cur=conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""INSERT INTO zones(nom,zone_type,arrondissement,geometry) SELECT %s,%s,%s,ST_SetSRID(ST_GeomFromGeoJSON(%s),4326) WHERE ST_IsValid(ST_SetSRID(ST_GeomFromGeoJSON(%s),4326)) RETURNING id,nom""",(payload.name,payload.zone_type,payload.arrondissement,encoded,encoded));row=cur.fetchone()
        if not row:raise HTTPException(422,"Géométrie de zone invalide")
        cur.execute("INSERT INTO audit_logs(actor_id,actor_role,action,resource_type,resource_id,new_value,reason) VALUES (%s,%s,'zone_created','zone',%s,%s,%s)",(user["user_id"],user["role"],row["id"],Json({"name":payload.name,"type":payload.zone_type}),payload.reason));conn.commit();return row
    except Exception:conn.rollback();raise
    finally:cur.close();conn.close()

@router.get("/tours")
def list_tours(planned_date:Optional[date]=None,limit:int=Query(100,ge=1,le=200),user=Depends(current_user)):
    conn=get_db_connection();cur=conn.cursor(cursor_factory=RealDictCursor);cur.execute("""SELECT id,agent_id,collector_id,planned_date,status,tour_type,version,routing_status,distance_m,duration_s FROM tours WHERE (%s::date IS NULL OR planned_date=%s) AND (%s OR agent_id=%s OR collector_id=%s) ORDER BY planned_date DESC,id DESC LIMIT %s""",(planned_date,planned_date,is_manager_role(user["role"]),user["user_id"],user["user_id"],limit));rows=cur.fetchall();cur.close();conn.close();return rows

@router.post("/tours")
def create_collection_tour(payload:TourCreate,user=Depends(manager)):
    ids=list(dict.fromkeys(payload.occurrence_ids))
    if len(ids)!=len(payload.occurrence_ids): raise HTTPException(422,"Occurrences dupliquées")
    conn=get_db_connection();cur=conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT id,daily_capacity,available_weekdays,service_area FROM users WHERE id=%s AND role='ramasseur' AND active=TRUE",(payload.collector_id,));collector=cur.fetchone()
        if not collector: raise HTTPException(404,"Ramasseur actif introuvable")
        if payload.planned_date.weekday() not in (collector["available_weekdays"] or []): raise HTTPException(409,"Ramasseur indisponible")
        if len(ids)>collector["daily_capacity"]: raise HTTPException(409,"Capacité dépassée")
        cur.execute("""SELECT o.id,o.status,o.collector_id,s.service_area,ST_Y(s.address_geometry) lat,ST_X(s.address_geometry) lon FROM collection_occurrences o JOIN domestic_subscriptions s ON s.id=o.subscription_id WHERE o.id=ANY(%s) FOR UPDATE OF o""",(ids,));rows=cur.fetchall()
        if len(rows)!=len(ids): raise HTTPException(404,"Occurrence introuvable")
        if any(r["collector_id"]!=payload.collector_id or r["status"] not in {"acceptee","en_route","arrivee"} for r in rows): raise HTTPException(409,"Occurrence non autorisée pour cette tournée")
        if collector["service_area"] and any(r["service_area"] and r["service_area"]!=collector["service_area"] for r in rows): raise HTTPException(409,"Occurrence hors zone")
        cur.execute("""SELECT 1 FROM tour_stops s JOIN tours t ON t.id=s.tour_id WHERE s.occurrence_id=ANY(%s) AND t.status IN ('planifiee','en_cours') LIMIT 1""",(ids,))
        if cur.fetchone(): raise HTTPException(409,"Occurrence déjà présente dans une tournée active")
        cur.execute("INSERT INTO tours(collector_id,planned_date,status,tour_type,zone_id,created_by,modification_reason) VALUES (%s,%s,'planifiee','collection',%s,%s,%s) RETURNING id",(payload.collector_id,payload.planned_date,payload.zone_id,user["user_id"],payload.reason));tour_id=cur.fetchone()["id"]
        ordered=sorted(rows,key=lambda row:ids.index(row["id"]))
        for order,row in enumerate(ordered,1):cur.execute("INSERT INTO tour_stops(tour_id,occurrence_id,stop_order,geometry) VALUES (%s,%s,%s,ST_SetSRID(ST_MakePoint(%s,%s),4326))",(tour_id,row["id"],order,row["lon"],row["lat"]))
        cur.execute("INSERT INTO audit_logs(actor_id,actor_role,action,resource_type,resource_id,new_value,reason) VALUES (%s,%s,'tour_created','tour',%s,%s,%s)",(user["user_id"],user["role"],tour_id,Json({"collector_id":payload.collector_id,"stop_count":len(rows)}),payload.reason))
        create_notification(conn,payload.collector_id,"tour_created","Nouvelle tournée",f"La tournée #{tour_id} vous a été attribuée.",f"/ramasseur#tour-{tour_id}","notification.tour_created",{"tour_id":tour_id},resource_type="tour",resource_id=tour_id)
        conn.commit();return {"id":tour_id,"status":"planifiee","stop_count":len(rows)}
    except Exception:conn.rollback();raise
    finally:cur.close();conn.close()

def _tour_access(cur,tour_id,user,lock=False):
    cur.execute(f"SELECT * FROM tours WHERE id=%s AND (%s OR agent_id=%s OR collector_id=%s){' FOR UPDATE' if lock else ''}",(tour_id,is_manager_role(user["role"]),user["user_id"],user["user_id"]));tour=cur.fetchone()
    if not tour: raise HTTPException(404,"Tournée introuvable")
    return tour

@router.get("/tours/{tour_id}")
def tour_detail(tour_id:int,user=Depends(current_user)):
    conn=get_db_connection();cur=conn.cursor(cursor_factory=RealDictCursor);tour=dict(_tour_access(cur,tour_id,user));tour.pop("route_geometry",None);cur.execute("SELECT ST_AsGeoJSON(route_geometry) geometry FROM tours WHERE id=%s",(tour_id,));encoded=cur.fetchone()["geometry"];cur.execute("SELECT id,report_id,occurrence_id,stop_order,status,ST_Y(geometry) lat,ST_X(geometry) lon FROM tour_stops WHERE tour_id=%s ORDER BY stop_order",(tour_id,));stops=cur.fetchall();result={**tour,"route_geometry":json.loads(encoded) if encoded else None,"stops":stops};cur.close();conn.close();return result

@router.post("/tours/{tour_id}/route")
def calculate_route(tour_id:int,user=Depends(current_user)):
    conn=get_db_connection();cur=conn.cursor(cursor_factory=RealDictCursor)
    try:
        tour=_tour_access(cur,tour_id,user,True)
        if not is_manager_role(user["role"]) and tour.get("status") not in {"planifiee","en_cours"}: raise HTTPException(409,"Tournée inactive")
        cur.execute("SELECT id,status,ST_Y(geometry) lat,ST_X(geometry) lon FROM tour_stops WHERE tour_id=%s ORDER BY stop_order",(tour_id,));stops=cur.fetchall();active=[s for s in stops if s["status"] not in {"completed","cancelled"}]
        if len(active)<2: raise HTTPException(409,"Pas assez d’arrêts à calculer")
        version=tour["version"]+1 if tour["routing_status"] in {"ready","failed","unavailable"} else tour["version"]
        provider=get_routing_provider()
        try: route=provider.route([(s["lat"],s["lon"]) for s in active]);status="ready";error=None
        except RoutingUnavailable: route=None;status="unavailable";error="provider_unavailable"
        if route:
            cur.execute("UPDATE tours SET version=%s,routing_provider=%s,routing_status='ready',route_geometry=ST_SetSRID(ST_GeomFromGeoJSON(%s),4326),distance_m=%s,duration_s=%s,calculated_at=NOW(),updated_at=NOW() WHERE id=%s",(version,route.provider,json.dumps(route.geometry),route.distance_m,route.duration_s,tour_id))
            cur.execute("INSERT INTO route_versions(tour_id,version,provider,status,geometry,distance_m,duration_s,created_by) VALUES (%s,%s,%s,'ready',ST_SetSRID(ST_GeomFromGeoJSON(%s),4326),%s,%s,%s)",(tour_id,version,route.provider,json.dumps(route.geometry),route.distance_m,route.duration_s,user["user_id"]))
        else:
            cur.execute("UPDATE tours SET version=%s,routing_provider=%s,routing_status='unavailable',route_geometry=NULL,distance_m=NULL,duration_s=NULL,calculated_at=NOW(),updated_at=NOW() WHERE id=%s",(version,provider.name,tour_id));cur.execute("INSERT INTO route_versions(tour_id,version,provider,status,error_code,created_by) VALUES (%s,%s,%s,'unavailable',%s,%s)",(tour_id,version,provider.name,error,user["user_id"]))
        cur.execute("INSERT INTO audit_logs(actor_id,actor_role,action,resource_type,resource_id,new_value) VALUES (%s,%s,'route_calculated','tour',%s,%s)",(user["user_id"],user["role"],tour_id,Json({"version":version,"status":status,"provider":provider.name})))
        conn.commit();return {"tour_id":tour_id,"version":version,"status":status,"geometry":route.geometry if route else None,"distance_m":route.distance_m if route else None,"duration_s":route.duration_s if route else None}
    except Exception:conn.rollback();raise
    finally:cur.close();conn.close()

@router.post("/tours/{tour_id}/start")
def start_tour(tour_id:int,user=Depends(current_user)):
    conn=get_db_connection();cur=conn.cursor(cursor_factory=RealDictCursor)
    try:
        tour=_tour_access(cur,tour_id,user,True)
        if tour["status"]!="planifiee":raise HTTPException(409,"Tournée non démarrable")
        cur.execute("UPDATE tours SET status='en_cours',started_at=NOW(),updated_at=NOW() WHERE id=%s",(tour_id,));cur.execute("UPDATE tour_stops SET status='current' WHERE tour_id=%s AND stop_order=(SELECT MIN(stop_order) FROM tour_stops WHERE tour_id=%s AND status='pending')",(tour_id,tour_id));cur.execute("INSERT INTO audit_logs(actor_id,actor_role,action,resource_type,resource_id) VALUES (%s,%s,'tour_started','tour',%s)",(user["user_id"],user["role"],tour_id));conn.commit();return {"id":tour_id,"status":"en_cours"}
    except Exception:conn.rollback();raise
    finally:cur.close();conn.close()

@router.post("/tours/{tour_id}/sync-progress")
def sync_tour_progress(tour_id:int,user=Depends(current_user)):
    conn=get_db_connection();cur=conn.cursor(cursor_factory=RealDictCursor)
    try:
        _tour_access(cur,tour_id,user,True)
        cur.execute("""UPDATE tour_stops ts SET status=CASE WHEN o.status='manquee' THEN 'missed' ELSE 'completed' END,completed_at=COALESCE(ts.completed_at,NOW()) FROM collection_occurrences o WHERE ts.tour_id=%s AND ts.occurrence_id=o.id AND ts.status IN ('pending','current') AND o.status IN ('confirmee','manquee')""",(tour_id,));updated=cur.rowcount
        cur.execute("""UPDATE tour_stops SET status='current' WHERE tour_id=%s AND status='pending' AND stop_order=(SELECT MIN(stop_order) FROM tour_stops WHERE tour_id=%s AND status='pending')""",(tour_id,tour_id))
        cur.execute("SELECT COUNT(*) FROM tour_stops WHERE tour_id=%s AND status IN ('pending','current')",(tour_id,));remaining=cur.fetchone()["count"]
        if remaining==0:cur.execute("UPDATE tours SET status='terminee',completed_at=NOW(),updated_at=NOW() WHERE id=%s",(tour_id,))
        if updated:cur.execute("INSERT INTO audit_logs(actor_id,actor_role,action,resource_type,resource_id,new_value) VALUES (%s,%s,'tour_progress_synced','tour',%s,%s)",(user["user_id"],user["role"],tour_id,Json({"updated":updated,"remaining":remaining})))
        conn.commit();return {"id":tour_id,"updated":updated,"remaining":remaining,"status":"terminee" if remaining==0 else "en_cours"}
    except Exception:conn.rollback();raise
    finally:cur.close();conn.close()

@router.post("/tours/{tour_id}/position",status_code=202)
def update_position(tour_id:int,payload:PositionCreate,user=Depends(current_user)):
    if user["role"] not in {"agent","ramasseur"}:raise HTTPException(403,"Position opérationnelle interdite")
    try:validate_coordinate(payload.lat,payload.lon, douala_only=True)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    maximum=float(os.getenv("POSITION_MAX_ACCURACY_METERS","250"))
    if payload.accuracy_m>maximum:raise HTTPException(422,"Précision insuffisante")
    interval=int(os.getenv("POSITION_MIN_INTERVAL_SECONDS","10"));retention=int(os.getenv("POSITION_RETENTION_MINUTES","120"));conn=get_db_connection();cur=conn.cursor(cursor_factory=RealDictCursor)
    try:
        tour=_tour_access(cur,tour_id,user)
        if tour["status"]!="en_cours":raise HTTPException(409,"Tournée inactive")
        cur.execute("SELECT recorded_at FROM operational_positions WHERE actor_id=%s ORDER BY recorded_at DESC LIMIT 1",(user["user_id"],));last=cur.fetchone()
        if last:
            cur.execute("SELECT EXTRACT(EPOCH FROM NOW()-%s) >= %s AS allowed",(last["recorded_at"],interval))
            if not cur.fetchone()["allowed"]:raise HTTPException(429,"Position trop fréquente")
        cur.execute("INSERT INTO operational_positions(tour_id,actor_id,actor_role,geometry,accuracy_m,expires_at) VALUES (%s,%s,%s,ST_SetSRID(ST_MakePoint(%s,%s),4326),%s,NOW()+(%s||' minutes')::interval) RETURNING id,recorded_at,expires_at",(tour_id,user["user_id"],user["role"],payload.lon,payload.lat,payload.accuracy_m,retention));row=cur.fetchone();conn.commit();return row
    except Exception:conn.rollback();raise
    finally:cur.close();conn.close()

@router.post("/tours/{tour_id}/incidents")
def create_incident(tour_id:int,payload:IncidentCreate,user=Depends(current_user)):
    conn=get_db_connection();cur=conn.cursor(cursor_factory=RealDictCursor)
    try:
        _tour_access(cur,tour_id,user)
        if payload.stop_id:
            cur.execute("SELECT 1 FROM tour_stops WHERE id=%s AND tour_id=%s",(payload.stop_id,tour_id))
            if not cur.fetchone():raise HTTPException(404,"Arrêt introuvable")
        cur.execute("INSERT INTO tour_incidents(tour_id,stop_id,author_id,category,description) VALUES (%s,%s,%s,%s,%s) RETURNING id,status,created_at",(tour_id,payload.stop_id,user["user_id"],payload.category,payload.description));row=cur.fetchone();cur.execute("INSERT INTO audit_logs(actor_id,actor_role,action,resource_type,resource_id,new_value) VALUES (%s,%s,'tour_incident','tour',%s,%s)",(user["user_id"],user["role"],tour_id,Json({"incident_id":row["id"],"category":payload.category})));conn.commit();return row
    except Exception:conn.rollback();raise
    finally:cur.close();conn.close()

@router.get("/collections/{occurrence_id}/progress")
def citizen_collection_progress(occurrence_id:int,user=Depends(current_user)):
    if user["role"]!="citoyen":raise HTTPException(403,"Réservé aux citoyens")
    stale=int(os.getenv("POSITION_STALE_SECONDS","120"));conn=get_db_connection();cur=conn.cursor(cursor_factory=RealDictCursor);cur.execute("""SELECT o.status,t.id tour_id,ROUND(ST_Y(p.geometry)::numeric,3) lat,ROUND(ST_X(p.geometry)::numeric,3) lon,p.recorded_at,(p.recorded_at>=NOW()-(%s||' seconds')::interval) fresh FROM collection_occurrences o JOIN domestic_subscriptions s ON s.id=o.subscription_id LEFT JOIN tour_stops ts ON ts.occurrence_id=o.id LEFT JOIN tours t ON t.id=ts.tour_id LEFT JOIN LATERAL(SELECT geometry,recorded_at FROM operational_positions WHERE tour_id=t.id AND expires_at>NOW() ORDER BY recorded_at DESC LIMIT 1)p ON TRUE WHERE o.id=%s AND s.user_id=%s""",(stale,occurrence_id,user["user_id"]));row=cur.fetchone();cur.close();conn.close()
    if not row:raise HTTPException(404,"Collecte introuvable")
    if row["status"] not in {"en_route","arrivee"}:row["lat"]=row["lon"]=row["recorded_at"]=None;row["fresh"]=False
    return row

@router.post("/assistant")
def geographic_assistant(payload:AssistantRequest,user=Depends(current_user)):
    if os.getenv("CHATBOT_ENABLED", "true").lower() != "true":
        raise HTTPException(503, "Assistant temporairement indisponible")
    try:intent=identify_intent(payload.query,user["role"],payload.intent)
    except LookupError as exc:return response(user.get("language","fr"),str(exc),"Please clarify your geographic request.",needs_clarification=True)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    except PermissionError as exc:raise HTTPException(403,str(exc)) from exc
    language=user.get("language","fr");conn=get_db_connection();cur=conn.cursor(cursor_factory=RealDictCursor)
    try:
        if intent=="report_status":
            if payload.resource_id:cur.execute("SELECT id,status FROM reports WHERE id=%s AND user_id=%s",(payload.resource_id,user["user_id"]))
            else:cur.execute("SELECT id,status FROM reports WHERE user_id=%s ORDER BY updated_at DESC LIMIT 2",(user["user_id"],))
            rows=cur.fetchall()
            if not rows:return response(language,"Aucun signalement autorisé trouvé.","No authorized report was found.")
            if len(rows)>1:return response(language,"Plusieurs signalements correspondent. Précisez leur identifiant.","Several reports match. Specify an ID.",needs_clarification=True)
            row=rows[0];return response(language,f"Le signalement #{row['id']} est {row['status']}.",f"Report #{row['id']} is {row['status']}.",facts={"report_id":row["id"],"status":row["status"]},link=f"/citoyen#signalement-{row['id']}")
        if intent in {"next_collection","collection_state"}:
            owner="s.user_id=%s" if user["role"]=="citoyen" else "o.collector_id=%s"
            cur.execute(f"SELECT o.id,o.status,o.scheduled_for FROM collection_occurrences o JOIN domestic_subscriptions s ON s.id=o.subscription_id WHERE {owner} AND o.status NOT IN ('annulee','confirmee','refusee') ORDER BY o.scheduled_for LIMIT 1",(user["user_id"],));row=cur.fetchone()
            if not row:return response(language,"Aucune prochaine collecte disponible.","No upcoming collection is available.")
            return response(language,f"La prochaine collecte #{row['id']} est {row['status']}.",f"Next collection #{row['id']} is {row['status']}.",facts={"collection_id":row["id"],"status":row["status"],"scheduled_for":row["scheduled_for"]},link=f"/{user['role']}#collecte-{row['id']}")
        if intent=="nearby_drop_points":
            if payload.lat is None or payload.lon is None:return response(language,"Indiquez une position pour rechercher les points publics.","Provide a position to find public drop points.",needs_clarification=True)
            validate_coordinate(payload.lat,payload.lon);cur.execute("SELECT id,nom,ROUND(ST_Distance(geometry::geography,ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography)) distance_m FROM points_collecte WHERE geometry IS NOT NULL AND ST_DWithin(geometry::geography,ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography,10000) ORDER BY distance_m LIMIT 5",(payload.lon,payload.lat,payload.lon,payload.lat));rows=cur.fetchall();return response(language,f"{len(rows)} point(s) public(s) proche(s) trouvé(s).",f"{len(rows)} nearby public drop point(s) found.",facts={"points":rows})
        if intent in {"assigned_interventions","interventions_in_zone","nearest_intervention"}:
            params=[user["user_id"]];distance=""
            if intent=="nearest_intervention":
                if payload.lat is None or payload.lon is None:return response(language,"Indiquez votre position autorisée.","Provide your authorized position.",needs_clarification=True)
                validate_coordinate(payload.lat,payload.lon);distance=",ROUND(ST_Distance(geometry::geography,ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography)) distance_m";params=[payload.lon,payload.lat,user["user_id"]]
            cur.execute(f"SELECT id,status,severity{distance} FROM reports WHERE agent_id=%s AND status IN ('assigne','en_route','en_cours','verification_requise') ORDER BY {'distance_m,' if distance else ''} updated_at DESC LIMIT 20",params);rows=cur.fetchall();return response(language,f"{len(rows)} intervention(s) autorisée(s).",f"{len(rows)} authorized intervention(s).",facts={"interventions":rows})
        if intent in {"remaining_stops","show_route"}:
            cur.execute("SELECT id,routing_status,distance_m,duration_s FROM tours WHERE collector_id=%s AND status IN ('planifiee','en_cours') ORDER BY planned_date,id LIMIT 1",(user["user_id"],));tour=cur.fetchone()
            if not tour:return response(language,"Aucune tournée active.","No active tour.")
            cur.execute("SELECT COUNT(*) remaining FROM tour_stops WHERE tour_id=%s AND status IN ('pending','current')",(tour["id"],));remaining=cur.fetchone()["remaining"]
            facts={"tour_id":tour["id"],"remaining":remaining,"routing_status":tour["routing_status"],"distance_m":tour["distance_m"],"duration_s":tour["duration_s"]};return response(language,f"La tournée #{tour['id']} contient {remaining} arrêt(s) restant(s).",f"Tour #{tour['id']} has {remaining} remaining stop(s).",facts=facts,link=f"/ramasseur#tour-{tour['id']}")
        if intent=="report_incident":
            cur.execute("SELECT id FROM tours WHERE collector_id=%s AND status='en_cours' ORDER BY started_at DESC LIMIT 1",(user["user_id"],));tour=cur.fetchone()
            if not tour:return response(language,"Aucune tournée active pour signaler un incident.","No active tour for reporting an incident.")
            return response(language,"Ouvrez le formulaire d’incident de votre tournée active.","Open the incident form for your active tour.",facts={"tour_id":tour["id"]},link=f"/ramasseur#tour-{tour['id']}")
        if intent=="open_resource":
            if not payload.resource_id:return response(language,"Précisez l’identifiant de la ressource.","Specify the resource ID.",needs_clarification=True)
            if user["role"]=="citoyen":cur.execute("SELECT id FROM reports WHERE id=%s AND user_id=%s",(payload.resource_id,user["user_id"]));prefix="citoyen#signalement"
            elif user["role"]=="agent":cur.execute("SELECT id FROM reports WHERE id=%s AND agent_id=%s",(payload.resource_id,user["user_id"]));prefix="agent#signalement"
            else:cur.execute("SELECT id FROM tours WHERE id=%s AND collector_id=%s",(payload.resource_id,user["user_id"]));prefix="ramasseur#tour"
            row=cur.fetchone()
            if not row:raise HTTPException(404,"Ressource autorisée introuvable")
            return response(language,"Ressource autorisée disponible.","Authorized resource available.",facts={"resource_id":row["id"]},link=f"/{prefix}-{row['id']}")
        if intent=="unassigned_collections":
            cur.execute("SELECT COUNT(*) count FROM collection_occurrences WHERE collector_id IS NULL AND status IN ('programmee','reprogrammee','refusee')");count=cur.fetchone()["count"]
        elif intent=="late_tours":cur.execute("SELECT COUNT(*) count FROM tours WHERE status='en_cours' AND planned_date<CURRENT_DATE");count=cur.fetchone()["count"]
        elif intent=="open_incidents":cur.execute("SELECT COUNT(*) count FROM tour_incidents WHERE status='open'");count=cur.fetchone()["count"]
        elif intent=="reports_in_zone":
            if not payload.zone_id:return response(language,"Précisez une zone.","Specify a zone.",needs_clarification=True)
            cur.execute("SELECT COUNT(*) count FROM reports r JOIN zones z ON z.id=%s AND ST_Covers(z.geometry,r.geometry) WHERE z.active=TRUE",(payload.zone_id,));count=cur.fetchone()["count"]
        elif intent=="resources_requiring_action":cur.execute("SELECT COUNT(*) count FROM reports WHERE status IN ('a_verifier','en_attente_validation','verification_requise','reouvert')");count=cur.fetchone()["count"]
        else:raise HTTPException(422,"Intention non prise en charge")
        cur.execute("INSERT INTO audit_logs(actor_id,actor_role,action,resource_type,new_value) VALUES (%s,%s,'geo_assistant_sensitive_query','assistant',%s)",(user["user_id"],user["role"],Json({"intent":intent,"result_count":count})));conn.commit();return response(language,f"Résultat autorisé : {count}.",f"Authorized result: {count}.",facts={"intent":intent,"count":count})
    finally:cur.close();conn.close()
