"""
qr.py
=====
Generación REAL del código QR cuando se confirma un depósito.

Por ahora el contenido es de prueba (config.QR_CONTENIDO = "TEST-RECICLAJE").
Más adelante acá irá la info de puntos del usuario, pero ESO NO se implementa
todavía (secciones 12 y 24 del brief).

Usa la librería 'qrcode' (que a su vez usa Pillow para generar la imagen).
El QR se guarda como PNG. Mostrarlo es responsabilidad de display.py, no de
este módulo: acá solo lo generamos y guardamos.
"""

try:
    import qrcode
except ImportError:
    print("[qr] ERROR: falta la librería qrcode.")
    print("     Instalá con: pip install qrcode[pil]")
    raise

import config


def generar_qr(contenido=None, ruta=None):
    """
    Genera un QR y lo guarda como PNG.

    Parámetros:
        contenido: texto que codifica el QR. Si es None, usa config.
        ruta:      dónde guardar el PNG. Si es None, usa config.

    Devuelve:
        La ruta del PNG generado (para que display.py lo pueda mostrar).

    Lanza excepción si algo falla, para que el controlador se entere
    (manejo de errores, sección 17).
    """
    contenido = contenido if contenido is not None else config.QR_CONTENIDO
    ruta = ruta if ruta is not None else config.QR_OUTPUT_PATH

    print(f"[qr] Generando QR con contenido: '{contenido}'")

    # Configuración básica del QR. box_size = tamaño de cada "cuadradito",
    # border = margen en cuadraditos (4 es el mínimo recomendado).
    qr = qrcode.QRCode(
        version=None,               # se ajusta solo al contenido
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(contenido)
    qr.make(fit=True)

    imagen = qr.make_image(fill_color="black", back_color="white")
    imagen.save(ruta)

    print(f"[qr] QR guardado en: {ruta}")
    return ruta
