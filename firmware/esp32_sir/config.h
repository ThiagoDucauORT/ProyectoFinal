#pragma once
#include <stdint.h>
constexpr int UART_RX_PIN = 16;
constexpr int UART_TX_PIN = 17;
constexpr int SERVO_PIN = 23;
// Un solo HC-SR04: conservar el primer sensor (GPIO 27/26).
constexpr int TRIGGER_PIN = 27;
constexpr int ECHO_PIN = 26;  // ECHO adaptado a 3.3 V
constexpr uint32_t BAUDRATE = 115200;
constexpr int ANGULO_CERRADO = 0;
constexpr int ANGULO_ABIERTO = 90;
constexpr int SERVO_MIN_US = 1000;
constexpr int SERVO_MAX_US = 2000;
constexpr float PRESENCIA_CM = 6.0f;
// Umbral inicial: pared de referencia a ~10 cm; validar con lecturas reales.
constexpr float AUSENCIA_CM = 8.0f;
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
