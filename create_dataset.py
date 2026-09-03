# create_dataset.py
import os
import numpy as np
import rasterio
from rasterio.features import rasterize
from shapely.geometry import Point
import geopandas as gpd

def create_mask_from_point(width, height, transform, lon, lat, radius_m=100):
    """Crée un masque binaire avec un cercle autour du point."""
    point = Point(lon, lat)
    radius_deg = radius_m / 111000.0  # conversion approximative en degrés
    circle = point.buffer(radius_deg)
    mask = rasterize([(circle, 1)], out_shape=(height, width), transform=transform, fill=0, dtype='uint8')
    return mask

def generate_tiles(image_dir, zones_geojson, output_dir='dataset'):
    os.makedirs(os.path.join(output_dir, 'images'), exist_ok=True)
    os.makedirs(os.path.join(output_dir, 'masks'), exist_ok=True)
    gdf = gpd.read_file(zones_geojson)

    for idx, row in gdf.iterrows():
        img_file = os.path.join(image_dir, f"zone_{row['id']}.tif")
        if not os.path.exists(img_file):
            continue
        with rasterio.open(img_file) as src:
            img = src.read()  # (bands, H, W)
            height, width = img.shape[1], img.shape[2]
            mask = create_mask_from_point(width, height, src.transform, row.geometry.x, row.geometry.y, radius_m=100)
            # Découper en tuiles de 128x128
            tile_size = 128
            for i in range(0, height - tile_size + 1, tile_size):
                for j in range(0, width - tile_size + 1, tile_size):
                    tile_img = img[:, i:i+tile_size, j:j+tile_size]
                    tile_mask = mask[i:i+tile_size, j:j+tile_size]
                    # Garder les tuiles où le dépôt est présent (au moins 1% de pixels positifs)
                    if tile_mask.sum() / (tile_size*tile_size) < 0.01:
                        continue
                    tile_id = f"zone_{row['id']}_{i}_{j}"
                    np.save(os.path.join(output_dir, 'images', tile_id + '.npy'), tile_img)
                    np.save(os.path.join(output_dir, 'masks', tile_id + '.npy'), tile_mask)
    print("Dataset généré.")

if __name__ == "__main__":
    generate_tiles('images', 'zones_rouges.geojson')