"""
controller.py
=============
El CEREBRO del tacho. Coordina cámara, detector, servos, sensor, QR y
display mediante una MÁQUINA DE ESTADOS.

Por qué máquina de estados (sección 10 del brief):
  El IMX500 puede detectar la misma botella en 30 frames seguidos. Sin una
  máquina de estados, abriríamos el servo 30 veces y generaríamos 30 QR. La
  máquina garantiza que cada objeto se procese UNA sola vez: solo aceptamos
  detecciones nuevas cuando volvemos al estado ESPERANDO_OBJETO.

Estados y transiciones:
  ESPERANDO_OBJETO  --detección válida estable-->  OBJETO_DETECTADO
  OBJETO_DETECTADO  --(abre compuerta)---------->  ESPERANDO_DEPOSITO
  ESPERANDO_DEPOSITO--HC-SR04 confirma---------->  OBJETO_DEPOSITADO
  ESPERANDO_DEPOSITO--timeout-------------------->  CERRANDO_COMPUERTA
  OBJETO_DEPOSITADO --(genera QR)--------------->  MOSTRAR_QR
  MOSTRAR_QR        --(muestra QR)-------------->  CERRANDO_COMPUERTA
  CERRANDO_COMPUERTA--(cierra compuerta)-------->  ESPERANDO_OBJETO

Diseño limpio: este archivo NO habla con GPIO ni con Picamera2 directo.
Habla con los módulos (servo, distance_sensor, qr, display). Cada uno
encapsula su hardware.
"""

import time
from enum import Enum, auto

import config


class Estado(Enum):
    ESPERANDO_OBJETO = auto()
    OBJETO_DETECTADO = auto()
    ESPERANDO_DEPOSITO = auto()
    OBJETO_DEPOSITADO = auto()
    MOSTRAR_QR = auto()
    CERRANDO_COMPUERTA = auto()


