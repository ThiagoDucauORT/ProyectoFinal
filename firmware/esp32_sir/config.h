#pragma once
#include <stdint.h>

// Pines de EJEMPLO para ESP32 clásico. Adaptar a la placa del compañero.
// No son los GPIO de la Raspberry. UART2 no está disponible en todos los ESP32.
constexpr int UART_RX_PIN = 16;
constexpr int UART_TX_PIN = 17;
constexpr int SERVO_PIN = 18;
constexpr int TRIGGER_PIN = 25;
constexpr int ECHO_PIN = 26;  // ECHO HC-SR04 adaptado a 3.3 V en hardware
constexpr uint32_t BAUDRATE = 115200;
constexpr int ANGULO_CERRADO = 0;
constexpr int ANGULO_ABIERTO = 90;
constexpr int SERVO_MIN_US = 1000;
constexpr int SERVO_MAX_US = 2000;

constexpr float PRESENCIA_CM = 15.0f;
constexpr float AUSENCIA_CM = 20.0f;  // histéresis: 15..20 no confirma ningún lado
constexpr unsigned MUESTRAS_ESTABLES = 3;
constexpr unsigned ERRORES_SENSOR_MAX = 5;
constexpr uint32_t MUESTREO_MS = 70;
constexpr uint32_t ECO_TIMEOUT_US = 25000;
constexpr uint32_t MOVIMIENTO_MS = 600;
constexpr uint32_t TIMEOUT_PRESENCIA_MS = 5000;
constexpr uint32_t TIMEOUT_PASO_MS = 10000;
constexpr uint32_t TIMEOUT_ENLACE_MS = 2000;

static_assert(PRESENCIA_CM >= 2 && AUSENCIA_CM > PRESENCIA_CM && AUSENCIA_CM <= 400,
              "Revisar umbrales: ausencia debe superar presencia (2..400 cm).");
static_assert(MUESTRAS_ESTABLES > 0 && ERRORES_SENSOR_MAX > 0,
              "Los contadores deben ser positivos.");
