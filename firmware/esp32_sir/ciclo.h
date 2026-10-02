#pragma once
#include "config.h"
#include <math.h>

// Lógica portable: no usa Arduino. Probada también con g++ en tests/.
enum class Fase { REPOSO, PRESENCIA, ABRIENDO, PASO, CERRANDO };

class Ciclo {
 public:
  using Evento = void (*)(const char*);
  using Mover = void (*)(bool);
  Ciclo(Evento evento, Mover mover) : evento_(evento), mover_(mover) {}

  Fase fase() const { return fase_; }
  bool activo() const { return fase_ != Fase::REPOSO; }
  bool medir() const { return fase_ == Fase::PRESENCIA || fase_ == Fase::PASO; }

  bool autorizar(uint32_t ahora) {
    if (activo()) return false;
    fase_ = Fase::PRESENCIA;
    inicio_ = contacto_ = ahora;
    estables_ = errores_ = 0;
    evento_("WAIT_PRESENT");
    return true;
  }

  void contacto(uint32_t ahora) { contacto_ = ahora; }

  void cancelar(uint32_t ahora) {
    if (activo()) cerrar("CANCELLED", ahora);
  }

  void actualizar(uint32_t ahora) {
    // Restas unsigned: soportan el rollover de millis().
    if (fase_ == Fase::CERRANDO) {
      if (ahora - inicio_ >= MOVIMIENTO_MS) {
        fase_ = Fase::REPOSO;
        evento_("CLOSED");
        evento_(resultado_);
      }
      return;
    }
    if (!activo()) return;
    if (ahora - contacto_ >= TIMEOUT_ENLACE_MS) {
      cerrar("LINK_TIMEOUT", ahora);
    } else if (fase_ == Fase::PRESENCIA && ahora - inicio_ >= TIMEOUT_PRESENCIA_MS) {
      cerrar("TIMEOUT_PRESENT", ahora);
    } else if (fase_ == Fase::ABRIENDO && ahora - inicio_ >= MOVIMIENTO_MS) {
      fase_ = Fase::PASO;
      inicio_ = ahora;
      estables_ = errores_ = 0;
      evento_("WAIT_CLEAR");
    } else if (fase_ == Fase::PASO && ahora - inicio_ >= TIMEOUT_PASO_MS) {
      cerrar("TIMEOUT_CLEAR", ahora);
    }
  }

  void muestra(float cm, uint32_t ahora) {
    if (!medir()) return;
    // Un eco faltante/invalidado NO cuenta como ausencia.
    if (!isfinite(cm) || cm < 2.0f || cm > 400.0f) {
      estables_ = 0;
      if (++errores_ >= ERRORES_SENSOR_MAX) cerrar("ERROR_SENSOR", ahora);
      return;
    }
    errores_ = 0;
    bool cumple = fase_ == Fase::PRESENCIA ? cm <= PRESENCIA_CM : cm >= AUSENCIA_CM;
    estables_ = cumple ? estables_ + 1 : 0;
    if (estables_ < MUESTRAS_ESTABLES) return;
    estables_ = 0;
    if (fase_ == Fase::PRESENCIA) {
      mover_(true);
      fase_ = Fase::ABRIENDO;
      inicio_ = ahora;
      evento_("OPEN");
    } else {
      cerrar("DEPOSIT_POSSIBLE", ahora);
    }
  }

 private:
  void cerrar(const char* resultado, uint32_t ahora) {
    // CANCEL puede invalidar un éxito aún pendiente de completar el cierre.
    resultado_ = resultado;
    if (fase_ == Fase::CERRANDO) return;
    mover_(false);
    fase_ = Fase::CERRANDO;
    inicio_ = ahora;
    estables_ = errores_ = 0;
  }
  Evento evento_;
  Mover mover_;
  Fase fase_ = Fase::REPOSO;
  uint32_t inicio_ = 0, contacto_ = 0;
  unsigned estables_ = 0, errores_ = 0;
  const char* resultado_ = "CANCELLED";
};
