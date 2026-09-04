"""
camera.py
=========
Responsable de TODO lo que tiene que ver con la Raspberry Pi AI Camera:
inicializar el sensor IMX500, cargar el modelo (.rpk), arrancar Picamera2
y entregar las salidas CRUDAS de la red neuronal.

Punto clave del proyecto (sección 23 del brief):
------------------------------------------------
La inferencia NO corre en la CPU de la Raspberry. Corre DENTRO del sensor
IMX500. Nosotros:
  1. Subimos el modelo .rpk al sensor (una sola vez, al arrancar).
  2. En cada frame, el sensor ya nos devuelve los TENSORES de salida de la
     red junto con los metadatos del frame.
  3. La CPU de la Pi solo hace el post-procesado liviano (interpretar esos
     tensores). NO hace la parte pesada (la convolución de la red).

Por eso este módulo entrega "outputs crudos" y es detector.py el que los
interpreta. Así separamos: captura (acá) vs. interpretación (detector.py).

Qué corre dónde:
  - IMX500 (sensor):  captura de imagen + TODA la inferencia de la red.
  - Raspberry Pi CPU: interpretar tensores, filtrar por umbral, lógica.
"""

import sys

# Estas importaciones vienen del paquete del sistema python3-picamera2.
# En SSH sin la cámara conectada fallarían; por eso las envolvemos para dar
# un mensaje de error claro (manejo de errores, sección 17).
try:
    from picamera2 import Picamera2, Preview, MappedArray
    from picamera2.devices import IMX500
    from picamera2.devices.imx500 import NetworkIntrinsics
except ImportError as e:
    print("[camera] ERROR: no se pudo importar picamera2 / IMX500.")
    print("         Instalá con: sudo apt install -y python3-picamera2 imx500-all")
    raise

# OpenCV lo usamos para dibujar las cajas sobre el frame del preview.
# Es opcional: si no está, el preview igual se ve, solo sin cajas dibujadas.
try:
    import cv2
    _CV2_OK = True
except ImportError:
    _CV2_OK = False

import config


