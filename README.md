NDVI parser
Веб-приложение, построенное на FastAPI и Redis для расчета и получения NDVI-растров с помощью библиотеки sentinelsat. 


Для начала работы необходимо отправить GEOJSON файл исследуемой территории, в ответ вы получите уникальный токен, который нужен для дальнейшей обработки файла. Токен действителен 24 часа после получения.

После получения токена выберите нужную вам операцию и отправьте запрос к API. Токен нужно указать непосредственно в URL, а в body запроса нужно приложить username и password для доступа к copernicus (профиль создается в течение недели после регистрации). Для более точного запроса также можно указать days_offset(за какой период искать снимки) и cloud_cover(снимки с каким cloud cover percentage допускаются для обработки). В случае ошибки 500 стоит попробовать повысить эти параметры.


FROM python

FROM ubuntu:20.04

RUN apt-get install -y python3-pip

RUN pip install --upgrade pip

RUN pip install -r requirements.txt

if cant't install GDAL: $ sudo apt-add-repository ppa:ubuntugis/ubuntugis-unstable
                        $ sudo apt-get update
                        $ sudo apt-get install python-gdal
if cant't install rasterio: pip install https://github.com/rasterio/rasterio/archive/master.zip

CMD uvicorn main:app or uvicorn main:app --reload   

