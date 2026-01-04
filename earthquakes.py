
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Sistema de Alerta de Sismos
Monitorea datos sísmicos en tiempo real y activa una alarma cuando se detecta un sismo significativo.
"""

import os
import time
import json
import math
import signal
import logging
import requests
import threading
import subprocess
from datetime import datetime

# Configuración del sistema
CONFIG = {
    # Coordenadas de tu ubicación exacta en Bogotá (reemplazar con tus coordenadas)
    "LOCATION": {
        "latitude": 4.6097,
        "longitude": -74.0817
    },
    # Distancia máxima en km para considerar un sismo relevante
    "MAX_DISTANCE": 300,
    # Magnitud mínima para considerar evacuación
    "EVACUATION_MAGNITUDE": 4.5,
    # Intervalo de verificación en segundos
    "CHECK_INTERVAL": 10,
    # Ruta al archivo de sonido de alarma
    "ALARM_SOUND": os.path.join(os.path.dirname(os.path.abspath(__file__)), "alarm.mp3"),
    # Duración máxima de la alarma en segundos
    "MAX_ALARM_DURATION": 120,
    # URL de la API del USGS para sismos recientes
    "USGS_API_URL": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_hour.geojson",
    # Directorio para almacenar logs y datos
    "DATA_DIR": os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"),

}
print("Carpeta de datos:", CONFIG["DATA_DIR"])

# Variables de estado
is_alarm_active = False
alarm_process = None
last_earthquake_id = None
shutdown_requested = False

# Configurar logging
if not os.path.exists(CONFIG["DATA_DIR"]):
    os.makedirs(CONFIG["DATA_DIR"], exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(CONFIG["DATA_DIR"], "system.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("earthquake_alert")

# Archivos de datos
LOG_FILE = os.path.join(CONFIG["DATA_DIR"], "earthquake_log.txt")
LAST_QUAKE_FILE = os.path.join(CONFIG["DATA_DIR"], "last_quake.json")

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calcula la distancia entre dos coordenadas usando la fórmula Haversine."""
    R = 6371  # Radio de la Tierra en km

    # Convertir coordenadas a radianes
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    # Diferencias de coordenadas
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    # Fórmula Haversine
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c