class Camera:
    """
    Envuelve el sensor IMX500 + Picamera2.

    Uso:
        cam = Camera()
        cam.iniciar()
        metadata = cam.capturar_metadata()   # en un loop
        ...
        cam.detener()
    """

    def __init__(self):
        self.imx500 = None
        self.intrinsics = None
        self.picam2 = None
        self._iniciada = False
        # Cajas a dibujar en el preview. El controller/detector las va
        # actualizando; el callback de dibujo las lee. Cada elemento es una
        # tupla (x, y, w, h, texto).
        self._cajas_a_dibujar = []

    def iniciar(self):
        """
        Inicializa el sensor y arranca la cámara.

        ORDEN IMPORTANTE: el objeto IMX500 DEBE crearse ANTES de instanciar
        Picamera2, porque es el que sube el firmware del modelo al sensor y
        nos dice qué número de cámara es la IMX500.
        """
        # --- 1. Cargar el modelo en el sensor -----------------------------
        # Esto sube el .rpk al IMX500. Es lo que hace que la inferencia
        # ocurra en el sensor y no en la CPU. Se hace UNA sola vez.
        print(f"[camera] Cargando modelo en IMX500: {config.MODEL_RPK_PATH}")
        self.imx500 = IMX500(config.MODEL_RPK_PATH)

        # --- 2. Intrinsics: metadatos de la red --------------------------
        # NetworkIntrinsics describe la red (tarea, labels, frame rate
        # recomendado, si preserva aspect ratio, etc.). Si el .rpk no los
        # trae embebidos, los completamos con defaults razonables.
        self.intrinsics = self.imx500.network_intrinsics
        if not self.intrinsics:
            self.intrinsics = NetworkIntrinsics()
            self.intrinsics.task = "object detection"
        elif self.intrinsics.task != "object detection":
            print("[camera] ERROR: el modelo no es de detección de objetos.")
            sys.exit(1)
        self.intrinsics.update_with_defaults()

        # --- 3. Instanciar Picamera2 sobre la cámara correcta ------------
        # imx500.camera_num nos dice cuál de las cámaras es la IMX500.
        self.picam2 = Picamera2(self.imx500.camera_num)

        # Configuración de PREVIEW. Para un tacho no necesitamos alta
        # resolución ni grabar video: el trabajo pesado lo hace el sensor.
        # buffer_count=12 es el valor que usan los ejemplos oficiales y da
        # margen para no perder frames. FrameRate sale del intrinsics para
        # que coincida con la tasa de inferencia real del modelo.
        config_cam = self.picam2.create_preview_configuration(
            controls={"FrameRate": self.intrinsics.inference_rate},
            buffer_count=12,
        )

        # Aplicamos la configuración a la cámara. En los ejemplos oficiales
        # de la AI Camera se hace configure() explícito ANTES de arrancar.
        self.picam2.configure(config_cam)
        self.imx500.show_network_fw_progress_bar()

        # --- 4. Preview (ventana con el video en vivo) --------------------
        # Si config.MOSTRAR_PREVIEW está activo, abrimos una ventana con el
        # video. Necesita pantalla conectada.
        #   QTGL = preview acelerado por GPU (escritorio con OpenGL).
        #   QT   = preview Qt por software (fallback si QTGL falla).
        #   DRM  = dibuja directo sobre el framebuffer/HDMI, SIN Qt/X11.
        #          Es la mejor opción si Qt da error de plugin "xcb".
        # IMPORTANTE: start_preview() va ANTES de start(), como en la doc.
        if config.MOSTRAR_PREVIEW:
            # Armamos el orden de intentos. Si config.PREVIEW_MODO fuerza
            # uno concreto ("QTGL"/"QT"/"DRM"), ese va primero.
            orden = {
                "QTGL": [Preview.QTGL, Preview.DRM, Preview.QT],
                "QT":   [Preview.QT, Preview.DRM, Preview.QTGL],
                "DRM":  [Preview.DRM, Preview.QTGL, Preview.QT],
            }.get(getattr(config, "PREVIEW_MODO", "QTGL"),
                  [Preview.QTGL, Preview.DRM, Preview.QT])

            abierto = False
            for modo in orden:
                try:
                    self.picam2.start_preview(modo)
                    print(f"[camera] Preview abierto con modo {modo}.")
                    abierto = True
                    break
                except Exception as e:
                    print(f"[camera] Preview {modo} no disponible ({e}). Probando otro...")
                    continue
            if not abierto:
                print("[camera] AVISO: no se pudo abrir ningún preview. "
                      "Sigo sin ventana (poné MOSTRAR_PREVIEW=False para ocultarlo).")

            # Registramos el callback que dibuja las cajas sobre cada frame.
            # pre_callback se ejecuta sobre el frame ANTES de mostrarlo.
            self.picam2.pre_callback = self._dibujar_cajas

        # --- 5. Arrancar ---------------------------------------------------
        self.picam2.start()

        # Si el modelo espera imágenes con relación de aspecto preservada,
        # se lo indicamos al sensor.
        if self.intrinsics.preserve_aspect_ratio:
            self.imx500.set_auto_aspect_ratio()

        self._iniciada = True
        print("[camera] Cámara IMX500 iniciada correctamente.")

    def capturar_metadata(self):
        """
        Devuelve los metadatos del último frame. Estos metadatos contienen
        las salidas de la red (los tensores). No es una foto: es el
        resultado de la inferencia hecha en el sensor.

        detector.py se encarga de convertir esto en detecciones.
        """
        if not self._iniciada:
            raise RuntimeError("[camera] La cámara no fue iniciada.")
        return self.picam2.capture_metadata()

    def get_outputs(self, metadata):
        """
        Extrae los tensores de salida de la red desde los metadatos.
        Puede devolver None si en ese frame todavía no hay salida lista.
        """
        return self.imx500.get_outputs(metadata, add_batch=True)

    def get_input_size(self):
        """Tamaño de entrada de la red (ancho, alto). Lo usa el detector
        para reescalar las bounding boxes al tamaño real."""
        return self.imx500.get_input_size()

    def convertir_bbox(self, bbox, metadata):
        """
        Convierte una caja en coordenadas de la red a coordenadas de la
        imagen de salida. Delega en el helper del propio IMX500 para no
        reimplementar la matemática de escalado/aspect ratio.
        """
        return self.imx500.convert_inference_coords(bbox, metadata, self.picam2)

    def set_cajas(self, cajas):
        """
        Actualiza la lista de cajas que el preview va a dibujar.
        Cada caja es (x, y, w, h, texto). La llama el detector en cada frame
        con SOLO los objetos que el tacho acepta (según config).
        """
        self._cajas_a_dibujar = cajas

    def _dibujar_cajas(self, request):
        """
        Callback de preview: se ejecuta sobre cada frame antes de mostrarlo.
        Dibuja las cajas guardadas en self._cajas_a_dibujar directamente
        sobre la imagen del preview usando OpenCV.

        No hace inferencia acá: solo pinta lo que el detector ya calculó.
        """
        if not _CV2_OK or not self._cajas_a_dibujar:
            return

        # MappedArray nos da acceso al buffer del frame para dibujar encima.
        with MappedArray(request, "main") as m:
            for (x, y, w, h, texto) in self._cajas_a_dibujar:
                # Rectángulo verde alrededor del objeto.
                cv2.rectangle(m.array, (x, y), (x + w, y + h),
                              (0, 255, 0), 2)
                # Fondo oscuro para que el texto se lea sobre cualquier color.
                cv2.rectangle(m.array, (x, y - 20), (x + len(texto) * 10, y),
                              (0, 0, 0), -1)
                # Nombre + confianza arriba de la caja.
                cv2.putText(m.array, texto, (x + 2, y - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

    def detener(self):
        """Apaga la cámara de forma ordenada."""
        if self.picam2 is not None:
            self.picam2.stop()
        self._iniciada = False
        print("[camera] Cámara detenida.")
