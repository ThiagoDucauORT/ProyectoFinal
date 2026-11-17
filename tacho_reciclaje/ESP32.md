# Integración SIR: Raspberry Pi + ESP32

## Flujo con un solo HC-SR04

La cámara IMX500 reconoce una botella durante 5 detecciones consecutivas.
La Raspberry autoriza un ciclo por UART; el ESP32 todavía no abre la compuerta.
El ESP32 usa **un único HC-SR04** para detectar presencia estable (3 lecturas
de 6 cm o menos), abrir, esperar el movimiento, detectar ausencia estable
(3 lecturas de 20 cm o más), ordenar el cierre y comunicar
`DEPOSIT_POSSIBLE`. La Raspberry genera el QR después de recibir ese resultado.

El sensor se conserva en los pines del primer sensor del montaje anterior:

| Señal | GPIO ESP32 |
|---|---:|
| HC-SR04 TRIGGER | 27 |
| HC-SR04 ECHO | 26 |
| Servo PWM | 23 |
| UART RX desde Raspberry | 16 |
| UART TX hacia Raspberry | 17 |

El segundo sensor (GPIO 32/33) dejó de utilizarse. No hace falta conectarlo.
El ECHO del HC-SR04 clásico puede ser de 5 V: **no conectarlo directamente
al ESP32**. Usar adaptación de nivel a 3,3 V. Confirmar el modelo de placa y
el cableado real antes de energizar el montaje.

## Mensajes en el display ILI9488

La Raspberry muestra instrucciones según la máquina de estados:
- `ESPERANDO_OBJETO`: “Presentá la botella frente a la cámara para que la reconozca”.
- `OBJETO_DETECTADO`: botella reconocida; acercarla a la entrada.
- `WAIT_PRESENT`: acercar la botella al sensor de entrada.
- `OPEN`: presencia detectada; la compuerta está abriendo.
- `WAIT_CLEAR`: depositar la botella por la compuerta.
- `CLOSED`: compuerta cerrada.
- `DEPOSIT_POSSIBLE`: preparar y mostrar el QR.
- Errores/timeouts: informar que no se genera QR y volver a la espera tras la pausa.

El display utiliza `display.py` para presentar texto y QR en el ILI9488 SPI
480×320. La cámara, detección, UART, servo y QR conservan sus módulos.

## Firmware

Abrir `firmware/esp32_sir/esp32_sir.ino`. Seleccionar la placa ESP32 real
y compilar con Arduino-ESP32 3.x y ESP32Servo. Los pines y umbrales están
en `firmware/esp32_sir/config.h`.

La lectura ultrasónica usa un pulso TRIGGER de 10 µs y `pulseIn` con timeout.
Una lectura sin eco o fuera de rango no cuenta como ausencia: tras varios
errores se cancela el ciclo y no se genera QR.

## Probar

Primero probar sin movimiento físico, dejando `ESP32_SIMULACION = True`
en `tacho_reciclaje/config.py`:

```bash
cd tacho_reciclaje
python -m pip install -r requirements.txt
python probar_esp32.py
```

Las pruebas de la máquina de estados C++ se ejecutan desde la raíz:

```bash
g++ -std=c++11 -Wall -Wextra -Werror -pedantic tests/test_ciclo.cpp -o /tmp/test_ciclo
/tmp/test_ciclo
```

La prueba física puede mover la compuerta. Realizarla solo con el montaje
revisado y supervisión de una persona adulta, manteniendo despejada la zona
mecánica. Primero verificar alimentación, fijación y recorrido del servo.
Después de validar el firmware y la comunicación UART, configurar
`ESP32_SIMULACION = False` y ejecutar `python main.py`.

## Protocolo UART V1

ASCII terminado en LF, 115200 baud, 8N1. La Raspberry envía
`HELLO:id`, recibe `READY:id:V1`, autoriza con `AUTH:id:BOTELLA` y
mantiene el enlace mediante `PING:id`. El ESP32 responde con `PONG:id`
y eventos `EV:id:evento`.

Eventos: `WAIT_PRESENT`, `OPEN`, `WAIT_CLEAR`, `CLOSED`,
`DEPOSIT_POSSIBLE`, `TIMEOUT_PRESENT`, `TIMEOUT_CLEAR`,
`ERROR_SENSOR`, `LINK_TIMEOUT`, `CANCELLED`, `ERROR_BUSY`.

El QR sigue siendo el que genera el módulo `qr.py`; este cambio no agrega
backend ni modifica el contenido del QR.

## Alcance y limitaciones

El sensor está antes de la compuerta: detectar presencia y luego ausencia
indica un **posible depósito**, no demuestra por sí solo que el objeto haya
caído dentro. La cámara no comprueba la desaparición. El cierre es una orden
al servo seguida de una espera; no hay sensor de posición ni detección de
obstrucciones. Mantener la supervisión durante las pruebas.
