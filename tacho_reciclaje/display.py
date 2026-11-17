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
            width=480,
            height=320,
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
    """Muestra mensajes centrados y con ajuste automático en el LCD."""
    print(f"[display] {texto}")
    if not _PIL_OK:
        return

    ancho_pantalla, alto_pantalla = 480, 320
    imagen = Image.new("RGB", (ancho_pantalla, alto_pantalla), (12, 20, 32))
    dibujo = ImageDraw.Draw(imagen)

    # Marco discreto para dar una apariencia más cuidada sin distraer.
    dibujo.rounded_rectangle(
        (10, 10, ancho_pantalla - 11, alto_pantalla - 11),
        radius=14,
        outline=(35, 105, 125),
        width=2,
    )
    dibujo.rounded_rectangle(
        (22, 22, ancho_pantalla - 23, 28),
        radius=3,
        fill=(35, 190, 190),
    )

    margen = 34
    ancho_texto = ancho_pantalla - 2 * margen
    palabras = str(texto).split()

    # Reducir la fuente si el mensaje necesita muchas líneas.
    lineas = []
    fuente = _fuente(25)
    for tamano in (25, 23, 21, 19):
        fuente = _fuente(tamano)
        lineas = []
        actual = ""
        for palabra in palabras:
            prueba = f"{actual} {palabra}".strip()
            if dibujo.textbbox((0, 0), prueba, font=fuente)[2] <= ancho_texto:
                actual = prueba
            else:
                if actual:
                    lineas.append(actual)
                # Evita que una palabra excepcionalmente larga desborde.
                actual = palabra
        if actual:
            lineas.append(actual)
        if len(lineas) <= 7:
            break

    alto_linea = fuente.getbbox("Ag")[3] - fuente.getbbox("Ag")[1] + 12
    alto_total = len(lineas) * alto_linea
    y = max(48, (alto_pantalla - alto_total) // 2 + 8)

    for linea in lineas:
        caja = dibujo.textbbox((0, 0), linea, font=fuente)
        ancho_linea = caja[2] - caja[0]
        x = (ancho_pantalla - ancho_linea) // 2 - caja[0]
        dibujo.text((x, y), linea, font=fuente, fill=(245, 248, 250))
        y += alto_linea

    _enviar_imagen(imagen)


def mostrar_qr(ruta_png):
    """Presenta el QR en el LCD, conservando el PNG como respaldo."""
    print(f"[display] QR disponible en: {ruta_png}")
    if not _PIL_OK:
        print("[display] Pillow no está disponible; no se puede dibujar el QR.")
        return

    try:
        qr = Image.open(ruta_png).convert("RGB")
        # Composición horizontal 480x320: QR a la izquierda y textos a la derecha.
        # El margen blanco alrededor del QR ayuda a que la cámara lo detecte.
        qr.thumbnail((248, 248), Image.Resampling.NEAREST)
        imagen = Image.new("RGB", (480, 320), "white")
        dibujo = ImageDraw.Draw(imagen)
        titulo = _fuente(24)
        subtitulo = _fuente(18)
        x = 18 + (248 - qr.width) // 2
        y = 36 + (248 - qr.height) // 2
        imagen.paste(qr, (x, y))
        dibujo.text((282, 72), "Deposito", font=titulo, fill="black")
        dibujo.text((282, 104), "confirmado", font=titulo, fill="black")
        dibujo.text((282, 166), "Escanea el", font=subtitulo, fill="black")
        dibujo.text((282, 191), "codigo QR", font=subtitulo, fill="black")
        dibujo.text((282, 244), "Gracias por", font=subtitulo, fill="black")
        dibujo.text((282, 268), "reciclar", font=subtitulo, fill="black")
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
