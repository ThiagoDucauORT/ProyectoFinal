"""
config.py
=========
Punto ÚNICO de configuración del tacho inteligente.

Idea clave: ningún otro archivo debería tener "números mágicos" ni rutas
hardcodeadas. Si mañana cambiás un pin, el modelo, o un ángulo del servo,
lo tocás ACÁ y nada más. El resto del código lee desde este módulo.

Pi 4 + AI Camera (IMX500) para detección; ESP32 para sensor y compuerta.
Los parámetros GPIO de las secciones 4 y 5 son del código anterior.
El flujo nuevo NO los usa: configurar hardware en firmware/esp32_sir/config.h.
"""

# ==========================================================================
# 1. MODELO / IMX500
# ==========================================================================
# Ruta al archivo .rpk que se sube al sensor IMX500.
#
# OPCIÓN A (la que estamos usando ahora): modelo genérico oficial que ya
# viene instalado con el paquete imx500-models. Detecta 80 clases COCO,
# entre ellas "bottle". Sirve para probar TODO el sistema hoy mismo.
#
# Cuando tengas tu modelo propio de marcas (best.pt -> export imx -> .rpk),
# solamente cambiás esta ruta y la lista OBJETOS_VALIDOS de abajo.
MODEL_RPK_PATH = "/usr/share/imx500-models/imx500_network_ssd_mobilenetv2_fpnlite_320x320_pp.rpk"

# Archivo de labels (nombres de clase). Para el modelo genérico COCO usamos
# el archivo de labels que traeremos al proyecto (assets/coco_labels.txt).
#
# Cuando uses tu modelo propio, la exportación imx te genera un labels.txt
# con TUS clases: apuntá esta ruta a ese archivo. NUNCA inventamos los
# nombres a mano; salen del modelo.
LABELS_PATH = "assets/coco_labels.txt"

# Umbral de confianza. Ignoramos toda detección por debajo de este valor.
CONFIDENCE_THRESHOLD = 0.50

# IoU para el post-procesado (fusiona cajas superpuestas del mismo objeto).
IOU_THRESHOLD = 0.65

# Máximo de detecciones que pedimos por frame. Más que suficiente para un
# tacho donde esperamos 1 objeto por vez.
MAX_DETECTIONS = 10


# ==========================================================================
# 2. OBJETOS QUE EL TACHO ACEPTA
# ==========================================================================
# Nombres de clase (tal como aparecen en LABELS_PATH) que consideramos
# "reciclables válidos". Solo estos disparan la apertura de compuerta.
#
# Con el modelo genérico COCO las clases relevantes son "bottle" (botella)
# y no hay una clase "can/lata" propia, así que por ahora trabajamos con
# botella. Cuando tengas tu modelo de marcas, esto pasa a ser algo como:
#   OBJETOS_VALIDOS = ["Coca-Cola", "Pepsi", "Sprite"]
OBJETOS_VALIDOS = ["bottle"]

# Mapeo objeto -> qué servo/compuerta usar. Con el modelo genérico todo
# cae en "botella". Cuando separes por tipo (botella vs lata) esto define
# qué compuerta se abre para cada clase detectada.
#   clave  = nombre de clase del modelo
#   valor  = "botella" o "lata" (clave que usa servo.py / config de pines)
OBJETO_A_COMPUERTA = {
    "bottle": "botella",
    # "can": "lata",   # <- se activará cuando tu modelo tenga la clase lata
}


# ==========================================================================
# 3. FILTRADO TEMPORAL DE DETECCIONES (anti falso positivo)
# ==========================================================================
# Exigimos que el MISMO objeto se detecte en varios frames seguidos antes
# de darlo por válido. Evita abrir la compuerta por un frame ruidoso.
FRAMES_CONSECUTIVOS_REQUERIDOS = 5


# ==========================================================================
# 4. SERVOS (compuertas) - GPIO / PWM
# ==========================================================================
# LEGADO: servo.py se conserva como referencia, no se carga desde main.py.
# Numeración BCM (la de gpiozero). Elegí pines que NO choquen con el resto.
#
# IMPORTANTE (ver sección de seguridad en la explicación): el servo se
# alimenta con una fuente EXTERNA de 5V, NO desde el pin de 5V de la Pi.
# El GPIO SOLO envía la señal PWM; masa (GND) común entre Pi y fuente.
SERVO_BOTELLA_PIN = 12   # GPIO12 (soporta PWM por hardware)
SERVO_LATA_PIN = 13      # GPIO13 (soporta PWM por hardware) - preparado

# Ángulos de la compuerta (grados). Ajustables según tu mecánica.
SERVO_ANGULO_CERRADO = 0
SERVO_ANGULO_ABIERTO = 90

# Tiempo (segundos) que damos al servo para llegar a la posición antes de
# considerar el movimiento terminado.
SERVO_TIEMPO_MOVIMIENTO = 0.6

