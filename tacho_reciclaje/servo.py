"""
servo.py
========
Control de los servomotores de las compuertas.

Tiene DOS modos, controlados por config.SERVO_SIMULACION:

  - SIMULACIÓN (True): no se toca el GPIO. Cada apertura/cierre imprime por
    consola qué señal se habría enviado (pin + ángulo). Sirve para probar el
    sistema completo SIN el servo conectado y confirmar que la orden sale.

  - REAL (False): control físico por GPIO/PWM con gpiozero + backend lgpio.

Librería (modo real): gpiozero con backend lgpio.
-------------------------------------------------
  - AngularServo te deja mover el servo por ÁNGULO; genera el PWM correcto
    sin que calcules duty cycles a mano.
  - En Raspberry Pi OS actual el backend recomendado es lgpio (RPi.GPIO y
    pigpio quedaron desactualizados en kernels nuevos).

SEGURIDAD (sección 19 del brief) — aplica al modo real:
  - El GPIO NO puede alimentar un servo, solo entrega la SEÑAL.
  - El servo se alimenta con fuente EXTERNA de 5V con corriente suficiente.
    Alimentarlo desde el pin 5V de la Pi puede resetear la placa.
  - GND de la fuente y GND de la Pi UNIDOS (masa común).
  - Conexión: GPIO -> señal del servo; fuente 5V -> V+ del servo; GND común.
"""

import time

import config

# Solo importamos gpiozero si vamos a usar hardware real. Así, en modo
# simulación, el código corre aunque gpiozero/lgpio no estén instalados o
# no haya GPIO disponible (por ejemplo, editando desde otra máquina).
if not config.SERVO_SIMULACION:
    try:
        from gpiozero import AngularServo, Device
        from gpiozero.pins.lgpio import LGPIOFactory
        Device.pin_factory = LGPIOFactory()
    except ImportError:
        print("[servo] ERROR: falta gpiozero/lgpio para el modo real.")
        print("        Instala con: sudo apt install -y python3-gpiozero python3-lgpio")
        print("        (o deja SERVO_SIMULACION = True en config.py)")
        raise


class Compuerta:
    """
    Representa UNA compuerta accionada por UN servo. Conoce su pin y sus
    angulos de abierto/cerrado. Se comporta distinto segun el modo.
    """

    def __init__(self, nombre, pin):
        self.nombre = nombre
        self.pin = pin
        self.simulado = config.SERVO_SIMULACION

        if self.simulado:
            # Modo simulacion: no creamos ningun objeto de hardware.
            self.servo = None
            print(f"[servo] (SIMULACION) Compuerta '{nombre}' preparada "
                  f"en pin GPIO{pin} (sin hardware).")
        else:
            # Modo real: creamos el AngularServo. min/max_pulse_width cubren
            # el rango tipico de un servo de 180. Ajusta si se mueve raro.
            self.servo = AngularServo(
                pin,
                min_angle=0,
                max_angle=180,
                min_pulse_width=0.0005,   # 0.5 ms
                max_pulse_width=0.0025,   # 2.5 ms
            )

        # Arrancamos en posicion cerrada.
        self.cerrar()

    def _mover_a(self, angulo, accion):
        """
        Mueve el servo a un angulo. En simulacion solo lo reporta; en real
        manda el PWM. `accion` es solo texto para el log ("ABRIR"/"CERRAR").
        """
        if self.simulado:
            # ESTE es el mensaje de "senal enviada" que pediste: confirma
            # que el sistema mando la orden, con pin y angulo concretos.
            print(f"[servo] >> SENAL ENVIADA al servo '{self.nombre}' "
                  f"(GPIO{self.pin}): {accion} -> {angulo} grados")
        else:
            self.servo.angle = angulo

        # En ambos modos esperamos el tiempo de movimiento, para que la
        # temporizacion del sistema sea la misma con o sin hardware.
        time.sleep(config.SERVO_TIEMPO_MOVIMIENTO)

    def abrir(self):
        print(f"[servo] Abriendo compuerta '{self.nombre}'")
        self._mover_a(config.SERVO_ANGULO_ABIERTO, "ABRIR")

    def cerrar(self):
        print(f"[servo] Cerrando compuerta '{self.nombre}'")
        self._mover_a(config.SERVO_ANGULO_CERRADO, "CERRAR")

    def liberar(self):
        """Libera el pin/PWM. Solo hace algo en modo real."""
        if not self.simulado and self.servo is not None:
            self.servo.close()


class ControlServos:
    """
    Administra TODAS las compuertas. El resto del programa habla con esta
    clase usando el "tipo de compuerta" ("botella" / "lata"), nunca con
    pines directamente.
    """

    def __init__(self):
        self.compuertas = {
            "botella": Compuerta("botella", config.SERVO_BOTELLA_PIN),
            # "lata": Compuerta("lata", config.SERVO_LATA_PIN),
        }
        modo = "SIMULACION" if config.SERVO_SIMULACION else "REAL"
        print(f"[servo] {len(self.compuertas)} compuerta(s) inicializada(s) "
              f"en modo {modo}.")

    def _compuerta(self, tipo_objeto):
        c = self.compuertas.get(tipo_objeto)
        if c is None:
            raise ValueError(f"[servo] No hay compuerta para '{tipo_objeto}'")
        return c

    def abrir_compuerta(self, tipo_objeto):
        self._compuerta(tipo_objeto).abrir()

    def cerrar_compuerta(self, tipo_objeto):
        self._compuerta(tipo_objeto).cerrar()

    def liberar_todo(self):
        for c in self.compuertas.values():
            c.liberar()
        print("[servo] Todos los servos liberados.")
