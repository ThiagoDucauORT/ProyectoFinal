"""
Coordina reconocimiento y QR. El ESP32 controla la secuencia física:
autorización -> presencia estable -> abrir -> ausencia estable -> cerrar.
La cámara NO comprueba desaparición. La ausencia indica un POSIBLE depósito.
"""
import time
from enum import Enum, auto
import config
from esp32 import ErrorESP32


class Estado(Enum):
    ESPERANDO_OBJETO = auto()
    OBJETO_DETECTADO = auto()
    ESPERANDO_DEPOSITO = auto()
    OBJETO_DEPOSITADO = auto()
    MOSTRAR_QR = auto()
    PAUSA = auto()


class Controller:
    def __init__(self, camera, detector, esp32, display, qr_module, reloj=None):
        self.camera = camera
        self.detector = detector
        self.esp32 = esp32
        self.display = display
        self.qr = qr_module
        self._reloj = reloj or time.monotonic
        self.estado = Estado.ESPERANDO_OBJETO
        self.tipo_objeto_actual = None
        self.nombre_clase_actual = None
        self._frames_validos_seguidos = 0
        self._clase_candidata = None
        self._fin_pausa = 0

    def procesar_frame(self):
        # Primero Serial; si la cámara bloquea la Pi, el ESP32 limita los tiempos.
        eventos = self.esp32.actualizar()
        if self.estado == Estado.ESPERANDO_OBJETO:
            self._estado_esperando_objeto(self.camera.capturar_metadata())
        elif self.estado == Estado.OBJETO_DETECTADO:
            self.esp32.autorizar_deposito(self.tipo_objeto_actual)
            self.display.mostrar_mensaje("Acercá la botella a la entrada.")
            self.estado = Estado.ESPERANDO_DEPOSITO
        elif self.estado == Estado.ESPERANDO_DEPOSITO:
            self._estado_esperando_deposito(eventos)
        elif self.estado == Estado.OBJETO_DEPOSITADO:
            try:
                self._ruta_qr_actual = self.qr.generar_qr()
                self.estado = Estado.MOSTRAR_QR
            except Exception as error:
                self.display.mostrar_mensaje(f"ERROR generando QR: {error}")
                self._terminar_ciclo()
        elif self.estado == Estado.MOSTRAR_QR:
            self.display.mostrar_qr(self._ruta_qr_actual)
            self._terminar_ciclo()
        elif self.estado == Estado.PAUSA and self._reloj() >= self._fin_pausa:
            self.display.mostrar_mensaje("Listo. Esperando otro objeto.")
            self.estado = Estado.ESPERANDO_OBJETO

    def _estado_esperando_objeto(self, metadata):
        objeto = self.detector.primer_objeto_valido(self.detector.detectar(metadata))
        if objeto is None:
            self._frames_validos_seguidos = 0
            self._clase_candidata = None
            return
        if objeto.nombre != self._clase_candidata:
            self._clase_candidata = objeto.nombre
            self._frames_validos_seguidos = 0
        self._frames_validos_seguidos += 1
        if self._frames_validos_seguidos >= config.FRAMES_CONSECUTIVOS_REQUERIDOS:
            self.tipo_objeto_actual = config.OBJETO_A_COMPUERTA.get(objeto.nombre)
            if self.tipo_objeto_actual != "botella":
                self.display.mostrar_mensaje("Esta compuerta no está implementada en el ESP32.")
                self._terminar_ciclo()
                return
            self.nombre_clase_actual = objeto.nombre
            self.display.mostrar_mensaje(f"Botella reconocida (conf {objeto.confianza:.2f}).")
            self.estado = Estado.OBJETO_DETECTADO

    def _estado_esperando_deposito(self, eventos):
        mensajes = {
            "WAIT_PRESENT": "Esperando presencia física en la entrada.",
            "OPEN": "Presencia detectada. Abriendo compuerta.",
            "WAIT_CLEAR": "Depositá la botella.",
            "CLOSED": "Orden de cierre terminada.",
        }
        for evento in eventos:
            if evento in mensajes:
                self.display.mostrar_mensaje(mensajes[evento])
            elif evento == "DEPOSIT_POSSIBLE":
                self.display.mostrar_mensaje("Posible depósito detectado; compuerta cerrada.")
                self.estado = Estado.OBJETO_DEPOSITADO
            elif evento in {"TIMEOUT_PRESENT", "TIMEOUT_CLEAR", "ERROR_SENSOR",
                            "LINK_TIMEOUT", "CANCELLED"}:
                self.display.mostrar_mensaje(f"Ciclo cancelado: {evento}. No se genera QR.")
                self._terminar_ciclo()
            elif evento == "ERROR_BUSY":
                raise ErrorESP32("El ESP32 está ocupado; reiniciá el programa.")

    def _terminar_ciclo(self):
        self.tipo_objeto_actual = None
        self.nombre_clase_actual = None
        self._clase_candidata = None
        self._frames_validos_seguidos = 0
        # Pausa por tiempo, sin exigir desaparición en frames de cámara.
        self._fin_pausa = self._reloj() + config.PAUSA_ENTRE_CICLOS
        self.estado = Estado.PAUSA