def play_alarm():
    """Reproduce el sonido de alarma."""
    global is_alarm_active, alarm_process

    if is_alarm_active:
        return  # Evitar múltiples alarmas simultáneas

    logger.info("¡ALERTA! ¡SISMO SIGNIFICATIVO DETECTADO! CONSIDERE EVACUAR.")
    print("\n¡ALERTA! ¡SISMO SIGNIFICATIVO DETECTADO! CONSIDERE EVACUAR.")
    print("Presione Ctrl+C y luego 'a' para reconocer y silenciar la alarma.")

    is_alarm_active = True

    try:
        # Verificar que el archivo de alarma existe
        if not os.path.exists(CONFIG["ALARM_SOUND"]):
            logger.error(f"Archivo de alarma no encontrado: {CONFIG['ALARM_SOUND']}")
            return

        # Detectar el sistema operativo para usar el reproductor adecuado
        if os.name == 'nt':  # Windows
            # Usar el reproductor de Windows Media Player
            alarm_process = subprocess.Popen(
                ["start", "", CONFIG["ALARM_SOUND"]],
                shell=True
            )
        elif os.name == 'posix':  # Linux/Mac
            # Intentar varios reproductores
            players = [
                ["mpg123", "-q", "--loop", "-1", CONFIG["ALARM_SOUND"]],
                ["mplayer", "-loop", "0", CONFIG["ALARM_SOUND"]],
                ["afplay", CONFIG["ALARM_SOUND"]]  # Para macOS
            ]

            for player_cmd in players:
                try:
                    alarm_process = subprocess.Popen(
                        player_cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    break
                except FileNotFoundError:
                    continue

        # Programar la detención automática después del tiempo máximo
        threading.Timer(CONFIG["MAX_ALARM_DURATION"], stop_alarm).start()

    except Exception as e:
        logger.error(f"Error al reproducir la alarma: {e}")
        is_alarm_active = False

def stop_alarm():
    """Detiene la reproducción de la alarma."""
    global is_alarm_active, alarm_process

    if not is_alarm_active:
        return

    is_alarm_active = False

    if alarm_process:
        try:
            if os.name == 'nt':  # Windows
                # En Windows, matar el proceso de Windows Media Player
                subprocess.call("taskkill /F /IM wmplayer.exe", shell=True)
            else:
                # En Linux/Mac, terminar el proceso
                alarm_process.terminate()

            alarm_process = None
            logger.info("Alarma detenida.")
            print("\nAlarma detenida.")
        except Exception as e:
            logger.error(f"Error al detener la alarma: {e}")

def log_earthquake(quake_data):
    """Registra información del sismo en un archivo de log."""
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"=== SISMO DETECTADO: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
            f.write(f"ID: {quake_data['id']}\n")
            f.write(f"Ubicación: {quake_data['location']}\n")
            f.write(f"Magnitud: {quake_data['magnitude']}\n")
            f.write(f"Profundidad: {quake_data['depth']} km\n")
            f.write(f"Tiempo: {quake_data['time']}\n")
            f.write(f"Distancia: {quake_data['distance']:.2f} km\n\n")
    except Exception as e:
        logger.error(f"Error al registrar el sismo: {e}")

def save_last_quake(quake_data):
    """Guarda información del último sismo detectado."""
    try:
        with open(LAST_QUAKE_FILE, "w") as f:
            json.dump(quake_data, f, indent=2)
    except Exception as e:
        logger.error(f"Error al guardar información del último sismo: {e}")

def load_last_quake():
    """Carga información del último sismo detectado."""
    global last_earthquake_id

    try:
        if os.path.exists(LAST_QUAKE_FILE):
            with open(LAST_QUAKE_FILE, "r") as f:
                quake_data = json.load(f)
                last_earthquake_id = quake_data.get("id")
    except Exception as e:
        logger.error(f"Error al cargar información del último sismo: {e}")

def check_earthquakes():
    """Verifica sismos recientes y activa la alarma si es necesario."""
    global last_earthquake_id

    try:
        # Consultar la API del USGS
        response = requests.get(CONFIG["USGS_API_URL"], timeout=10)
        data = response.json()
        features = data.get("features", [])

        if not features:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] No hay sismos recientes que reportar.")
            return

        # Filtrar sismos por proximidad a la ubicación configurada
        nearby_quakes = []
        for quake in features:
            quake_coords = quake["geometry"]["coordinates"]
            quake_lat = quake_coords[1]
            quake_lon = quake_coords[0]

            distance = calculate_distance(
                CONFIG["LOCATION"]["latitude"],
                CONFIG["LOCATION"]["longitude"],
                quake_lat,
                quake_lon
            )

            if distance <= CONFIG["MAX_DISTANCE"]:
                nearby_quakes.append({
                    "quake": quake,
                    "distance": distance
                })

        if not nearby_quakes:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] No hay sismos cercanos a tu ubicación.")
            return

        # Ordenar por magnitud (de mayor a menor)
        nearby_quakes.sort(key=lambda x: x["quake"]["properties"]["mag"], reverse=True)

        # Verificar el sismo más fuerte
        strongest = nearby_quakes[0]
        quake_obj = strongest["quake"]
        quake_id = quake_obj["id"]

        # Evitar alertar sobre el mismo sismo múltiples veces
        if quake_id == last_earthquake_id:
            return

        # Extraer información del sismo
        magnitude = quake_obj["properties"]["mag"]
        depth = quake_obj["geometry"]["coordinates"][2]
        location = quake_obj["properties"]["place"]
        time_ms = quake_obj["properties"]["time"]
        quake_time = datetime.fromtimestamp(time_ms/1000).strftime('%Y-%m-%d %H:%M:%S')
        distance = strongest["distance"]

        # Guardar información del sismo
        quake_data = {
            "id": quake_id,
            "magnitude": magnitude,
            "depth": depth,
            "location": location,
            "time": quake_time,
            "distance": distance
        }

        last_earthquake_id = quake_id
        save_last_quake(quake_data)
        log_earthquake(quake_data)

        # Mostrar información del sismo
        print("\n=== INFORMACIÓN DE SISMO DETECTADO ===")
        print(f"Ubicación: {location}")
        print(f"Magnitud: {magnitude}")
        print(f"Profundidad: {depth} km")
        print(f"Tiempo: {quake_time}")
        print(f"Distancia: {distance:.2f} km")

        # Determinar si se requiere evacuación basado en la magnitud
        if magnitude >= CONFIG["EVACUATION_MAGNITUDE"]:
            play_alarm()
        else:
            print("Este sismo no requiere evacuación inmediata, pero manténgase alerta.")

    except requests.exceptions.RequestException as e:
        logger.error(f"Error al conectar con la API del USGS: {e}")
        print(f"Error de conexión: {e}")
    except Exception as e:
        logger.error(f"Error al verificar sismos: {e}")
        print(f"Error: {e}")

