import requests
import psycopg2
from database import get_db_connection

def get_osm_points_douala():
    """
    Récupère les points de collecte et recyclage depuis OpenStreetMap.
    Utilise un serveur Overpass alternatif.
    """
    # Serveurs Overpass alternatifs
    serveurs = [
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass-api.de/api/interpreter",
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
    ]
    
    query = """
    [out:json][timeout:30];
    node["amenity"="recycling"](3.80,9.50,4.20,9.90);
    out body;
    """
    
    for serveur in serveurs:
        try:
            print(f"Essai du serveur : {serveur}")
            response = requests.post(
                serveur, 
                data={"data": query}, 
                timeout=30,
                headers={"User-Agent": "SmartWasteCM/1.0"}
            )
            response.raise_for_status()
            data = response.json()
            
            points = []
            for element in data.get("elements", []):
                tags = element.get("tags", {})
                points.append({
                    "nom": tags.get("name", f"Point recyclage {element['id']}"),
                    "type_activite": "recyclage",
                    "lat": element["lat"],
                    "lon": element["lon"],
                    "types_dechets": ["tout"]
                })
            
            print(f"✅ {len(points)} points trouvés sur {serveur}")
            return points
            
        except Exception as e:
            print(f"❌ Erreur {serveur} : {e}")
    
    return []

def inserer_points_osm():
    """
    Insère les points OSM dans la base.
    """
    points = get_osm_points_douala()
    
    if not points:
        print("Aucun point OSM récupéré. Passage à l'étape suivante.")
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    for p in points:
        cur.execute("""
            INSERT INTO points_collecte (nom, type_activite, geometry, types_dechets, source, fiabilite)
            VALUES (%s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, 'OSM', 'enquete')
        """, (p["nom"], p["type_activite"], p["lon"], p["lat"], p["types_dechets"]))
    
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"✅ {len(points)} points OSM insérés")

if __name__ == "__main__":
    inserer_points_osm()