from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List
import psycopg2.extras
from database import get_db_connection
from core.security import decode_token
from app.services.live_tracking import update_agent_position

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])
security = HTTPBearer()

def get_agent_id(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_token(credentials.credentials)
    if not payload or payload["role"] not in ["agent", "admin", "municipal"]:
        raise HTTPException(403, "Accès refusé")
    return payload["user_id"]

@router.post("/position")
async def envoyer_position(
    lat: float,
    lon: float,
    agent_id: int = Depends(get_agent_id)
):
    """L'agent envoie sa position GPS en temps réel."""
    await update_agent_position(agent_id, lat, lon)
    return {"status": "ok", "lat": lat, "lon": lon}

@router.get("/tournee/{tournee_id}/points")
async def get_points_tournee(
    tournee_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Retourne les points (signalements) d'une tournée avec statut."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT r.id, r.severity, r.confidence, r.status, r.waste_type,
               ST_Y(r.geometry) AS lat, ST_X(r.geometry) AS lon
        FROM reports r
        WHERE r.id IN (SELECT report_id FROM tournee_signalements WHERE tournee_id = %s)
        ORDER BY r.id
    """, (tournee_id,))
    points = cur.fetchall()
    cur.close()
    conn.close()
    return points

@router.get("/tournee/{tournee_id}/itineraire")
async def get_itineraire_tournee(
    tournee_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Calcule l'itinéraire routier réel entre les points de la tournée."""
    from route_optimizer import get_graph, calculer_matrice_distances
    import networkx as nx
    import osmnx as ox
    import json

    points = await get_points_tournee(tournee_id, credentials)
    if len(points) < 2:
        return {"geometry": None, "message": "Pas assez de points"}

    coords = [(p["lat"], p["lon"]) for p in points]
    G = get_graph()
    noeuds = [ox.distance.nearest_nodes(G, lon, lat) for lat, lon in coords]

    # Construire le GeoJSON de la route (concaténation des plus courts chemins)
    route_geojson = {"type": "FeatureCollection", "features": []}
    for i in range(len(noeuds)-1):
        try:
            chemin = nx.shortest_path(G, noeuds[i], noeuds[i+1], weight='length')
            coords_chemin = [(G.nodes[n]['x'], G.nodes[n]['y']) for n in chemin]
            route_geojson["features"].append({
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": coords_chemin},
                "properties": {"from": i, "to": i+1}
            })
        except nx.NetworkXNoPath:
            continue

    return {"geometry": route_geojson}

@router.post("/signalement/{signalement_id}/preuve")
async def envoyer_preuve(
    signalement_id: int,
    file: UploadFile = File(...),
    lat: float = Form(...),
    lon: float = Form(...),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """L'agent confirme la collecte avec photo de preuve."""
    # Vérifier le rôle
    payload = decode_token(credentials.credentials)
    if not payload or payload["role"] not in ["agent", "admin", "municipal"]:
        raise HTTPException(403, "Accès refusé")

    image_bytes = await file.read()
    photo_base64 = base64.b64encode(image_bytes).decode('utf-8')
    conn = get_db_connection()
    cur = conn.cursor()
    # Statut : traité si l'IA voit "trash", sinon verification_requise (logique déjà existante dans main.py)
    # On réutilise la fonction predict_type du main
    from main import predict_type
    type_dechet, confiance = predict_type(image_bytes)
    if type_dechet != 'trash':
        resultat = "echec"
        nouveau_statut = "verification_requise"
    else:
        resultat = "valide"
        nouveau_statut = "traite"

    cur.execute("""
        UPDATE reports SET status = %s, photo_preuve_base64 = %s,
        resultat_preuve = %s, confiance_preuve = %s, date_traitement = NOW()
        WHERE id = %s RETURNING id, status
    """, (nouveau_statut, photo_base64, resultat, confiance, signalement_id))
    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    return {"id": result[0], "status": result[1], "type_dechet_detecte": type_dechet}