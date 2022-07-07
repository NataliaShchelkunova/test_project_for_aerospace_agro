import os
import secrets
import traceback
from io import BytesIO

import aioredis
import numpy as np
from core.work_with_files import clip_get_path, prepare_zip
from fastapi import APIRouter, File, HTTPException, UploadFile, responses
from PIL import Image
from tools.calculation_ndva import get_array, get_png_image

from .utils import (
    SentinelRequest,
    check_array,
    check_geojson,
    check_png,
    check_zip,
    convert_array_fromRedis,
    save_to_Redis,
)

r = aioredis.Redis(host='redis', port=6379, decode_responses=True)
router = APIRouter()

token_length = os.getenv('TOKEN_BYTES_LENGTH', 6)
geojson_hours_alive = os.getenv('GEOJSON_HOURS_ALIVE', 24)


@router.post("/upload_geojson/")
async def load_geojson(file: UploadFile = File()):
    token = secrets.token_urlsafe(int(token_length))
    rset = await r.set(f'{token}_geojson', file.file.read())
    if rset:
        await r.expire(f'{token}_geojson', int(geojson_hours_alive) * 60 * 60)
        return {"token": token,
                "message": f'Created! File be alive for {geojson_hours_alive}'
                           f' hours'}
    else:
        return HTTPException(500)


@router.delete('/delete_geojson/{geojson_id}')
async def delete_geojson(geojson_id):
    rdel = await r.delete(f'{geojson_id}_geojson')
    if rdel:
        raise HTTPException(204, detail='Deleted')
    else:
        raise HTTPException(404, detail='Not found, already deleted or '
                                        'invalid token')


@router.post('/pull_data/{geojson_id}')
async def pull_data(geojson_id, sentinel_request: SentinelRequest):
    try:
        geojson = await check_geojson(geojson_id)
        array = await check_array(geojson_id)
        zip_bytes = await check_zip(geojson_id)
        if None in (array, zip_bytes):
            b04_path, b08_path = clip_get_path(geojson,
                                               sentinel_request,
                                               geojson_id)
            array_meta = get_array(b04_path, b08_path)
            if array_meta:
                array, _ = array_meta
            else:
                raise HTTPException(404, detail='Not found array, already deleted or '
                                    'invalid token')
            zip_bytes = prepare_zip(b04_path, b08_path)
            rset = await r.set(f'{geojson_id}_zip', zip_bytes.getvalue())
            if rset:
                await r.expire(f'{geojson_id}_zip', int(geojson_hours_alive) * 60 * 60)
        if type(array) == bytes:
            array = convert_array_fromRedis(array)
        png_data = BytesIO()
        path_png = get_png_image(array, geojson_id)
        if not path_png:
            raise FileNotFoundError
        im = Image.open(path_png)
        im.save(png_data, format=im.format)
        rset = await r.set(f'{geojson_id}_image', png_data.getvalue())
        if rset:
            await r.expire(f'{geojson_id}_image', int(geojson_hours_alive) * 60 * 60)
        png_data.close()
        array_bytes = save_to_Redis(array)
        rset = await r.set(f'{geojson_id}_array', bytes(array_bytes))
        if rset:
            await r.expire(f'{geojson_id}_array', int(geojson_hours_alive) * 60 * 60)
        return {
            "token": geojson_id,
            "message": f'Created! File be alive for {geojson_hours_alive}'
            f' hours'
        }
    except Exception as exp:
        traceback.print_exc()
        return HTTPException(404, detail='Not found data, already deleted or '
                             'invalid token')


@router.post('/pull_satellite_images/{geojson_id}')
async def pull_images(geojson_id, sentinel_request: SentinelRequest):
    zip_bytes = await check_zip(geojson_id)
    if zip_bytes is None:
        is_ok = await pull_data(geojson_id, sentinel_request)
        if type(is_ok) != dict:
            return is_ok
        else:
            zip_bytes = await check_zip(geojson_id)
    zip_bytes = BytesIO(zip_bytes)
    return responses.StreamingResponse(iter([zip_bytes.getvalue()]),
                                       media_type="application/"
                                                  "x-zip-compressed",
                                       headers={
                                           "Content-Disposition":
                                               f"attachment;filename="
                                               f"{geojson_id}.zip"})


@router.post('/calculate_ndvi/{geojson_id}')
async def calculate_ndvi(geojson_id, sentinel_request: SentinelRequest):
    array_bytes = await check_array(geojson_id)
    if array_bytes is None:
        is_ok = await pull_data(geojson_id, sentinel_request)
        if type(is_ok) != dict:
            return is_ok
        else:
            array_bytes = await check_array(geojson_id)
    result_array_convertation = convert_array_fromRedis(array_bytes)
    return {
        "max": np.nanmax(result_array_convertation),
        "mean": np.nanmean(result_array_convertation),
        "median": np.nanmedian(result_array_convertation),
        "min": np.nanmin(result_array_convertation)
    }


@router.post('/im_ndvi/{geojson_id}')
async def ndvi_image(geojson_id, sentiel_request: SentinelRequest):
    image = await check_png(geojson_id)
    if image is None:
        is_ok = await pull_data(geojson_id, sentiel_request)
        if type(is_ok) != dict:
            return is_ok
        else:
            image = await check_png(geojson_id)
    return responses.StreamingResponse(BytesIO(image), media_type="image/png")
