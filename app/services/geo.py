from dataclasses import dataclass
from math import asin,cos,radians,sin,sqrt

DOUALA_BOUNDS=(3.70,9.30,4.35,10.05)

@dataclass(frozen=True)
class BoundingBox:
    south:float;west:float;north:float;east:float
    def as_envelope_params(self): return self.west,self.south,self.east,self.north

def validate_coordinate(latitude:float,longitude:float,*,douala_only:bool=False)->None:
    if not (-90<=latitude<=90 and -180<=longitude<=180): raise ValueError("Coordonnées invalides")
    if douala_only:
        south,west,north,east=DOUALA_BOUNDS
        if not (south<=latitude<=north and west<=longitude<=east): raise ValueError("Position hors zone prise en charge")

def validate_bbox(south:float,west:float,north:float,east:float)->BoundingBox:
    validate_coordinate(south,west);validate_coordinate(north,east)
    if south>=north or west>=east or north-south>2 or east-west>2: raise ValueError("Emprise géographique invalide ou excessive")
    return BoundingBox(south,west,north,east)

def haversine_meters(first:tuple[float,float],second:tuple[float,float])->float:
    validate_coordinate(*first);validate_coordinate(*second)
    lat1,lon1,lat2,lon2=map(radians,(*first,*second));dlat=lat2-lat1;dlon=lon2-lon1
    value=sin(dlat/2)**2+cos(lat1)*cos(lat2)*sin(dlon/2)**2
    return 2*6371008.8*asin(sqrt(value))

def point_in_operational_zone(cur,latitude:float,longitude:float,zone_id:int)->bool:
    validate_coordinate(latitude,longitude)
    cur.execute("SELECT ST_Covers(geometry,ST_SetSRID(ST_MakePoint(%s,%s),4326)) FROM zones WHERE id=%s AND active=TRUE AND geometry IS NOT NULL AND ST_IsValid(geometry) AND ST_SRID(geometry)=4326",(longitude,latitude,zone_id))
    row=cur.fetchone();return bool(row and row[0])
