"""Protocolo UART V1, sin GPIO en la Raspberry. Líneas ASCII terminadas en LF."""
import time
import uuid
import config


class ErrorESP32(RuntimeError):
    pass


TERMINALES = {"DEPOSIT_POSSIBLE", "TIMEOUT_PRESENT", "TIMEOUT_CLEAR",
              "ERROR_SENSOR", "LINK_TIMEOUT", "CANCELLED", "ERROR_BUSY"}
EVENTOS = TERMINALES | {"WAIT_PRESENT", "OPEN", "WAIT_CLEAR", "CLOSED"}


class ClienteESP32:
    def __init__(self, puerto=None, reloj=None):
        self._reloj = reloj or time.monotonic
        self._buffer = bytearray()
        self._descartando = False
        self._id = None
        self._abierta = False
        self._cerrada = False
        self._ultimo_ping = 0
        self._ultima_respuesta = self._reloj()
        self._inicio = 0
        if puerto is None:
            try:
                import serial
                puerto = serial.Serial(config.ESP32_PUERTO, config.ESP32_BAUDRATE,
                                       timeout=0, write_timeout=0.5)
            except (ImportError, OSError) as error:
                raise ErrorESP32(f"No se pudo abrir Serial: {error}") from error
        self._puerto = puerto
        try:
            self._sincronizar()
        except BaseException:
            self._puerto.close()
            raise

    def _enviar(self, linea):
        datos = (linea + "\n").encode("ascii")
        try:
            if self._puerto.write(datos) != len(datos):
                raise ErrorESP32("Escritura Serial incompleta.")
        except OSError as error:
            raise ErrorESP32(f"Fallo de escritura Serial: {error}") from error

    def _lineas(self):
        try:
            datos = self._puerto.read(min(self._puerto.in_waiting, 1024))
        except OSError as error:
            raise ErrorESP32(f"Fallo de lectura Serial: {error}") from error
        lineas = []
        for byte in datos:
            if byte == 10:
                if not self._descartando:
                    lineas.append(self._buffer.decode("ascii", errors="replace").strip())
                self._buffer.clear()
                self._descartando = False
            elif not self._descartando:
                self._buffer.append(byte)
                if len(self._buffer) > 120:
                    self._buffer.clear()
                    self._descartando = True
        return lineas

    def _sincronizar(self):
        # HELLO cierra cualquier ciclo anterior; READY espera el movimiento.
        token = uuid.uuid4().hex
        limite = self._reloj() + config.ESP32_TIMEOUT_INICIO
        proximo = 0
        while self._reloj() < limite:
            if self._reloj() >= proximo:
                self._enviar(f"HELLO:{token}")
                proximo = self._reloj() + 1.0
            if f"READY:{token}:V1" in self._lineas():
                return
            time.sleep(0.01)
        raise ErrorESP32("No llegó READY V1; revisá firmware, puerto y cableado.")

    def autorizar_deposito(self, tipo):
        if tipo != "botella" or self._id is not None:
            raise ErrorESP32("Autorización inválida o ciclo ya activo.")
        self._id = uuid.uuid4().hex
        self._abierta = self._cerrada = False
        self._inicio = self._ultima_respuesta = self._ultimo_ping = self._reloj()
        # No reintentar AUTH: evita abrir dos veces por una respuesta perdida.
        self._enviar(f"AUTH:{self._id}:BOTELLA")

    def actualizar(self):
        ahora = self._reloj()
        if self._id is not None and ahora - self._ultimo_ping >= config.ESP32_INTERVALO_PING:
            self._enviar(f"PING:{self._id}")
            self._ultimo_ping = ahora
        eventos = []
        for linea in self._lineas():
            partes = linea.split(":")
            if self._id is None or len(partes) < 2 or partes[1] != self._id:
                continue
            if len(partes) == 2 and partes[0] == "PONG":
                self._ultima_respuesta = ahora
            elif len(partes) == 3 and partes[0] == "EV" and partes[2] in EVENTOS:
                evento = partes[2]
                self._ultima_respuesta = ahora
                if evento == "OPEN":
                    self._abierta = True
                    self._cerrada = False
                elif evento == "CLOSED":
                    self._cerrada = True
                elif evento == "DEPOSIT_POSSIBLE" and not (self._abierta and self._cerrada):
                    raise ErrorESP32("Resultado sin apertura y cierre previos; no se genera QR.")
                eventos.append(evento)
                if evento in TERMINALES:
                    self._id = None
        if self._id is not None:
            if ahora - self._ultima_respuesta >= config.ESP32_TIMEOUT_RESPUESTA:
                self.cancelar()
                raise ErrorESP32("El ESP32 dejó de responder; no se genera QR.")
            if ahora - self._inicio >= config.ESP32_TIMEOUT_CICLO:
                self.cancelar()
                raise ErrorESP32("Se superó el tiempo máximo del ciclo; no se genera QR.")
        return eventos

    def cancelar(self):
        if self._id is not None:
            self._enviar(f"CANCEL:{self._id}")
            self._id = None

    def liberar(self):
        try:
            self.cancelar()
        finally:
            self._puerto.close()


class ESP32Simulado:
    """Ensayo automático de presencia, apertura, ausencia y cierre, sin hardware."""
    def __init__(self, reloj=None):
        self._reloj = reloj or time.monotonic
        self._pendientes = []

    def autorizar_deposito(self, tipo):
        if tipo != "botella" or self._pendientes:
            raise ErrorESP32("Autorización simulada inválida.")
        ahora = self._reloj()
        self._pendientes = [(ahora, "WAIT_PRESENT"), (ahora + 1, "OPEN"),
                            (ahora + 1.6, "WAIT_CLEAR"), (ahora + 3.6, "CLOSED"),
                            (ahora + 3.6, "DEPOSIT_POSSIBLE")]

    def actualizar(self):
        eventos = []
        while self._pendientes and self._pendientes[0][0] <= self._reloj():
            eventos.append(self._pendientes.pop(0)[1])
        return eventos

    def cancelar(self):
        self._pendientes.clear()

    def liberar(self):
        self.cancelar()
