
# download_sentinel_copernicus.py
from sentinelsat import SentinelAPI
import geopandas as gpd
from shapely.geometry import Point
from dotenv import load_dotenv
import os

load_dotenv()

# Identifiants Copernicus Data Space
USERNAME = os.getenv("COPERNICUS_USERNAME")
PASSWORD = os.getenv("COPERNICUS_PASSWORD")

if not USERNAME or not PASSWORD:
    raise RuntimeError("COPERNICUS_USERNAME et COPERNICUS_PASSWORD doivent être définis")

# Connexion
api = SentinelAPI(USERNAME, PASSWORD, 'https://apihub.copernicus.eu/apihub')

# Lire les zones rouges
zones = gpd.read_file('zones_rouges.geojson')

# Répertoire de sortie
output_dir = 'images_copernicus'
os.makedirs(output_dir, exist_ok=True)

# Pour chaque zone, chercher et télécharger la tuile la plus récente sans nuages
for idx, row in zones.iterrows():
    lon, lat = row.geometry.x, row.geometry.y
    footprint = Point(lon, lat).buffer(0.02)  # ~2 km buffer

    products = api.query(
        footprint.wkt,
        date=('20260101', '20260831'),
        platformname='Sentinel-2',
        cloudcoverpercentage=(0, 20),
        producttype='S2MSI2A'
    )

    # Prendre le premier produit (le plus récent)
    if products:
        product_id = list(products.keys())[0]
        print(f"Téléchargement de {product_id} pour la zone {row['id']}...")
        api.download(product_id, directory_path=output_dir)
    else:
        print(f"Aucune image trouvée pour la zone {row['id']}")

print("Téléchargements terminés.")