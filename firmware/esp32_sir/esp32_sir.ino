#include <Arduino.h>
#include <ESP32Servo.h>
#include <ctype.h>
#include <string.h>
#include "ciclo.h"

HardwareSerial enlace(2);
Servo compuerta;
char idCiclo[33] = "";
char ultimoId[33] = "";  // AUTH duplicada jamás inicia el mismo ciclo otra vez
char saludo[33] = "";
uint32_t inicioSaludo = 0;
bool saludoPendiente = false;
bool sincronizado = false;
char linea[121];
size_t usados = 0;
bool descartando = false;
uint32_t ultimaMuestra = 0;

void mover(bool abrir) {
  compuerta.write(abrir ? ANGULO_ABIERTO : ANGULO_CERRADO);
}

void emitir(const char* evento) {
  enlace.printf("EV:%s:%s\n", idCiclo, evento);
}

Ciclo ciclo(emitir, mover);

bool idValido(const char* id) {
  if (!id || strlen(id) != 32) return false;
  for (unsigned i = 0; i < 32; ++i) {
    if (!isxdigit(static_cast<unsigned char>(id[i]))) return false;
  }
  return true;
}

void comando(char* texto, uint32_t ahora) {
  char* contexto = nullptr;
  char* tipo = strtok_r(texto, ":", &contexto);
  char* id = strtok_r(nullptr, ":", &contexto);
  char* valor = strtok_r(nullptr, ":", &contexto);
  char* extra = strtok_r(nullptr, ":", &contexto);
  if (!tipo || !idValido(id) || extra) return;
  if (!strcmp(tipo, "HELLO") && !valor) {
    // Repetir el mismo saludo NO reinicia el tiempo de cierre.
    if (strcmp(saludo, id)) {
      strcpy(saludo, id);
      sincronizado = false;
      saludoPendiente = true;
      ciclo.cancelar(ahora);
      mover(false);
      inicioSaludo = ahora;
    } else if (sincronizado) {
      enlace.printf("READY:%s:V1\n", saludo);
    }
  } else if (!strcmp(tipo, "AUTH") && valor && !strcmp(valor, "BOTELLA")) {
    if (!sincronizado || !strcmp(ultimoId, id)) return;
    if (ciclo.activo()) {
      enlace.printf("EV:%s:ERROR_BUSY\n", id);
      return;
    }
    strcpy(idCiclo, id);
    strcpy(ultimoId, id);
    ciclo.autorizar(ahora);
  } else if (!valor && !strcmp(idCiclo, id)) {
    if (!strcmp(tipo, "PING") && ciclo.activo()) {
      ciclo.contacto(ahora);
      enlace.printf("PONG:%s\n", idCiclo);
    } else if (!strcmp(tipo, "CANCEL")) {
      ciclo.cancelar(ahora);
    }
  }
}

float distanciaCM(int triggerPin, int echoPin) {
  digitalWrite(triggerPin, LOW);
  delayMicroseconds(2);
  digitalWrite(triggerPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(triggerPin, LOW);
  unsigned long duracion = pulseIn(echoPin, HIGH, ECO_TIMEOUT_US);
  return duracion ? duracion * 0.0343f / 2.0f : NAN;
}

void setup() {
  Serial.begin(BAUDRATE);
  enlace.begin(BAUDRATE, SERIAL_8N1, UART_RX_PIN, UART_TX_PIN);
  pinMode(TRIGGER_PIN_1, OUTPUT);
  digitalWrite(TRIGGER_PIN_1, LOW);
  pinMode(ECHO_PIN_1, INPUT);
  pinMode(TRIGGER_PIN_2, OUTPUT);
  digitalWrite(TRIGGER_PIN_2, LOW);
  pinMode(ECHO_PIN_2, INPUT);
  compuerta.setPeriodHertz(50);
  compuerta.attach(SERVO_PIN, SERVO_MIN_US, SERVO_MAX_US);
  if (!compuerta.attached()) {
    Serial.println("ERROR: servo no inicializado. Revisar config.h.");
    while (true) delay(1000);  // no READY, no autorizaciones
  }
  mover(false);
  Serial.println("SIR V1: esperando HELLO por UART2.");
}

void loop() {
  // Procesamiento acotado: una ráfaga Serial no retrasa los timeouts.
  for (unsigned n = 0; n < 256 && enlace.available(); ++n) {
    char c = enlace.read();
    if (c == '\n') {
      if (!descartando) {
        linea[usados] = '\0';
        comando(linea, millis());
      }
      usados = 0;
      descartando = false;
    } else if (c != '\r' && !descartando) {
      if (usados < sizeof(linea) - 1) linea[usados++] = c;
      else { usados = 0; descartando = true; }
    }
  }
  uint32_t ahora = millis();
  ciclo.actualizar(ahora);
  if (saludoPendiente && !ciclo.activo() && ahora - inicioSaludo >= MOVIMIENTO_MS) {
    saludoPendiente = false;
    sincronizado = true;
    enlace.printf("READY:%s:V1\n", saludo);
  }
  if (ciclo.medir() && ahora - ultimaMuestra >= MUESTREO_MS) {
    ultimaMuestra = ahora;
    // Medir secuencialmente para reducir interferencia entre ecos.
    float cm1 = distanciaCM(TRIGGER_PIN_1, ECHO_PIN_1);
    delay(5);
    float cm2 = distanciaCM(TRIGGER_PIN_2, ECHO_PIN_2);
    ahora = millis();
    ciclo.actualizar(ahora);   // timeout tiene prioridad sobre las lecturas
    ciclo.muestra(cm1, cm2, ahora);
  }
  delay(1);
}
