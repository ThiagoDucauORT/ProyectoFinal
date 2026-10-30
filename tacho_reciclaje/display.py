"""
display.py
==========
Salida de usuario para consola y display SPI ILI9488 de 3.5".
La interfaz táctil no se inicializa todavía: requiere identificar su
controlador y los pines propios del táctil (T_CS/T_IRQ, etc.).
"""

import config
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

_device = None
_device_error = None


def _fuente(tamano):
    """Carga una fuente legible y usa la fuente Pillow por defecto si falta."""
    for ruta in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        if Path(ruta).exists():
            try:
                return ImageFont.truetype(ruta, tamano)
            except Exception:
                pass
    return ImageFont.load_default()


def _obtener_display():
    """Inicialización diferida: un fallo del LCD no detiene cámara/ESP32."""
    global _device, _device_error
    if not getattr(config, "DISPLAY_HABILITADO", False):
        return None
    if _device is not None:
        return _device
    if _device_error is not None:
        return None

    try:
        from luma.core.interface.serial import spi
        from luma.lcd.device import ili9488

        interfaz = spi(
            port=config.DISPLAY_SPI_PORT,
            device=config.DISPLAY_SPI_DEVICE,
            gpio_DC=config.DISPLAY_DC_PIN,
            gpio_RST=config.DISPLAY_RESET_PIN,
            bus_speed_hz=getattr(config, "DISPLAY_SPI_HZ", 16000000),
        )
        _device = ili9488(
            interfaz,
            width=320,
            height=480,
            rotate=getattr(config, "DISPLAY_ROTACION", 0),
            bgr=getattr(config, "DISPLAY_BGR", False),
        )
        print("[display] ILI9488 inicializado por SPI.")
        return _device
    except Exception as error:
        _device_error = error
        print(f"[display] No se pudo inicializar ILI9488: {error}")
        print("[display] El programa continúa por consola.")
        return None


def _enviar_imagen(imagen):
    dispositivo = _obtener_display()
    if dispositivo is None:
        return False
    try:
        dispositivo.display(imagen)
        return True
    except Exception as error:
        print(f"[display] Error enviando imagen al LCD: {error}")
        return False


def mostrar_mensaje(texto):
    """Muestra el mensaje por consola y en el LCD si está disponible."""
    print(f"[display] {texto}")
    if not _PIL_OK:
        return
    imagen = Image.new("RGB", (320, 480), "black")
    dibujo = ImageDraw.Draw(imagen)
    fuente = _fuente(23)
    margen = 18
    ancho = 284
    palabras = str(texto).split()
    lineas = []
    actual = ""
    for palabra in palabras:
        prueba = f"{actual} {palabra}".strip()
        if dibujo.textbbox((0, 0), prueba, font=fuente)[2] <= ancho:
            actual = prueba
        else:
            if actual:
                lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    y = 45
    for linea in lineas[:12]:
        dibujo.text((margen, y), linea, font=fuente, fill="white")
        y += 34
    _enviar_imagen(imagen)


def mostrar_qr(ruta_png):
    """Presenta el QR en el LCD, conservando el PNG como respaldo."""
    print(f"[display] QR disponible en: {ruta_png}")
    if not _PIL_OK:
        print("[display] Pillow no está disponible; no se puede dibujar el QR.")
        return

    try:
        qr = Image.open(ruta_png).convert("RGB")
        # QR grande, cuadrado y con margen blanco para facilitar el escaneo.
        qr.thumbnail((286, 286), Image.Resampling.NEAREST)
        imagen = Image.new("RGB", (320, 480), "white")
        dibujo = ImageDraw.Draw(imagen)
        titulo = _fuente(25)
        subtitulo = _fuente(17)
        dibujo.text((22, 28), "Deposito confirmado", font=titulo, fill="black")
        x = (320 - qr.width) // 2
        y = 88 + (286 - qr.height) // 2
        imagen.paste(qr, (x, y))
        dibujo.text((35, 397), "Escanea tu codigo QR", font=subtitulo, fill="black")
        dibujo.text((82, 427), "Gracias por reciclar", font=subtitulo, fill="black")
        if not _enviar_imagen(imagen):
            print("[display] No se pudo mostrar el QR en el LCD.")
        else:
            print("[display] QR mostrado en ILI9488.")
    except Exception as error:
        print(f"[display] No se pudo preparar el QR ({error}).")
        return

    # El QR permanece visible mientras el controlador completa su pausa.
    # No se bloquea aquí para no detener el procesamiento de la cámara.


def limpiar_display():
    """Libera el LCD al cerrar el programa."""
    global _device
    if _device is not None:
        try:
            _device.cleanup()
        except Exception as error:
            print(f"[display] Aviso al liberar ILI9488: {error}")
        finally:
            _device = None
    print("[display] Display limpiado.")
