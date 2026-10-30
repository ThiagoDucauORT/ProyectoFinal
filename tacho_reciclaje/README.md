# Tacho Inteligente de Reciclaje — Software Embebido

Software del SIR: **Raspberry Pi 4 + AI Camera (IMX500)** para reconocimiento y QR, y **ESP32** para servo y HC-SR04. El único sensor está antes de la compuerta. El servo abre después de reconocer la botella **y confirmar presencia física**; tras presencia → ausencia estable, cierra y se genera un QR por **posible depósito**. La cámara no comprueba desaparición.

**Configuración inicial: `ESP32_SIMULACION = True`.** Para cargar el firmware, configurar UART y probar la placa, seguir [ESP32.md](ESP32.md). Incluye cómo volver atrás.

---

## 1. Arquitectura

```
tacho_reciclaje/
├── main.py              # arranca y coordina todo
├── config.py            # TODOS los parámetros configurables (pines, umbrales, rutas)
├── camera.py            # IMX500 + Picamera2: inicializa el sensor y entrega detecciones crudas
├── detector.py          # interpreta las salidas del IMX500 -> class_id, nombre, confianza, bbox
├── controller.py        # máquina de estados: la lógica del tacho
├── esp32.py             # enlace UART con ESP32 y simulador
├── probar_esp32.py      # ensayo de un ciclo sin cámara ni QR
├── servo.py             # control GPIO anterior, conservado como referencia
├── distance_sensor.py   # sensor GPIO anterior, conservado como referencia
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
| Decisiones de reconocimiento, display y QR | Raspberry Pi (CPU) |
| Presencia/ausencia, servo y tiempos físicos | ESP32 |

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

### Servo y sensor ahora conectados al ESP32

Ver [ESP32.md](ESP32.md) para pines de ejemplo, firmware Arduino, UART y
pruebas reales. Los comandos de los módulos `servo.py` y
`distance_sensor.py` corresponden al montaje GPIO anterior.

## 4b. Probar sin ESP32, servo ni sensor

En `config.py`, dejar `ESP32_SIMULACION = True`.
La cámara sigue siendo real; el ESP32 simulado representa presencia,
apertura, ausencia y cierre antes del QR.
Los flags GPIO antiguos no controlan este flujo.

Para un ensayo sin cámara ni QR:

```bash
python probar_esp32.py
```

Para el recorrido con la AI Camera:

```bash
python main.py
```

Con la placa cargada y configurada, usar `python probar_esp32.py --real`
para probar un ciclo físico sin IA. Después poner
`ESP32_SIMULACION = False` para el programa completo.
No se pasa automáticamente a simulación ante errores de comunicación.

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
        → controller.py autoriza → ESP32 controla servo / HC-SR04 → posible depósito → QR
```
