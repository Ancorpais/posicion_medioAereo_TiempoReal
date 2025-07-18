#!/usr/bin/env python
# coding: utf-8

# # API - Medio Aereo Tiempo Real (ultima posición)
# 

# ## Configuración y librerías

# In[1]:


import requests
import time
from datetime import datetime
import json
from arcgis.gis import GIS
from arcgis.features import FeatureLayer
import threading


# In[2]:


dataset = '/arcgis/home/config_MedioAereo_Posicionamiento_TiempoReal.json'
with open(dataset, "r", encoding="utf-8") as file:
    config = json.load(file)
    workspace = config.get("workspace")
    capa_helicoptero = config.get("capa_helicoptero")
    medios_aereos = config.get("medios_aereos")
    portal = config.get("portal")
    user = config.get("user")
    password = config.get("password")
    api_key = config.get("api_key")
    salidaJson = config.get("salidaJson")
capa_helicoptero


# In[3]:


gis = GIS(portal, user, password)
capa = FeatureLayer(capa_helicoptero, gis=gis)


# ## Funciones

# In[4]:


def cargar_entidades(data, medio_aereo):
#     with open(json_path, 'r', encoding='utf-8') as f:
#         data = json.load(f)

    entidades_add = []
    ids_a_eliminar = []

    # 1. Buscar en la capa todos los registros que coincidan con el medio aéreo (nombre)
    where_clause = f"nombre = '{medio_aereo}'"

    try:
        query = capa.query(where=where_clause, out_fields="objectid")
        for feat in query.features:
            objectid = feat.attributes.get("objectid")
            if objectid is not None:
                ids_a_eliminar.append(objectid)
    except Exception as e:
        print(f"❌ Error al ejecutar la consulta por nombre: {e}")
        return {"error": str(e)}

    # 2. Procesar los datos del JSON y preparar entidades
    for entrada in data['points']:
        punto_datos = entrada['point']

        try:
            estado = punto_datos['info']
            coord = punto_datos['points']
            sensores = punto_datos['telemetria']
            fecha = punto_datos['time']

            x = coord['LONGITUDE']
            y = coord['LATITUDE']
            z = coord['ALTITUDE']

            fecha_evento = datetime.datetime(
                year=fecha['YEAR'],
                month=fecha['MONTH'],
                day=fecha['DAY'],
                hour=fecha['HOUR'],
                minute=fecha['MINUTE'],
                second=fecha['SECOND'],
                microsecond=fecha['MILLISECOND'] * 1000
            )

            atributos = {
                "mission_num": estado.get("MISSION_NUM"),
                "pkt_num": estado.get("PKT_NUM"),
                "status": estado.get("STATUS"),
                "longitude": x,
                "latitude": y,
                "altitude": z,
                "climb": coord.get("CLIMB"),
                "fix_mode": coord.get("FIX_MODE"),
                "heading": coord.get("HEADING"),
                "lidar_distance": coord.get("LIDAR_DISTANCE"),
                "sat_used": coord.get("SAT_USED"),
                "sat_vis": coord.get("SAT_VIS"),
                "speed": coord.get("SPEED"),
                "gpio_status": sensores.get("GPIO_STATUS"),
                "gps_status": sensores.get("GPS_STATUS"),
                "ir_status": sensores.get("IR_STATUS"),
                "lidar_status": sensores.get("LIDAR_STATUS"),
                "rgb_status": sensores.get("RGB_STATUS"),
                "fecha": fecha_evento,
                "nombre": medio_aereo
            }

            entidad = {
                "geometry": {
                    "x": x,
                    "y": y,
                    "z": z,
                    "spatialReference": {"wkid": 4326}
                },
                "attributes": atributos
            }

            entidades_add.append(entidad)

        except KeyError as e:
            print(f"❌ Error al procesar punto: {e}")
            return {"error": str(e)}

    # 3. Eliminar anteriores y añadir nuevas entidades
    try:
        resultado = capa.edit_features(
            deletes=ids_a_eliminar if ids_a_eliminar else None,
            adds=entidades_add
        )
        return resultado
    except Exception as e:
        print(f"❌ Error al guardar en la capa: {e}")
        return {"error": str(e)}


# In[5]:


def make_api_call(serial, token, url, headers, medio_aereo):
    try:
        response = requests.get(url, headers=headers)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        json = response.json()

        print(f"\n[{timestamp}] Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        cargar_entidades(json, medio_aereo)
        return response.status_code

    except requests.exceptions.RequestException as e:
        print(f"\nRequest error: {e}")
        return None


# In[6]:


def continuous_polling(medio_aereo, intervalo=10):
    # Configuration
    serial = medio_aereo
    token = api_key
    url = f"https://qcdn.hightek.it/v2/{serial}/lastPoint.json"
    headers = {
        "Authorization": f"Bearer {token}"
    }

    print("Starting sequential polling...")
    print(f"URL: {url}")
    print("Press CTRL+C to terminate\n")
    print("Waiting 1 second between calls...")

    try:
        while True:
            status = make_api_call(serial, token, url, headers, medio_aereo)

            # If the call fails, wait 5 seconds before retrying
            if status is None:
                print("Waiting 5 seconds before retrying...")
                time.sleep(intervalo)
                continue

            # Wait 1 second after each response before the next call
            print("\nWaiting 1 second...")
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nPolling terminated by user")


# ## Ejecución

# In[ ]:


if __name__ == "__main__":
    threads = []

    print("🚁 Lanzando seguimiento en paralelo para todos los medios aéreos...\n")

    for medio_aereo in medios_aereos:
        t = threading.Thread(target=continuous_polling, args=(medio_aereo, 10), daemon=True)
        t.start()
        threads.append(t)

    try:
        # Mantiene el hilo principal vivo para que los hilos hijos sigan activos
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Programa detenido por el usuario. Cerrando todos los hilos...")

