import os.path
from copy import copy

import geojson as gj
import numpy
import rasterio
from matplotlib import image
from matplotlib.colors import ListedColormap
from osgeo import gdal
from sentinelsat import SentinelAPI, geojson_to_wkt, products


def validate_path(result: list):
    images = []

    for path in result:
        if 'IMG_DATA' in path and path.endswith('jp2'):
            images.append(path)

    for ind in range(len(images)):
        try:
            sample1 = images[ind].replace('4', '').replace('8', '')
            sample2 = images[ind + 1].replace('4', '').replace('8', '')
            if sample1 == sample2:
                if 'B04' in images[ind]:
                    group04, group08 = images[ind], images[ind + 1]
                else:
                    group04, group08 = images[ind + 1], images[ind]
                return group04, group08
        except IndexError:
            break

    return False


def pull_geojson_for_images_(geojson,
                             username,
                             password,
                             cloudcover,
                             days_offset):
    api = SentinelAPI(username, password)
    footprint = geojson_to_wkt(gj.loads(geojson))
    search_query = api.query(footprint,
                             date=(f"NOW-{days_offset}DAY",
                                   "NOW"),
                             platformname='Sentinel-2',
                             cloudcoverpercentage=(0, cloudcover),
                             limit=1)

    if not search_query:
        return False

    download_filter = products.make_path_filter("*B0[48]*.jp2")
    path = api.download_all(search_query,
                            nodefilter=download_filter)

    if not path:
        return False

    path = path[0][list(path[0].keys())[0]]
    b04_path, b08_path = validate_path(list(path['nodes'].keys()))

    if not b04_path or not b08_path:
        return False

    download_folder = path['node_path']
    b04_path = download_folder + b04_path[1:]
    b08_path = download_folder + b08_path[1:]

    return b04_path, b08_path


def clip_tif(band4_path, band8_path, geojson, token):
    try:
        geojson = geojson.decode()
    except AttributeError:
        pass
    for band, file in zip([4, 8], [band4_path, band8_path]):
        try:
            gdal.Warp(f'{token}_0{band}.jp2',
                      file,
                      cutlineDSName=geojson,
                      cropToCutline=True,
                      format='GTiff')

        except Exception as exc:
            print('CLIP TIF FAILED\n', exc)
            return False

    return f'{token}_04.jp2', f'{token}_08.jp2'


def get_array(band4_path, band8_path):
    try:
        if os.path.exists(band4_path) or os.path.exists(band8_path):
            with rasterio.open(band4_path) as src4, \
                    rasterio.open(band8_path) as src8:
                band4 = src4.read(1)
                band8 = src8.read(1)
                numpy.seterr(divide='ignore', invalid='ignore')
                ndvi = (band8 - band4) / (
                    band8.astype(float) + band4.astype(float))
                ndvi[ndvi > 1] = None
                return ndvi, src8
        else:
            raise FileNotFoundError
    except Exception as exc:
        print('GET ARRAY FAILED\n', exc)
        return False


def get_tif(array, meta, token):
    try:
        data = copy(meta.meta)
        data.update(
            driver='GTiff',
            dtype=array.dtype,
            count=1,
            width=array.shape[1],
            height=array.shape[0],
        )
        with rasterio.open(f'{token}.tif', 'w', **data) as ndvi_handle:
            ndvi_handle.write(array, 1)

        return f'{token}.tif'
    except Exception as exc:
        print('GET TIF FAILED\n', exc)
        return False


def get_png_image(array, token):
    try:
        color_list = ["gray", "y", "yellowgreen", "g", "darkgreen"]

        cmap = ListedColormap(color_list)
        image.imsave(f'{token}.png', array,
                     cmap=cmap,
                     vmin=0,
                     vmax=1)
        return f'{token}.png'

    except Exception as exc:
        print('GET PNG FAILED\n', exc)
        return False
