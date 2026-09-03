# download_sentinel_images.py
import ee
import geemap
import geopandas as gpd
import os

ee.Initialize()

def download_images_for_zones(geojson_path, buffer_m=200, start_date='2026-01-01', end_date='2026-08-31', output_dir='images'):
    gdf = gpd.read_file(geojson_path)
    os.makedirs(output_dir, exist_ok=True)

    for idx, row in gdf.iterrows():
        lat, lon = row.geometry.y, row.geometry.x
        point = ee.Geometry.Point([lon, lat]).buffer(buffer_m)
        collection = ee.ImageCollection('COPERNICUS/S2') \
            .filterBounds(point) \
            .filterDate(start_date, end_date) \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)) \
            .select(['B2','B3','B4','B8','B11','B12'])
        image = collection.median().clip(point)
        geemap.ee_export_image(
            image,
            filename=os.path.join(output_dir, f"zone_{row['id']}.tif"),
            scale=10,
            region=point,
            file_per_band=False
        )
        print(f"Image pour la zone {row['id']} téléchargée.")

if __name__ == "__main__":
    download_images_for_zones("zones_rouges.geojson")