class Controller:
    """
    Recibe ya construidos los módulos que necesita (inyección de
    dependencias). Así es fácil de leer y de testear.
    """

    def __init__(self, camera, detector, servos, sensor, display, qr_module):
        self.camera = camera
        self.detector = detector
        self.servos = servos
        self.sensor = sensor
        self.display = display
        self.qr = qr_module

        self.estado = Estado.ESPERANDO_OBJETO

        # Datos del objeto que estamos procesando en este ciclo.
        self.tipo_objeto_actual = None      # "botella" / "lata"
        self.nombre_clase_actual = None     # "bottle", "Coca-Cola"...

        # Filtrado temporal: contamos frames consecutivos con detección
        # válida para evitar falsos positivos (sección 11).
        self._frames_validos_seguidos = 0

        # Marca de tiempo para el timeout de espera de depósito.
        self._t_inicio_espera_deposito = None

    # ----------------------------------------------------------------------
    # BUCLE PRINCIPAL
    # ----------------------------------------------------------------------
    def procesar_frame(self):
        """
        Se llama una vez por frame desde main.py. Según el estado actual,
        hace lo que corresponde. Devolver nada; el estado se guarda en self.
        """
        # Capturamos metadata del sensor (contiene la inferencia ya hecha).
        metadata = self.camera.capturar_metadata()

        # SOLO nos interesa mirar detecciones cuando estamos esperando un
        # objeto. En el resto de los estados IGNORAMOS detecciones nuevas
        # (sección 16), justamente para no reprocesar la misma botella.
        if self.estado == Estado.ESPERANDO_OBJETO:
            self._estado_esperando_objeto(metadata)

        elif self.estado == Estado.OBJETO_DETECTADO:
            self._estado_objeto_detectado()

        elif self.estado == Estado.ESPERANDO_DEPOSITO:
            self._estado_esperando_deposito()

        elif self.estado == Estado.OBJETO_DEPOSITADO:
            self._estado_objeto_depositado()

        elif self.estado == Estado.MOSTRAR_QR:
            self._estado_mostrar_qr()

        elif self.estado == Estado.CERRANDO_COMPUERTA:
            self._estado_cerrando_compuerta()

    # ----------------------------------------------------------------------
    # ESTADO: ESPERANDO_OBJETO
    # ----------------------------------------------------------------------
    def _estado_esperando_objeto(self, metadata):
        """Miramos las detecciones. Si una clase válida aparece de forma
        estable durante varios frames, pasamos a OBJETO_DETECTADO."""
        detecciones = self.detector.detectar(metadata)
        objeto = self.detector.primer_objeto_valido(detecciones)

        if objeto is None:
            # No hay objeto válido este frame: reseteamos el contador.
            self._frames_validos_seguidos = 0
            return

        # Hay objeto válido. Sumamos al contador de estabilidad.
        self._frames_validos_seguidos += 1

        if self._frames_validos_seguidos >= config.FRAMES_CONSECUTIVOS_REQUERIDOS:
            # Detección estable confirmada -> guardamos y avanzamos.
            self.nombre_clase_actual = objeto.nombre
            self.tipo_objeto_actual = config.OBJETO_A_COMPUERTA.get(objeto.nombre)
            self._frames_validos_seguidos = 0

            self.display.mostrar_mensaje(
                f"Objeto detectado: {objeto.nombre} "
                f"(conf {objeto.confianza:.2f})"
            )
            self._cambiar_estado(Estado.OBJETO_DETECTADO)

    # ----------------------------------------------------------------------
    # ESTADO: OBJETO_DETECTADO
    # ----------------------------------------------------------------------
    def _estado_objeto_detectado(self):
        """Abrimos la compuerta correspondiente y pasamos a esperar el
        depósito."""
        self.display.mostrar_mensaje("Abriendo compuerta...")
        self.servos.abrir_compuerta(self.tipo_objeto_actual)

        # Avisamos al sensor que empieza la ventana de espera del depósito.
        # (En modo simulación, esto arranca el temporizador que confirmará
        # el depósito solo. En modo real es inofensivo.)
        self.sensor.iniciar_espera()

        # Arrancamos el reloj del timeout de depósito.
        self._t_inicio_espera_deposito = time.time()
        self.display.mostrar_mensaje("Depositá el objeto, por favor.")
        self._cambiar_estado(Estado.ESPERANDO_DEPOSITO)

    # ----------------------------------------------------------------------
    # ESTADO: ESPERANDO_DEPOSITO
    # ----------------------------------------------------------------------
    def _estado_esperando_deposito(self):
        """Leemos el HC-SR04. Si confirma depósito, avanzamos. Si pasa
        demasiado tiempo, cerramos por timeout (no dejamos el tacho
        trabado)."""
        if self.sensor.objeto_depositado():
            self.display.mostrar_mensaje("Depósito confirmado.")
            self._cambiar_estado(Estado.OBJETO_DEPOSITADO)
            return

        # Chequeo de timeout.
        transcurrido = time.time() - self._t_inicio_espera_deposito
        if transcurrido >= config.TIMEOUT_ESPERANDO_DEPOSITO:
            self.display.mostrar_mensaje(
                "No se depositó nada a tiempo. Cerrando compuerta."
            )
            self._cambiar_estado(Estado.CERRANDO_COMPUERTA)

    # ----------------------------------------------------------------------
    # ESTADO: OBJETO_DEPOSITADO
    # ----------------------------------------------------------------------
    def _estado_objeto_depositado(self):
        """Depósito confirmado -> generamos el QR."""
        self.display.mostrar_mensaje("Generando código QR...")
        try:
            ruta = self.qr.generar_qr()
            self._ruta_qr_actual = ruta
            self._cambiar_estado(Estado.MOSTRAR_QR)
        except Exception as e:
            # Si el QR falla, no dejamos el sistema colgado: avisamos y
            # cerramos igual.
            self.display.mostrar_mensaje(f"ERROR generando QR: {e}")
            self._cambiar_estado(Estado.CERRANDO_COMPUERTA)

    # ----------------------------------------------------------------------
    # ESTADO: MOSTRAR_QR
    # ----------------------------------------------------------------------
    def _estado_mostrar_qr(self):
        """Mostramos/guardamos el QR y pasamos a cerrar."""
        self.display.mostrar_qr(self._ruta_qr_actual)
        self._cambiar_estado(Estado.CERRANDO_COMPUERTA)

    # ----------------------------------------------------------------------
    # ESTADO: CERRANDO_COMPUERTA
    # ----------------------------------------------------------------------
    def _estado_cerrando_compuerta(self):
        """Cerramos la compuerta y volvemos al inicio del ciclo."""
        self.display.mostrar_mensaje("Cerrando compuerta.")
        self.servos.cerrar_compuerta(self.tipo_objeto_actual)

        # Limpiamos el estado del objeto procesado.
        self.tipo_objeto_actual = None
        self.nombre_clase_actual = None

        self.display.mostrar_mensaje("Listo. Esperando otro objeto.\n")
        self._cambiar_estado(Estado.ESPERANDO_OBJETO)

    # ----------------------------------------------------------------------
    # Utilidad
    # ----------------------------------------------------------------------
    def _cambiar_estado(self, nuevo):
        """Centraliza el cambio de estado (útil para depurar: acá podrías
        loguear todas las transiciones)."""
        self.estado = nuevo
