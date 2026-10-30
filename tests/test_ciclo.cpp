#include <assert.h>
#include <string>
#include <vector>
#include "../firmware/esp32_sir/ciclo.h"

std::vector<std::string> eventos;
std::vector<bool> movimientos;
void evento(const char* e) { eventos.emplace_back(e); }
void mover(bool abrir) { movimientos.push_back(abrir); }
void limpiar() { eventos.clear(); movimientos.clear(); }
void presencia(Ciclo& c, uint32_t t) {
  c.muestra(5, 5, t); c.muestra(5, 5, t + 70); c.muestra(5, 5, t + 140);
}
void avance(Ciclo& c, uint32_t t) { c.contacto(t); c.actualizar(t); }

int main() {
  {
    // Un sensor a 7 cm impide abrir aunque el otro mida 5 cm.
    limpiar(); Ciclo c(evento, mover); c.autorizar(0);
    c.muestra(5, 7, 70); c.muestra(5, 7, 140); c.muestra(5, 7, 210);
    assert(movimientos.empty());
    presencia(c, 280);
    assert(movimientos == std::vector<bool>{true});
  }
  {
    limpiar(); Ciclo c(evento, mover);
    assert(c.autorizar(0));
    assert(!c.autorizar(0));
    assert(movimientos.empty());  // reconocer nunca abre
    c.muestra(5, 5, 70); c.muestra(7, 5, 140); c.muestra(5, 5, 210);
    assert(movimientos.empty());  // un sensor >6 cm reinicia la estabilidad
    presencia(c, 280);
    assert(movimientos == std::vector<bool>{true});
    c.muestra(30, 30, 500);           // ignorar lectura durante movimiento
    avance(c, 1020);
    assert(c.fase() == Fase::PASO);
    c.muestra(NAN, 25, 1090);        // eco faltante no indica depósito
    c.muestra(25, 25, 1160); c.muestra(17, 17, 1230); // banda intermedia reinicia
    c.muestra(25, 25, 1300); c.muestra(25, 25, 1370);
    assert(c.fase() == Fase::PASO);
    c.muestra(25, 25, 1440);
    assert(c.fase() == Fase::CERRANDO);
    assert(eventos.back() == "WAIT_CLEAR"); // no resultado antes de cerrar
    c.actualizar(2040);
    assert(eventos[eventos.size()-2] == "CLOSED");
    assert(eventos.back() == "DEPOSIT_POSSIBLE");
    assert((movimientos == std::vector<bool>{true, false}));
    assert(!c.activo());
  }
  {
    limpiar(); Ciclo c(evento, mover); c.autorizar(0);
    avance(c, TIMEOUT_PRESENCIA_MS);
    c.actualizar(TIMEOUT_PRESENCIA_MS + MOVIMIENTO_MS);
    assert(eventos.back() == "TIMEOUT_PRESENT");
    assert(movimientos == std::vector<bool>{false});
  }
  {
    limpiar(); Ciclo c(evento, mover); c.autorizar(0); presencia(c, 0);
    avance(c, 740); avance(c, 740 + TIMEOUT_PASO_MS);
    c.actualizar(740 + TIMEOUT_PASO_MS + MOVIMIENTO_MS);
    assert(eventos.back() == "TIMEOUT_CLEAR");
  }
  {
    limpiar(); Ciclo c(evento, mover); c.autorizar(0); presencia(c, 0);
    c.actualizar(TIMEOUT_ENLACE_MS);
    c.actualizar(TIMEOUT_ENLACE_MS + MOVIMIENTO_MS);
    assert(eventos.back() == "LINK_TIMEOUT");
  }
  {
    limpiar(); Ciclo c(evento, mover); c.autorizar(0);
    c.actualizar(TIMEOUT_ENLACE_MS);
    c.actualizar(TIMEOUT_ENLACE_MS + MOVIMIENTO_MS);
    assert(eventos.back() == "LINK_TIMEOUT");
    assert(movimientos == std::vector<bool>{false}); // no abrió sin presencia
  }
  for (bool despuesDeAbrir : {false, true}) {
    limpiar(); Ciclo c(evento, mover); c.autorizar(0);
    if (despuesDeAbrir) presencia(c, 0);
    c.cancelar(200); c.actualizar(200 + MOVIMIENTO_MS);
    assert(eventos.back() == "CANCELLED");
  }
  for (bool despuesDeAbrir : {false, true}) {
    limpiar(); Ciclo c(evento, mover); c.autorizar(0);
    if (despuesDeAbrir) { presencia(c, 0); avance(c, 740); }
    for (unsigned n = 0; n < ERRORES_SENSOR_MAX; ++n) c.muestra(NAN, 25, 800);
    c.actualizar(800 + MOVIMIENTO_MS);
    assert(eventos.back() == "ERROR_SENSOR");
  }
  {
    limpiar(); Ciclo c(evento, mover); c.autorizar(0); presencia(c, 0);
    avance(c, 740);
    c.muestra(30, 30, 800); c.muestra(30, 30, 870); c.muestra(30, 30, 940);
    c.cancelar(1000); c.actualizar(1540);
    assert(eventos.back() == "CANCELLED"); // no premio si cancelan cerrando
  }
  {
    limpiar(); Ciclo c(evento, mover);
    uint32_t inicio = UINT32_MAX - 1000;
    c.autorizar(inicio);
    c.actualizar(inicio + TIMEOUT_ENLACE_MS);
    c.actualizar(inicio + TIMEOUT_ENLACE_MS + MOVIMIENTO_MS);
    assert(eventos.back() == "LINK_TIMEOUT"); // rollover de millis()
  }
}
