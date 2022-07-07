import os
import secrets
import aioredis
import pickle
from fastapi import (
    UploadFile,
    File,
    HTTPException,
    responses, APIRouter)
from PIL import Image
from io import BytesIO
from core.work_with_files import (
    clip_get_path,
    calculate_ndvi_values,
    calculate_ndvi_values_from_paths,
    prepare_zip,
)

from tools.calculation_ndva import (get_array,
                                    get_png_image,
                                    )
from .utils import (SentinelRequest,
                    check_geojson,
                    check_array,
                    check_png,
                    get_image,
                    check_path,
                    save_to_Redis,
                    convert_array_fromRedis,

                    )


r = aioredis.Redis(host='redis', port=6379, decode_responses=True)
router = APIRouter()
token_length = os.getenv('TOKEN_BYTES_LENGTH', 8)
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


@router.post('/pull_satellite_images/{geojson_id}')
async def pull_images(geojson_id, sentinel_request: SentinelRequest):
    geojson = await check_geojson(geojson_id)
    paths = await check_path(geojson_id)

    if paths is None:
        b04_path, b08_path = clip_get_path(geojson,
                                           sentinel_request,
                                           geojson_id)
        array_meta = get_array(b04_path, b08_path)
        if array_meta is not False:
            array, meta = array_meta
            png_data = BytesIO()
            path_png = get_png_image(array, geojson_id)
            im = Image.open(path_png)
            im.save(png_data, format=im.format)
            rset = await r.set(f'{geojson_id}_image', png_data.getvalue())
            if rset:
                await r.expire(f'{geojson_id}_image', int(geojson_hours_alive) * 60 * 60)
            png_data.close()
            array_bytes = save_to_Redis(array)
            result = check_array(array_bytes)
            rset = await r.set(f'{geojson_id}_array', bytes(array_bytes))
            if rset:
                await r.expire(f'{geojson_id}_array', int(geojson_hours_alive) * 60 * 60)

    else:
        paths = pickle.loads(paths)
        b04_path, b08_path = paths

    zip_bytes = prepare_zip(b04_path, b08_path)

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
    print("array_bytes", array_bytes)
    if array_bytes:
        result_array_convertation = await convert_array_fromRedis(array_bytes)
        print("array", result_array_convertation)

    geojson = await check_geojson(geojson_id)
    paths = await check_path(geojson_id)
    if paths is None:
        data = calculate_ndvi_values(geojson, sentinel_request, geojson_id)
    else:
        paths = pickle.loads(paths)
        b04_path, b08_path = paths
        data = calculate_ndvi_values_from_paths(b04_path, b08_path)
    return data


@router.post('/tif_ndvi/{geojson_id}')
async def ndvi_image_tif(geojson_id, sentiel_request: SentinelRequest):
    return await get_image(geojson_id, sentiel_request, True)


@router.post('/png_ndvi/{geojson_id}')
async def ndvi_image_png(geojson_id, sentiel_request: SentinelRequest):
    image_io = await check_png(geojson_id)
    if image_io:
        im_png = Image.open(image_io)
        return await im_png
    return await get_image(geojson_id, sentiel_request, False)
