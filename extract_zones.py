import requests
import json
import time
from shapely.geometry import Polygon, MultiPolygon, shape, Point
from shapely.ops import transform
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

arrondissements = [
    "Douala I",
    "Douala II",
    "Douala III",
    "Douala IV",
    "Douala V",
    "Douala VI"
]

zones_data = []

for arr in arrondissements:
    print(f"Recherche de {arr}...")
    
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": f"{arr}, Douala, Cameroon",
        "format": "json",
        "polygon_geojson": 1,
        "limit": 1
    }
    headers = {
        "User-Agent": "SmartWasteCM/1.0 (projet memoire)"
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if data:
                geojson = data[0].get("geojson")
                if geojson:
                    geom = shape(geojson)
                    
                    # Si c'est un Point, créer une zone tampon
                    if isinstance(geom, Point):
                        geom = geom.buffer(0.02)  # environ 2 km
                        print(f"  ⚠️ {arr} est un point, buffer créé")
                    
                    # Si c'est un Polygon, convertir en MultiPolygon si nécessaire
                    elif isinstance(geom, Polygon):
                        pass  # on accepte aussi les polygones simples
                    
                    zones_data.append((arr, geom.wkt))
                    print(f"  ✅ {arr} trouvé")
                else:
                    print(f"  ❌ Pas de géométrie pour {arr}")
            else:
                print(f"  ❌ {arr} non trouvé")
        else:
            print(f"  ❌ Erreur HTTP {response.status_code} pour {arr}")
    except Exception as e:
        print(f"  ❌ Erreur pour {arr}: {e}")
    
    time.sleep(1)

# Insérer dans PostgreSQL en convertissant tout en MultiPolygon
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

for nom, geom_wkt in zones_data:
    # Conversion sécurisée vers MultiPolygon dans PostGIS
    cur.execute("""
        INSERT INTO zones (nom, geometry, zone_type, source)
        VALUES (
            %s,
            ST_Multi(ST_SetSRID(%s::geometry, 4326)),
            'arrondissement',
            'OSM/Nominatim'
        )
    """, (nom, geom_wkt))

conn.commit()
cur.close()
conn.close()

print(f"\n✅ {len(zones_data)} arrondissements insérés avec succès")
for nom, _ in zones_data:
    print(f"  - {nom}")