"""
main.py
=======
Punto de entrada del sistema. Su única responsabilidad es:
  1. Inicializar todos los módulos (con manejo de errores claro).
  2. Construir el controlador con esos módulos.
  3. Correr el bucle principal (un frame por vuelta).
  4. Apagar todo de forma ordenada al terminar (Ctrl+C).

No tiene lógica del tacho: esa vive en controller.py. main.py solo "arma
la orquesta y da la señal de arranque".
"""

import sys
import time

import config
from camera import Camera
from detector import Detector
from servo import ControlServos
from distance_sensor import SensorDistancia
from controller import Controller
import qr as qr_module
import display


def inicializar_modulos():
    """
    Crea e inicializa cada módulo. Si algo falla, lo decimos claramente y
    cortamos (sección 17: manejo de errores).
    Devuelve todos los módulos listos.
    """
    print("=" * 60)
    print("  TACHO INTELIGENTE DE RECICLAJE - inicializando")
    print("=" * 60)

    # --- Cámara + IMX500 ---------------------------------------------------
    try:
        camera = Camera()
        camera.iniciar()
    except Exception as e:
        print(f"[main] ERROR al iniciar la cámara/IMX500: {e}")
        sys.exit(1)

    # --- Detector (necesita la cámara para leer labels/tamaños) -----------
    try:
        detector = Detector(camera)
    except Exception as e:
        print(f"[main] ERROR al iniciar el detector: {e}")
        camera.detener()
        sys.exit(1)

    # --- Servos ------------------------------------------------------------
    try:
        servos = ControlServos()
    except Exception as e:
        print(f"[main] ERROR al iniciar los servos: {e}")
        camera.detener()
        sys.exit(1)

    # --- Sensor de distancia ----------------------------------------------
    try:
        sensor = SensorDistancia()
    except Exception as e:
        print(f"[main] ERROR al iniciar el HC-SR04: {e}")
        camera.detener()
        servos.liberar_todo()
        sys.exit(1)

    print("[main] Todos los módulos inicializados correctamente.\n")
    return camera, detector, servos, sensor


def main():
    camera, detector, servos, sensor = inicializar_modulos()

    controller = Controller(
        camera=camera,
        detector=detector,
        servos=servos,
        sensor=sensor,
        display=display,
        qr_module=qr_module,
    )

    display.mostrar_mensaje("Sistema listo. Esperando objetos...\n")

    try:
        # BUCLE PRINCIPAL: procesamos un frame por vuelta, indefinidamente.
        while True:
            controller.procesar_frame()
            # Pequeña pausa para no saturar la CPU con vueltas vacías.
            # El sensor ya limita la tasa real de inferencia.
            time.sleep(0.01)

    except KeyboardInterrupt:
        # Ctrl+C: salida limpia.
        print("\n[main] Interrupción recibida. Apagando...")

    finally:
        # Apagado ordenado: liberamos hardware pase lo que pase.
        display.limpiar_display()
        sensor.liberar()
        servos.liberar_todo()
        camera.detener()
        print("[main] Apagado completo. Chau!")


if __name__ == "__main__":
    main()
