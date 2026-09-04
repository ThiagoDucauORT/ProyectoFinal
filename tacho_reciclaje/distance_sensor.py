"""
distance_sensor.py
==================
Confirmacion de que el objeto ingreso al tacho.

Tiene DOS modos, controlados por config.SENSOR_SIMULACION:

  - SIMULACION (True): no se toca el GPIO. El deposito se da por confirmado
    automaticamente tras esperar config.SENSOR_SIM_SEGUNDOS desde que se
    abrio la compuerta. Sirve para probar el ciclo completo (hasta el QR)
    teniendo SOLO la camara y la placa, sin el HC-SR04 conectado.

  - REAL (False): lectura fisica del HC-SR04 por GPIO con gpiozero.

Como funciona el HC-SR04 (modo real):
  1. Se manda un pulso corto por TRIGGER.
  2. El sensor emite ultrasonido y pone ECHO en alto.
  3. ECHO vuelve a bajo cuando el eco regresa.
  4. El tiempo en alto es proporcional a la distancia.
  gpiozero.DistanceSensor implementa todo ese protocolo por nosotros.

SEGURIDAD (seccion 19 del brief) - aplica al modo real:
  - El pin ECHO del HC-SR04 entrega 5V; el GPIO de la Pi tolera 3.3V.
  - Conectar ECHO directo al GPIO puede DANAR la placa.
  - Hay que poner un DIVISOR DE TENSION entre ECHO y el GPIO
    (tipico: R1=1k del ECHO al GPIO, R2=2k del GPIO a GND).
  - TRIGGER es salida de la Pi (3.3V) y el sensor la lee bien: va directo.
  - Este codigo asume que ECHO ya llega adaptado a 3.3V por hardware.
"""

import time

import config

# Solo importamos gpiozero si vamos a usar hardware real. En simulacion el
# modulo corre sin gpiozero/lgpio ni sensor conectado.
if not config.SENSOR_SIMULACION:
    try:
        from gpiozero import DistanceSensor, Device
        from gpiozero.pins.lgpio import LGPIOFactory
        Device.pin_factory = LGPIOFactory()
    except ImportError:
        print("[distance] ERROR: falta gpiozero/lgpio para el modo real.")
        print("           Instala con: sudo apt install -y python3-gpiozero python3-lgpio")
        print("           (o deja SENSOR_SIMULACION = True en config.py)")
        raise


class SensorDistancia:
    """
    Envuelve el HC-SR04. La unica pregunta que le hace el resto del sistema
    es: "ya ingreso el objeto?" -> objeto_depositado().
    """

    def __init__(self):
        self.simulado = config.SENSOR_SIMULACION
        # Marca de tiempo de cuando empezamos a esperar el deposito.
        # La usa el modo simulacion para contar los segundos.
        self._t_inicio_espera = None

        if self.simulado:
            self.sensor = None
            print(f"[distance] (SIMULACION) HC-SR04 en modo simulado: "
                  f"confirmara deposito {config.SENSOR_SIM_SEGUNDOS}s despues "
                  f"de abrir la compuerta.")
        else:
            # DistanceSensor mide en METROS. max_distance define el rango.
            self.sensor = DistanceSensor(
                echo=config.HC_SR04_ECHO_PIN,
                trigger=config.HC_SR04_TRIGGER_PIN,
                max_distance=1.0,
            )
            print(f"[distance] HC-SR04 inicializado "
                  f"(TRIG={config.HC_SR04_TRIGGER_PIN}, "
                  f"ECHO={config.HC_SR04_ECHO_PIN}).")

    def iniciar_espera(self):
        """
        Marca el momento en que el sistema empieza a esperar el deposito.
        El controller la llama justo al abrir la compuerta. En modo real no
        hace falta, pero la dejamos por compatibilidad (no molesta).
        """
        self._t_inicio_espera = time.time()

    def distancia_cm(self):
        """Distancia medida en centimetros (solo modo real)."""
        if self.simulado:
            return -1.0
        return self.sensor.distance * 100.0

    def objeto_depositado(self):
        """
        True si se confirma que el objeto ingreso al tacho.

        - Simulacion: True una vez que pasaron SENSOR_SIM_SEGUNDOS desde
          iniciar_espera().
        - Real: True si hay un objeto a DETECTION_DISTANCE_CM o menos.
        """
        if self.simulado:
            if self._t_inicio_espera is None:
                return False
            transcurrido = time.time() - self._t_inicio_espera
            if transcurrido >= config.SENSOR_SIM_SEGUNDOS:
                print(f"[distance] (SIMULACION) Deposito confirmado "
                      f"tras {transcurrido:.1f}s.")
                self._t_inicio_espera = None  # evita re-disparo
                return True
            return False

        d = self.distancia_cm()
        presente = d <= config.DETECTION_DISTANCE_CM
        if presente:
            print(f"[distance] Objeto detectado a {d:.1f} cm -> "
                  f"deposito confirmado.")
        return presente

    def liberar(self):
        """Libera el pin al apagar (solo modo real)."""
        if not self.simulado and self.sensor is not None:
            self.sensor.close()
        print("[distance] Sensor liberado.")
