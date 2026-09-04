# Tacho Inteligente de Reciclaje — Software Embebido

Software que corre en una **Raspberry Pi 4 (8GB)** con **Raspberry Pi AI Camera (Sony IMX500)**, servos reales y sensor HC-SR04. Detecta un objeto reciclable, abre una compuerta, confirma el depósito con el ultrasónico y genera un QR de prueba.

---

## 1. Arquitectura

```
tacho_reciclaje/
├── main.py              # arranca y coordina todo
├── config.py            # TODOS los parámetros configurables (pines, umbrales, rutas)
├── camera.py            # IMX500 + Picamera2: inicializa el sensor y entrega detecciones crudas
├── detector.py          # interpreta las salidas del IMX500 -> class_id, nombre, confianza, bbox
├── controller.py        # máquina de estados: la lógica del tacho
├── servo.py             # control REAL de servos (gpiozero + lgpio)
├── distance_sensor.py   # control REAL del HC-SR04 (gpiozero)
├── qr.py                # generación REAL del QR
├── display.py           # interfaz con el futuro display (hoy: consola + ventana QR)
├── assets/
│   └── coco_labels.txt  # nombres de clase del modelo genérico
├── models/              # acá irá tu modelo propio (.rpk) cuando lo tengas
└── requirements.txt
```

**Regla de oro del diseño:** `controller.py` NO toca GPIO ni Picamera2 directamente. Cada pieza de hardware está encapsulada en su módulo. Así, el día que cambies el display, o migres el modelo, tocás un solo archivo.

### Qué corre dónde (IMX500 vs. Raspberry Pi)

| Tarea | Dónde corre |
|---|---|
| Captura de imagen | IMX500 (sensor) |
| **Inferencia de la red neuronal** | **IMX500 (sensor)** ← lo pesado |
| Interpretar tensores de salida | Raspberry Pi (CPU, liviano) |
| Máquina de estados, servos, sensor, QR | Raspberry Pi (CPU) |

Esta es la ventaja clave de la AI Camera: la Pi queda casi libre porque la red corre dentro del sensor.

---

## 2. Instalación (desde la terminal SSH de la Raspberry Pi)

### 2.1 Conectarse por SSH y actualizar el sistema

```bash
ssh pi@<IP-de-tu-raspberry>
sudo apt update && sudo apt full-upgrade -y
sudo reboot
```

### 2.2 Firmware y herramientas del IMX500 (por APT)

```bash
# Firmware del sensor + modelos genéricos (.rpk) + herramientas de empaquetado
sudo apt install -y imx500-all imx500-tools

# Picamera2 y apps de cámara
sudo apt install -y python3-picamera2 rpicam-apps

# GPIO moderno (gpiozero + backend lgpio)
sudo apt install -y python3-gpiozero python3-lgpio

# Utilidades varias
sudo apt install -y git python3-venv python3-pip
sudo reboot
```

> Los modelos genéricos quedan en `/usr/share/imx500-models/`. El que usa este proyecto por defecto es `imx500_network_ssd_mobilenetv2_fpnlite_320x320_pp.rpk`.

### 2.3 Copiar el proyecto y crear el entorno virtual

```bash
cd ~
# (copiá la carpeta tacho_reciclaje por scp, git o VS Code Remote-SSH)
cd ~/tacho_reciclaje

# Venv que HEREDA los paquetes del sistema (picamera2, gpiozero se instalan por apt)
python3 -m venv --system-site-packages venv
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

### 2.4 Ejecutar

```bash
cd ~/tacho_reciclaje
source venv/bin/activate
python main.py
```

Ctrl+C para salir (apaga todo de forma ordenada).

---

## 3. Desarrollo con VS Code + Remote-SSH

1. Instalá la extensión **Remote - SSH** en VS Code (en tu PC).
2. `F1` → *Remote-SSH: Connect to Host* → `pi@<IP>`.
3. *File → Open Folder* → `/home/pi/tacho_reciclaje`.
4. Seleccioná el intérprete: `F1` → *Python: Select Interpreter* → el del venv (`~/tacho_reciclaje/venv/bin/python`).
5. Abrí una terminal integrada (ya está en la Pi por SSH) y corré `python main.py`.

Todo el código se ejecuta En la Raspberry, no en tu PC.

---

## 4. Verificar el hardware

### Cámara AI / IMX500
```bash
rpicam-hello --list-cameras          # debería listar la IMX500
rpicam-hello -t 5000                  # 5s de preview (si tenés pantalla/HDMI)
```

### Demo oficial de detección (confirma que la IA del sensor anda)
```bash
git clone https://github.com/raspberrypi/picamera2.git
cd picamera2/examples/imx500
python imx500_object_detection_demo.py \
  --model /usr/share/imx500-models/imx500_network_ssd_mobilenetv2_fpnlite_320x320_pp.rpk