def handle_keyboard_input():
    """Maneja la entrada de teclado para controlar la alarma."""
    global shutdown_requested

    print("Presione 'a' para reconocer y silenciar una alarma activa, o 'q' para salir")

    while not shutdown_requested:
        try:
            # Leer un carácter sin necesidad de presionar Enter
            if os.name == 'nt':  # Windows
                import msvcrt
                if msvcrt.kbhit():
                    key = msvcrt.getch().decode('utf-8').lower()
                    if key == 'a' and is_alarm_active:
                        stop_alarm()
                    elif key == 'q':
                        shutdown_requested = True
                        stop_alarm()
                        print("\nCerrando sistema de alerta de sismos...")
            else:  # Linux/Mac
                import termios, sys, tty
                old_settings = termios.tcgetattr(sys.stdin)
                try:
                    tty.setcbreak(sys.stdin.fileno())
                    if sys.stdin.read(1).lower() == 'a' and is_alarm_active:
                        stop_alarm()
                    elif sys.stdin.read(1).lower() == 'q':
                        shutdown_requested = True
                        stop_alarm()
                        print("\nCerrando sistema de alerta de sismos...")
                finally:
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

            time.sleep(0.1)
        except Exception:
            # Si hay un error en la lectura del teclado, simplemente continuamos
            time.sleep(0.1)

def signal_handler(sig, frame):
    """Maneja señales para una terminación limpia del programa."""
    global shutdown_requested
    print("\nSeñal de terminación recibida. Cerrando el sistema...")
    shutdown_requested = True
    stop_alarm()

def main():
    """Función principal del sistema de alerta de sismos."""
    global shutdown_requested

    # Registrar manejadores de señales
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Cargar información del último sismo
    load_last_quake()

    print('=== SISTEMA DE ALERTA DE SISMOS INICIADO ===')
    print(f"Monitoreando sismos cerca de: {CONFIG['LOCATION']['latitude']}, {CONFIG['LOCATION']['longitude']}")
    print(f"Distancia máxima de monitoreo: {CONFIG['MAX_DISTANCE']} km")
    print(f"Magnitud mínima para evacuación: {CONFIG['EVACUATION_MAGNITUDE']}")
    print(f"Intervalo de verificación: {CONFIG['CHECK_INTERVAL']} segundos")
    print('===================================================\n')

    # Iniciar hilo para manejar entrada de teclado
    keyboard_thread = threading.Thread(target=handle_keyboard_input)
    keyboard_thread.daemon = True
    keyboard_thread.start()

    # Verificar inmediatamente al iniciar
    check_earthquakes()

    # Bucle principal
    last_check = time.time()
    while not shutdown_requested:
        current_time = time.time()
        elapsed = current_time - last_check

        if elapsed >= CONFIG["CHECK_INTERVAL"]:
            check_earthquakes()
            last_check = current_time

        # Dormir un poco para no consumir CPU innecesariamente
        time.sleep(1)

    print("Sistema de alerta de sismos detenido.")

if __name__ == "__main__":
    main()
