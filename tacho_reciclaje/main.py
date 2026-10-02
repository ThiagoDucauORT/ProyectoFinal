"""Arranca cámara, detector y enlace ESP32; libera recursos al salir."""
import time
import config
from camera import Camera
from detector import Detector
from controller import Controller
from esp32 import ClienteESP32, ESP32Simulado, ErrorESP32
import qr as qr_module
import display


def main():
    camera = None
    esp32 = None
    try:
        if config.ESP32_SIMULACION:
            print("[main] SIMULACIÓN ESP32: QR de prueba, sin sensor ni servo reales.")
            esp32 = ESP32Simulado()
        else:
            esp32 = ClienteESP32()
        camera = Camera()
        camera.iniciar()
        detector = Detector(camera)
        controller = Controller(camera, detector, esp32, display, qr_module)
        display.mostrar_mensaje("Sistema listo. Esperando objetos...")
        while True:
            controller.procesar_frame()
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\n[main] Apagando...")
    except ErrorESP32 as error:
        print(f"[main] ERROR ESP32: {error}. No se autorizan más depósitos.")
        return 1
    finally:
        # Cancelar ANTES de limpiar ventanas o cámara.
        try:
            if esp32 is not None:
                esp32.liberar()
        finally:
            try:
                if camera is not None:
                    camera.detener()
            finally:
                display.limpiar_display()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
