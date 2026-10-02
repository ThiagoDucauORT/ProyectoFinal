# Integración SIR: Raspberry Pi + ESP32

## Qué cambia

La cámara reconoce una botella durante 5 detecciones consecutivas. La
Raspberry envía una autorización; **todavía no se abre la compuerta**.
El ESP32 espera 3 mediciones válidas seguidas a 15 cm o menos, abre, espera
600 ms de movimiento y luego busca 3 mediciones válidas seguidas a 20 cm
o más. Ordena cerrar, espera otros 600 ms y comunica un **posible depósito**.
Recién entonces la Raspberry genera el QR de prueba.

La cámara no comprueba que la botella desaparezca. El sensor está antes
de la compuerta: retirar la botella hacia atrás también puede dar un
posible depósito. Se acepta esa limitación para este prototipo.
El QR sigue conteniendo `TEST-RECICLAJE`; no se agregaron puntos ni backend.

| Archivo | Responsabilidad |
|---|---|
| `controller.py` | Reconocimiento estable, autorización y QR según resultado |
| `esp32.py` | Serial, identificador de ciclo, heartbeat y simulador |
| `main.py` | Arranque y apagado; ya no carga GPIO de servo/sensor |
| `config.py` | Puerto, baudrate, simulación y tiempos de la Raspberry |
| `../firmware/esp32_sir/esp32_sir.ino` | UART y acceso al servo y HC-SR04 |
| `../firmware/esp32_sir/ciclo.h` | Secuencia física autónoma |
| `../firmware/esp32_sir/config.h` | Pines y calibración del ESP32 |
| `servo.py`, `distance_sensor.py` | Código anterior conservado como referencia |
| `probar_esp32.py` | Ensayo de un ciclo sin cámara ni QR |

Los flags anteriores `SERVO_SIMULACION` y `SENSOR_SIMULACION` no controlan
el flujo nuevo. Ahora se usa `ESP32_SIMULACION`.

## 1. Primero probar la simulación

Desde `tacho_reciclaje/`, con el entorno Python del proyecto activado:

```bash
python -m pip install -r requirements.txt
python probar_esp32.py
```

Sin cámara ni placa debe imprimir:
`WAIT_PRESENT`, `OPEN`, `WAIT_CLEAR`, `CLOSED`, `DEPOSIT_POSSIBLE`.
Es un recorrido automático de prueba, no una lectura física.

Para probar además cámara y QR en la Raspberry:
dejar `ESP32_SIMULACION = True` en `config.py` y ejecutar `python main.py`.
La cámara tiene que estar conectada. El QR generado en simulación es solo
para probar el software.

## 2. Preparar el firmware

La configuración de ejemplo es para un **ESP32 clásico con UART2**.
No se conoce aún el modelo exacto ni el pinout de la placa del equipo.
En variantes como ESP32-C3 hay que adaptar el UART además de los pines.

1. Instalar Arduino IDE y el paquete de placas **esp32 by Espressif Systems**
   de la serie 3.x. URL del gestor:
   `https://espressif.github.io/arduino-esp32/package_esp32_index.json`.
2. Instalar **ESP32Servo** de Kevin Harrington / John K. Bennett desde el
   gestor de bibliotecas, con versión compatible con Arduino-ESP32 3.x.
3. Abrir `firmware/esp32_sir/esp32_sir.ino`.
4. Seleccionar el modelo de placa y el puerto de programación reales.
5. Ajustar `config.h` con el compañero de hardware.
6. Compilar y cargar el sketch. El USB muestra diagnósticos a 115200;
   el protocolo con la Raspberry usa UART2, no ese USB.

| Señal | GPIO ESP32 de ejemplo |
|---|---|
| RX desde Raspberry | 16 |
| TX hacia Raspberry | 17 |
| PWM servo | 18 |
| HC-SR04 TRIGGER | 25 |
| HC-SR04 ECHO | 26, con adaptación de tensión |

Los números son GPIO, no números de pata del encapsulado ni posición del
conector. No conectar siguiendo esta tabla si no coincide con la placa.
Calibrar ángulos 0/90, pulsos 1000/2000 µs y tiempo de movimiento 600 ms.
El firmware ordena cerrar al arrancar.

## 3. Conectar UART en Raspberry Pi 4

| Raspberry Pi 4 | ESP32 |
|---|---|
| GPIO14 TX, pin físico 8 | RX configurado en `config.h` |
| GPIO15 RX, pin físico 10 | TX configurado en `config.h` |
| GND | GND común |

UART es lógica de 3,3 V. El ECHO del HC-SR04 convencional requiere
adaptación desde 5 V a 3,3 V. Usar la alimentación del servo prevista en
la placa y masa común; el PWM no alimenta el motor.

En la Raspberry ejecutar `sudo raspi-config`, entrar en la configuración
del puerto serie, desactivar la consola de login por Serial y activar
el hardware Serial. Reiniciar. Verificar que exista `/dev/serial0`.
Si faltan permisos, agregar el usuario al grupo `dialout` y volver a
iniciar sesión:

```bash
sudo usermod -aG dialout "$USER"
```

En `config.py`:

```python
ESP32_PUERTO = "/dev/serial0"
ESP32_BAUDRATE = 115200
```

Cambiar solo el puerto a `/dev/ttyUSB0` no cambia la UART del firmware:
para comunicar por USB hay que adaptar también el sketch. Este código
está preparado para la conexión entre GPIO de la placa.

## 4. Probar la placa antes de usar la cámara

```bash
cd tacho_reciclaje
python probar_esp32.py --real
```

**Esta prueba autoriza una botella sin IA** y puede mover el servo. No
genera QR. Acercar un objeto al sensor y luego retirarlo de su campo para
ensayar el recorrido; eso prueba la lógica, no demuestra un depósito.

