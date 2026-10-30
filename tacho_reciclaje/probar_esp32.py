"""Prueba un solo ciclo físico sin cámara y sin generar QR."""
import argparse
import time
from esp32 import ClienteESP32, ESP32Simulado, ErrorESP32, TERMINALES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real", action="store_true",
                        help="usar UART REAL; autoriza una apertura si hay presencia")
    args = parser.parse_args()
    cliente = None
    try:
        cliente = ClienteESP32() if args.real else ESP32Simulado()
        print("PRUEBA REAL: acercá un objeto al sensor." if args.real else
              "SIMULACIÓN: no se mueve ningún servo.")
        cliente.autorizar_deposito("botella")
        while True:
            for evento in cliente.actualizar():
                print(evento)
                if evento in TERMINALES:
                    return 0 if evento == "DEPOSIT_POSSIBLE" else 1
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("Prueba cancelada.")
        return 1
    except ErrorESP32 as error:
        print(f"ERROR: {error}")
        return 1
    finally:
        if cliente is not None:
            cliente.liberar()


if __name__ == "__main__":
    raise SystemExit(main())