```

### Servos
Con el proyecto instalado, un test rápido en Python:
```bash
python -c "from servo import ControlServos; import time; s=ControlServos(); s.abrir_compuerta('botella'); time.sleep(1); s.cerrar_compuerta('botella'); s.liberar_todo()"
```

### HC-SR04
```bash
python -c "from distance_sensor import SensorDistancia; import time; d=SensorDistancia();
[print(f'{d.distancia_cm():.1f} cm') or time.sleep(0.5) for _ in range(10)]; d.liberar()"
```

---

## 4b. Probar SIN servo ni sensor (solo cámara y placa)

Si todavía tenés solo la cámara y la Raspberry, podés correr el ciclo completo (detección → apertura → depósito → QR → cierre) en modo simulación. En `config.py`:

```python
SERVO_SIMULACION = True     # el servo no se mueve; imprime la señal que enviaría
SENSOR_SIMULACION = True    # el depósito se confirma solo tras unos segundos
SENSOR_SIM_SEGUNDOS = 3.0   # cuánto tarda en confirmarse el depósito simulado
```

Con esto:

- **Servo:** en vez de mover hardware, imprime la confirmación de que mandó la orden:
  ```
  [servo] >> SEÑAL ENVIADA al servo 'botella' (GPIO12): ABRIR -> 90 grados
  ```
- **Sensor:** en vez de leer el HC-SR04, da por confirmado el depósito automáticamente unos segundos después de abrir la compuerta. Así el flujo avanza y **el QR se genera de verdad** (`qr.png`).

Ninguno de los dos modos necesita que gpiozero esté funcionando, así que el arranque no falla por falta de hardware. Cuando conectes cada pieza, cambiás su flag a `False` y pasa a control real, sin tocar el resto del código.

> Nota: la cámara SÍ tiene que estar conectada — la detección es hardware real (IMX500). Lo que se simula es solo lo que no tenés todavía: servo y sensor.

### Ventana de video en vivo (preview)

Al correr `main.py` se abre una ventana mostrando lo que ve la cámara, con la **caja y el nombre dibujados sobre los objetos que el tacho acepta** (botella). Se controla con:

```python
MOSTRAR_PREVIEW = True     # ventana con video en vivo + cajas
```

Requiere **pantalla conectada** a la Pi (entorno gráfico). Si corrés sin escritorio, ponelo en `False` y el sistema funciona igual, solo sin ventana. El resto de los objetos (persona, etc.) se detectan pero no se les dibuja caja, para no ensuciar la pantalla.

---

## 5. Seguridad eléctrica (LEER antes de conectar)

- **Servos:** aliméntalos con una **fuente externa de 5V** con corriente suficiente. **NUNCA** desde el pin 5V de la Pi (los picos de corriente la resetean). **GND común** entre Pi, fuente y servos. El GPIO solo lleva la **señal**.
- **HC-SR04 ECHO:** entrega **5V**, el GPIO tolera **3.3V**. Poné un **divisor de tensión** en ECHO (típico R1=1kΩ + R2=2kΩ) antes de entrar al GPIO. TRIGGER va directo (la Pi manda 3.3V y el sensor la lee bien).

---

## 6. Pasar a tu modelo propio (marcas) — para más adelante

El código ya está preparado. El objeto `YOLO("best.pt")` corre en **CPU**, NO en el sensor. Para usar el acelerador del IMX500 hay que **exportar y empaquetar** el modelo:

```bash
# En tu PC o en la Pi, con Ultralytics instalado:
pip install ultralytics

python - << 'PY'
from ultralytics import YOLO
m = YOLO("best.pt")                 # tu modelo entrenado (yolov8n o yolo11n)
m.export(format="imx", data="tu_dataset.yaml")   # cuantiza y exporta a formato imx
PY
```

Eso genera una carpeta `best_imx_model/` con, entre otros, `packerOut.zip` y `labels.txt`. Después empaquetás el `.rpk`:

```bash
cd best_imx_model
imx500-package -i packerOut.zip -o out
# genera out/network.rpk
```

Finalmente, en `config.py`:
```python
MODEL_RPK_PATH = "models/network.rpk"
LABELS_PATH = "models/labels.txt"      # el que generó el export (TUS clases)
OBJETOS_VALIDOS = ["Coca-Cola", "Pepsi", "Sprite"]   # tus clases reales
```

**Importante:** solo **YOLOv8n** y **YOLO11n** (nano) son exportables a IMX500. Modelos más grandes no.

El flujo completo queda:
```
best.pt → export imx (cuantización) → packerOut.zip → imx500-package → network.rpk
        → se sube al IMX500 → el sensor infiere → detector.py interpreta
        → controller.py decide → servo / HC-SR04 / QR
```
