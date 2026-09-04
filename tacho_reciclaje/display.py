"""
display.py
==========
Interfaz con el DISPLAY. El display físico todavía NO existe, así que este
módulo trabaja en "modo consola": imprime mensajes por pantalla y opcional-
mente abre una ventana para mostrar el QR generado.

Idea de diseño (sección 13 del brief):
  - El resto del programa NO debe saber si hay display físico o no.
  - Habla siempre con estas 3 funciones: mostrar_mensaje, mostrar_qr,
    limpiar_display.
  - Cuando tengas el display real, SOLO tocás este archivo. El controlador
    ni se entera.

La ventana del QR se abre con OpenCV si está disponible y si
config.DISPLAY_MOSTRAR_VENTANA_QR = True. Si corrés headless por SSH sin
entorno gráfico, poné esa opción en False y todo sigue funcionando por
consola.
"""

import config

# OpenCV es opcional: solo lo usamos para la ventana de prueba del QR.
# Si no está o no hay entorno gráfico, seguimos sin romper.
try:
    import cv2
    _CV2_OK = True
except ImportError:
    _CV2_OK = False


def mostrar_mensaje(texto):
    """Muestra un mensaje al usuario. Hoy: por consola."""
    print(f"[display] {texto}")


def mostrar_qr(ruta_png):
    """
    Muestra el QR generado. Hoy:
      - Siempre avisa por consola dónde quedó el PNG.
      - Si hay OpenCV + entorno gráfico + la opción activada, abre una
        ventana con el QR unos segundos.
    """
    print(f"[display] QR disponible en: {ruta_png}")

    if not config.DISPLAY_MOSTRAR_VENTANA_QR:
        return
    if not _CV2_OK:
        print("[display] (OpenCV no disponible; no se abre ventana de QR)")
        return

    try:
        imagen = cv2.imread(ruta_png)
        if imagen is None:
            print("[display] No se pudo leer el PNG del QR.")
            return
        cv2.imshow("QR - TEST RECICLAJE", imagen)
        # waitKey(0) espera una tecla; usamos un tiempo para que no bloquee
        # el ciclo del tacho para siempre. 3000 ms = 3 s.
        cv2.waitKey(3000)
        cv2.destroyWindow("QR - TEST RECICLAJE")
    except Exception as e:
        # Típico si no hay entorno gráfico (headless). No es fatal.
        print(f"[display] No se pudo abrir la ventana del QR ({e}).")


def limpiar_display():
    """Limpia el display. Hoy: cierra ventanas de OpenCV si las hubiera."""
    if _CV2_OK:
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass
    print("[display] Display limpiado.")