Validar también:

| Prueba | Resultado esperado |
|---|---|
| No acercar objeto | `TIMEOUT_PRESENT`, sin abrir |
| Mantener objeto después de abrir | `TIMEOUT_CLEAR`, cierre, sin QR |
| Perder el eco durante varias lecturas | `ERROR_SENSOR`, sin QR |
| Interrumpir la comunicación durante el ciclo | Cierre autónomo por `LINK_TIMEOUT` |
| Presencia y luego ausencia estable | Cierre antes de `DEPOSIT_POSSIBLE` |

El HC-SR04 necesita un eco válido del fondo cuando no hay objeto. Si al
quedar libre apunta a un espacio sin eco, aparecerá `ERROR_SENSOR`.
Ajustar ubicación, fondo y umbrales con mediciones reales. Un timeout de
eco nunca se interpreta como ausencia.

El cierre es una **orden más un tiempo de espera**, no hay sensor de
posición del servo. Si el objeto queda trabado, el código igualmente
ordena cerrar al vencer el tiempo: revisar mecánica, fuerza y ángulos
antes de habilitar la compuerta para uso. No detecta obstrucciones.

## 5. Activar todo

Una vez que el ensayo físico funciona, poner:

```python
ESP32_SIMULACION = False
```

y ejecutar `python main.py`. No hay cambio automático a simulación si
falla la placa: el programa informa el error y deja de autorizar ciclos.
Después de cada resultado hay una pausa de 2 s; no se consulta la
desaparición con la cámara para habilitar el próximo ciclo.

## Protocolo V1

ASCII con salto de línea LF, 115200 baud, 8N1. `id` es un identificador
hexadecimal de 32 caracteres. Cada autorización lleva uno nuevo.

| Dirección | Mensaje | Uso |
|---|---|---|
| Pi → ESP32 | `HELLO:id` | Sincroniza y ordena cerrar cualquier ciclo anterior |
| ESP32 → Pi | `READY:id:V1` | Responde después del tiempo de cierre |
| Pi → ESP32 | `AUTH:id:BOTELLA` | Autoriza un único ciclo |
| Pi → ESP32 | `PING:id` | Cada 0,5 s durante el ciclo |
| ESP32 → Pi | `PONG:id` | Confirma enlace |
| Pi → ESP32 | `CANCEL:id` | Cancela y ordena cerrar |
| ESP32 → Pi | `EV:id:evento` | Informa pasos y resultado |

Eventos: `WAIT_PRESENT`, `OPEN`, `WAIT_CLEAR`, `CLOSED`,
`DEPOSIT_POSSIBLE`, `TIMEOUT_PRESENT`, `TIMEOUT_CLEAR`,
`ERROR_SENSOR`, `LINK_TIMEOUT`, `CANCELLED`, `ERROR_BUSY`.
Los resultados normales se envían después de `CLOSED`.
`ERROR_BUSY` rechaza una autorización inesperada.
Resultados de otro identificador o duplicados no generan otro QR.
No se reintenta una autorización perdida.

Tiempos ESP32: presencia 5 s, desaparición 10 s, movimiento 0,6 s,
heartbeat perdido 2 s. Raspberry: respuesta 3 s, ciclo completo 20 s.
Si cambiás tiempos en el firmware, ajustar los límites Python también.
La lectura ultrasónica espera como máximo 25 ms y se intenta cada 70 ms.

## Pruebas automatizadas

Desde la raíz del repositorio, sin hardware:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
mkdir -p build
g++ -std=c++11 -Wall -Wextra -Werror -pedantic tests/test_ciclo.cpp -o build/test_ciclo
./build/test_ciclo
```

Prueban estabilidad, umbrales, ausencia de eco, cierre antes del resultado,
timeouts, cancelación, rollover de millis(), Serial fragmentado, mensajes
de otro ciclo y un solo QR sin consultar desaparición con cámara.
Son pruebas de Python y de la lógica C++; no reemplazan compilar el
sketch con el core ESP32 ni ensayar la placa y la cámara reales.

## Cómo volver atrás

Los cambios están en la rama `sir/esp32-posible-deposito`, separados de
`main`. Para probar esa rama en una copia local sin cambios pendientes:

```bash
git fetch origin
git switch --track origin/sir/esp32-posible-deposito
```

Si ya existe la rama local, usar `git switch sir/esp32-posible-deposito`.
Para regresar al programa anterior, detenerlo y usar `git switch main`.
Guardar antes los ajustes locales de pines/puerto (por ejemplo con un
commit en tu rama) para que no impidan cambiar de rama.

- **Antes de fusionar el PR:** cerrar el PR con *Close pull request*.
  `main` sigue intacta; no hace falta revertir código.
- **Después de fusionar:** usar *Revert* en el PR fusionado si GitHub
  ofrece el botón. Crea otro PR con los cambios inversos. Revisarlo y
  fusionarlo para recuperar el código anterior.
- Alternativa desde Git: `git revert <SHA>` si se fusionó con squash;
  `git revert -m 1 <SHA_DEL_MERGE>` si se creó un merge commit. Hacerlo
  en otra rama y enviar un PR. No usar force push para borrar historial.

Cambiar de rama o revertir Python **no desprograma el ESP32 ni cambia el
cableado**. El programa anterior necesita servo y sensor conectados a la
Raspberry como antes. Para volver físicamente al montaje anterior hay
que restaurar esas conexiones/configuraciones con el compañero.

Referencias: [UART Arduino-ESP32](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/serial.html),
[ESP32Servo](https://github.com/madhephaestus/ESP32Servo),
[UART Raspberry Pi](https://www.raspberrypi.com/documentation/computers/configuration.html).
