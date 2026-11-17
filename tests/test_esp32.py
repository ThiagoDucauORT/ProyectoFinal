"""Pruebas sin Raspberry, ESP32, cámara ni librerías GPIO."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tacho_reciclaje"))
import config
from esp32 import ClienteESP32, ErrorESP32, ESP32Simulado
from controller import Controller, Estado


class Reloj:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


class Puerto:
    def __init__(self):
        self.rx = bytearray()
        self.tx = []
        self.cerrado = False

    @property
    def in_waiting(self):
        return len(self.rx)

    def write(self, datos):
        self.tx.append(datos.decode().strip())
        if datos.startswith(b"HELLO:"):
            token = datos.decode().strip().split(":")[1]
            self.agregar(f"READY:{token}:V1\n")
        return len(datos)

    def read(self, cantidad):
        datos = bytes(self.rx[:cantidad])
        del self.rx[:cantidad]
        return datos

    def agregar(self, texto):
        self.rx.extend(texto.encode())

    def close(self):
        self.cerrado = True


class TestSerial(unittest.TestCase):
    def setUp(self):
        self.puerto = Puerto()
        self.reloj = Reloj()
        self.cliente = ClienteESP32(self.puerto, self.reloj)
        self.cliente.autorizar_deposito("botella")
        self.id = self.cliente._id

    def ev(self, evento):
        self.puerto.agregar(f"EV:{self.id}:{evento}\n")

    def test_fragmentos_y_resultado_despues_del_cierre(self):
        self.puerto.agregar(f"EV:{self.id}:OP")
        self.assertEqual(self.cliente.actualizar(), [])
        self.puerto.agregar("EN\n")
        self.assertEqual(self.cliente.actualizar(), ["OPEN"])
        self.ev("WAIT_CLEAR")
        self.ev("CLOSED")
        self.ev("DEPOSIT_POSSIBLE")
        self.assertEqual(self.cliente.actualizar(),
                         ["WAIT_CLEAR", "CLOSED", "DEPOSIT_POSSIBLE"])
        self.assertIsNone(self.cliente._id)

    def test_no_acepta_resultado_sin_cierre(self):
        self.ev("OPEN")
        self.ev("DEPOSIT_POSSIBLE")
        with self.assertRaises(ErrorESP32):
            self.cliente.actualizar()

    def test_cierre_anterior_a_apertura_no_valida_resultado(self):
        self.ev("CLOSED")
        self.ev("OPEN")
        self.ev("DEPOSIT_POSSIBLE")
        with self.assertRaises(ErrorESP32):
            self.cliente.actualizar()

    def test_fallo_serial_no_entrega_resultado(self):
        def fallar(cantidad):
            raise OSError("Puerto desconectado")
        self.puerto.read = fallar
        with self.assertRaises(ErrorESP32):
            self.cliente.actualizar()

    def test_ignora_otro_ciclo_y_duplicados(self):
        self.puerto.agregar("EV:otro:DEPOSIT_POSSIBLE\n")
        self.ev("TIMEOUT_PRESENT")
        self.ev("DEPOSIT_POSSIBLE")
        self.assertEqual(self.cliente.actualizar(), ["TIMEOUT_PRESENT"])

    def test_silencio_cancela(self):
        self.reloj.t += config.ESP32_TIMEOUT_RESPUESTA
        with self.assertRaises(ErrorESP32):
            self.cliente.actualizar()
        self.assertIn(f"CANCEL:{self.id}", self.puerto.tx)

    def test_pong_no_evade_timeout_total(self):
        self.reloj.t += config.ESP32_TIMEOUT_CICLO
        self.puerto.agregar(f"PONG:{self.id}\n")
        with self.assertRaises(ErrorESP32):
            self.cliente.actualizar()

    def test_linea_demasiado_larga_se_descarta(self):
        self.puerto.agregar("x" * 150 + f"EV:{self.id}:DEPOSIT_POSSIBLE\n")
        self.ev("WAIT_PRESENT")
        self.assertEqual(self.cliente.actualizar(), ["WAIT_PRESENT"])

    def test_liberar_cancela_y_cierra_puerto(self):
        self.cliente.liberar()
        self.assertTrue(self.puerto.cerrado)
        self.assertIn(f"CANCEL:{self.id}", self.puerto.tx)

    def test_no_reautoriza_ciclo_activo(self):
        with self.assertRaises(ErrorESP32):
            self.cliente.autorizar_deposito("botella")


class Camara:
    def __init__(self):
        self.capturas = 0

    def capturar_metadata(self):
        self.capturas += 1
        return {}


class Detector:
    def detectar(self, metadata):
        return [SimpleNamespace(nombre="bottle", confianza=0.9)]

    def primer_objeto_valido(self, detecciones):
        return detecciones[0] if detecciones else None


class Pantalla:
    def __init__(self):
        self.qrs = []

    def mostrar_mensaje(self, texto):
        pass

    def mostrar_qr(self, ruta):
        self.qrs.append(ruta)


class QR:
    def __init__(self):
        self.cantidad = 0

    def generar_qr(self):
        self.cantidad += 1
        return "prueba.png"


class TestController(unittest.TestCase):
    def setUp(self):
        self.reloj = Reloj()
        self.esp = ESP32Simulado(self.reloj)
        self.camara = Camara()
        self.qr = QR()
        self.pantalla = Pantalla()
        self.ctrl = Controller(self.camara, Detector(), self.esp,
                               self.pantalla, self.qr, self.reloj)

    def autorizar(self):
        for _ in range(config.FRAMES_CONSECUTIVOS_REQUERIDOS + 1):
            self.ctrl.procesar_frame()
        self.assertEqual(self.ctrl.estado, Estado.ESPERANDO_DEPOSITO)

    def test_ciclo_sin_consultar_desaparicion_en_camara(self):
        self.autorizar()
        capturas = self.camara.capturas
        self.ctrl.procesar_frame()
        self.assertEqual(self.qr.cantidad, 0)
        self.reloj.t += 4
        self.ctrl.procesar_frame()
        self.ctrl.procesar_frame()
        self.ctrl.procesar_frame()
        self.assertEqual(self.camara.capturas, capturas)
        self.assertEqual(self.qr.cantidad, 1)
        self.assertEqual(self.pantalla.qrs, ["prueba.png"])
        self.ctrl.procesar_frame()
        self.assertEqual(self.qr.cantidad, 1)

    def test_errores_y_timeouts_no_entregan_qr(self):
        for evento in ["TIMEOUT_PRESENT", "TIMEOUT_CLEAR", "ERROR_SENSOR",
                       "LINK_TIMEOUT", "CANCELLED"]:
            with self.subTest(evento=evento):
                self.ctrl.estado = Estado.ESPERANDO_DEPOSITO
                self.ctrl._estado_esperando_deposito([evento])
                self.assertEqual(self.ctrl.estado, Estado.PAUSA)
                self.assertEqual(self.qr.cantidad, 0)

    def test_frames_de_clases_distintas_no_se_suman(self):
        for nombre in ["bottle", "otra"] * 4:
            objeto = SimpleNamespace(nombre=nombre, confianza=0.9)
            self.ctrl.detector.primer_objeto_valido = lambda detecciones, o=objeto: o
            self.ctrl._estado_esperando_objeto({})
        self.assertEqual(self.ctrl.estado, Estado.ESPERANDO_OBJETO)


if __name__ == "__main__":
    unittest.main()