# MODO SIMULACIÓN de servos.
#   True  -> NO se toca el GPIO. Cada movimiento imprime por consola qué
#            señal se habría enviado (pin + ángulo). Útil mientras el servo
#            NO está conectado: te da confirmación de que el sistema manda
#            la orden, sin necesitar hardware.
#   False -> control real por GPIO/PWM (cuando conectes el servo).
SERVO_SIMULACION = False


# ==========================================================================
# 5. SENSOR HC-SR04 (confirmación de depósito) - GPIO
# ==========================================================================
# LEGADO: distance_sensor.py no se carga desde main.py. El sensor está ANTES
# de la compuerta; presencia -> ausencia permite estimar un posible depósito.
# ATENCIÓN: el pin ECHO del HC-SR04 entrega 5V y el GPIO de la Pi tolera
# solo 3.3V. Debe ir un DIVISOR DE TENSIÓN entre ECHO y el GPIO.
# El código asume que la señal que LLEGA al GPIO ya está adaptada a 3.3V.
HC_SR04_TRIGGER_PIN = 23   # GPIO23 - salida (3.3V, OK directo)
HC_SR04_ECHO_PIN = 24      # GPIO24 - entrada (¡vía divisor de tensión!)

# Si un objeto queda a esta distancia (cm) o menos frente al sensor,
# lo tomamos como "objeto ingresó al tacho".
DETECTION_DISTANCE_CM = 15.0

# Cuánto tiempo (segundos) esperamos el depósito antes de cerrar por timeout
# (para no quedar trabados si el usuario no deposita nada).
TIMEOUT_ESPERANDO_DEPOSITO = 15.0

# MODO SIMULACIÓN del HC-SR04.
#   True  -> NO se toca el GPIO. El "depósito" se confirma solo tras esperar
#            SENSOR_SIM_SEGUNDOS desde que se abre la compuerta. Útil para
#            probar el ciclo completo (hasta el QR) sin el sensor conectado.
#   False -> lectura real del HC-SR04 por GPIO.
SENSOR_SIMULACION = True

# En modo simulación, cuántos segundos tras abrir la compuerta se da por
# confirmado el depósito (simula el tiempo que tarda el usuario en depositar).
SENSOR_SIM_SEGUNDOS = 3.0


# ==========================================================================
# 6. QR
# ==========================================================================
QR_CONTENIDO = "TEST-RECICLAJE"   # contenido de prueba (sin puntos aún)
QR_OUTPUT_PATH = "qr.png"          # dónde se guarda el PNG generado


# ==========================================================================
# 7. DISPLAY
# ==========================================================================
# Como todavía no hay display físico, display.py trabaja en modo consola
# y opcionalmente abre una ventana con el QR. Poné False si corrés headless
# (por SSH sin entorno gráfico) para que no intente abrir ventanas.
DISPLAY_MOSTRAR_VENTANA_QR = True

# PREVIEW DE LA CÁMARA (ventana con el video en vivo + cajas de detección).
#   True  -> abre una ventana mostrando lo que ve la cámara, dibujando la
#            caja y el nombre de los objetos que el tacho ACEPTA (botella).
#            Necesita PANTALLA conectada / entorno gráfico en la Pi.
#   False -> sin ventana (por ejemplo si corrés por SSH sin escritorio).
MOSTRAR_PREVIEW = True

# Modo de preview a intentar PRIMERO. El sistema igual prueba los otros como
# fallback si el elegido falla.
#   "QTGL" -> ventana Qt acelerada por GPU (escritorio normal).
#   "QT"   -> ventana Qt por software.
#   "DRM"  -> dibuja directo sobre el HDMI/framebuffer, SIN Qt ni X11.
# Si te da el error "could not load the Qt platform plugin xcb", poné "DRM":
# esquiva Qt por completo y suele funcionar con monitor por HDMI.
PREVIEW_MODO = "QTGL"


# ==========================================================================
# 8. ESP32: comunicación y simulación del NUEVO flujo
# ==========================================================================
# True simula solo el ESP32; cámara y generación de QR siguen siendo reales.
# Para usar la placa, cargar el firmware y cambiar a False.
# No existe fallback automático a simulación si falla la comunicación real.
ESP32_SIMULACION = True
ESP32_PUERTO = "/dev/serial0"     # UART GPIO de la Pi, NO USB por defecto
ESP32_BAUDRATE = 115200           # debe coincidir con config.h del ESP32
ESP32_TIMEOUT_INICIO = 8.0       # handshake HELLO / READY
ESP32_INTERVALO_PING = 0.5
ESP32_TIMEOUT_RESPUESTA = 3.0
ESP32_TIMEOUT_CICLO = 20.0       # mayor que presencia + paso + movimientos
PAUSA_ENTRE_CICLOS = 2.0         # pausa temporal, sin comprobar con la cámara
