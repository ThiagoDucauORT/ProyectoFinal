"""
detector.py
===========
Toma las salidas CRUDAS de la red (que vienen del sensor IMX500 vía
camera.py) y las convierte en una lista de detecciones limpias y usables:

    class_id, nombre_de_clase, confianza, bounding_box

Además aplica el umbral de confianza: descarta todo lo que esté por debajo
de config.CONFIDENCE_THRESHOLD.

División de trabajo:
  - camera.py    -> habla con el hardware, entrega tensores crudos.
  - detector.py  -> interpreta esos tensores (esto corre en CPU, es liviano).
  - controller.py-> decide qué hacer con las detecciones.

Este archivo NO sabe nada de servos, sensores ni QR. Solo detecciones.
"""

import numpy as np

import config


class Deteccion:
    """Una detección individual ya interpretada y validada."""

    def __init__(self, class_id, nombre, confianza, bbox):
        self.class_id = class_id      # int, índice de clase del modelo
        self.nombre = nombre          # str, nombre legible ("bottle", "Coca-Cola"...)
        self.confianza = confianza    # float 0..1
        self.bbox = bbox              # caja (formato del helper del IMX500)

    def __repr__(self):
        return f"<Deteccion {self.nombre} conf={self.confianza:.2f}>"


class Detector:
    """
    Interpreta las salidas del IMX500 usando la info de la cámara.

    Necesita referencias a:
      - camera: para get_outputs / get_input_size / convertir_bbox.
      - labels: lista de nombres de clase (cargada desde config.LABELS_PATH).
    """

    def __init__(self, camera):
        self.camera = camera
        self.labels = self._cargar_labels()

    def _cargar_labels(self):
        """
        Carga los nombres de clase desde el archivo de labels.
        NO inventamos nombres: salen del archivo que corresponde al modelo.
        """
        try:
            with open(config.LABELS_PATH, "r") as f:
                labels = [ln.strip() for ln in f.readlines() if ln.strip()]
            print(f"[detector] {len(labels)} labels cargadas desde {config.LABELS_PATH}")
            return labels
        except FileNotFoundError:
            print(f"[detector] ERROR: no se encontró el archivo de labels "
                  f"{config.LABELS_PATH}")
            raise

    def nombre_de_clase(self, class_id):
        """Traduce un class_id a su nombre. Si el id se sale del rango,
        devolvemos un placeholder para no romper."""
        if 0 <= class_id < len(self.labels):
            return self.labels[class_id]
        return f"clase_{class_id}"

    def detectar(self, metadata):
        """
        Recibe los metadatos de un frame (de camera.capturar_metadata()) y
        devuelve una lista de objetos Deteccion que superan el umbral.

        El post-procesado exacto depende del modelo. Para los modelos de
        detección "_pp" (post-processed) del zoo oficial —como el SSD
        MobileNet que usamos en la opción A— el sensor ya devuelve las
        salidas separadas en cajas, scores y clases. Eso es lo que
        interpretamos acá.
        """
        outputs = self.camera.get_outputs(metadata)
        if outputs is None:
            # Todavía no hay salida lista en este frame. Normal al arrancar.
            return []

        # Los modelos "_pp" devuelven 3 tensores: cajas, scores, clases.
        # (boxes, scores, classes)
        try:
            boxes = outputs[0][0]     # (N, 4)
            scores = outputs[1][0]    # (N,)
            classes = outputs[2][0]   # (N,)
        except (IndexError, TypeError):
            # Si el modelo devuelve otro formato, avisamos claramente en vez
            # de fallar en silencio.
            print("[detector] ADVERTENCIA: formato de salida inesperado. "
                  "¿El .rpk es un modelo de detección post-procesado (_pp)?")
            return []

        detecciones = []
        for box, score, cls in zip(boxes, scores, classes):
            score = float(score)
            if score < config.CONFIDENCE_THRESHOLD:
                continue  # ignoramos por debajo del umbral

            class_id = int(cls)
            nombre = self.nombre_de_clase(class_id)

            # Convertimos la caja a coordenadas de imagen real.
            bbox = self.camera.convertir_bbox(box, metadata)

            detecciones.append(Deteccion(class_id, nombre, score, bbox))

        # Actualizamos el preview: le pasamos a la cámara SOLO las cajas de
        # los objetos que el tacho acepta (config.OBJETOS_VALIDOS), con su
        # nombre y confianza, para que las dibuje sobre el video.
        self._actualizar_preview(detecciones)

        return detecciones

    def _actualizar_preview(self, detecciones):
        """
        Arma la lista de cajas a dibujar (solo objetos aceptados) y se la
        pasa a la cámara. La bbox del IMX500 viene como (x, y, w, h).
        """
        cajas = []
        for d in detecciones:
            if d.nombre not in config.OBJETOS_VALIDOS:
                continue  # solo dibujamos lo que el tacho acepta
            try:
                x, y, w, h = d.bbox
                texto = f"{d.nombre} {d.confianza:.2f}"
                cajas.append((int(x), int(y), int(w), int(h), texto))
            except (ValueError, TypeError):
                # Si el formato de la caja no es el esperado, la salteamos
                # sin romper el preview.
                continue
        self.camera.set_cajas(cajas)

    def primer_objeto_valido(self, detecciones):
        """
        De una lista de detecciones, devuelve la PRIMERA que sea un objeto
        que el tacho acepta (según config.OBJETOS_VALIDOS), o None.

        El controlador espera 1 objeto por vez, así que con la primera
        válida alcanza.
        """
        for d in detecciones:
            if d.nombre in config.OBJETOS_VALIDOS:
                return d
        return None
