import mimetypes

import aioredis
import numpy as np
from fastapi import HTTPException, responses
from pydantic import BaseModel

from .work_with_files import get_picture

r = aioredis.Redis(host='redis', port=6379, decode_responses=True)


class SentinelRequest(BaseModel):
    username: str
    password: str
    days_offset: int = 14
    cloud_cover: int = 15


async def check_geojson(geojson_id):
    geojson = await r.get(f'{geojson_id}_geojson')
    if geojson:
        return geojson

    else:
        raise HTTPException(404, detail='Not found, already deleted or '
                                        'invalid token')


async def check_zip(geojson_id):
    zip_bytes = await r.get(f'{geojson_id}_zip')
    return zip_bytes


async def check_path(geojson_id):
    paths = await r.get(f'{geojson_id}_paths')
    if paths:
        return paths
    return None


async def check_array(geojson_id):
    array = await r.get(f'{geojson_id}_array')
    if array:
        return array
    return None


async def check_png(geojson_id):
    image_png = await r.get(f'{geojson_id}_image')
    if image_png:
        return image_png
    return None


async def get_image(geojson_id, sentiel_request, tif):
    geojson = await check_geojson(geojson_id)
    path = get_picture(geojson, sentiel_request, geojson_id, tif)
    return responses.FileResponse(path, media_type=mimetypes.guess_type(
        path)[0], content_disposition_type='attachment', filename=path)


def save_to_Redis(arr: np.array) -> str:
    arr_dtype = bytearray(str(arr.dtype), 'utf-8')
    arr_shape = bytearray(','.join([str(a) for a in arr.shape]), 'utf-8')
    sep = bytearray('|', 'utf-8')
    array_bytes = arr.ravel().tobytes()
    to_return = arr_dtype + sep + arr_shape + sep + array_bytes
    return to_return


def convert_array_fromRedis(serialized_arr: str) -> np.array:
    sep = '|'.encode('utf-8')
    i_0 = serialized_arr.find(sep)
    i_1 = serialized_arr.find(sep, i_0 + 1)
    arr_dtype = serialized_arr[:i_0].decode('utf-8')
    arr_shape = tuple([int(a)
                      for a in serialized_arr[i_0 + 1:i_1].decode('utf-8').split(',')])
    arr_str = serialized_arr[i_1 + 1:]
    arr = np.frombuffer(arr_str, dtype=arr_dtype).reshape(arr_shape)

    return arr
