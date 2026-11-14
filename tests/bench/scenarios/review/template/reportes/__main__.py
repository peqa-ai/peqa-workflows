import argparse

from reportes.reporte import generar_reporte, total_general


def main(argv=None):
    parser = argparse.ArgumentParser(prog="reportes")
    comandos = parser.add_subparsers(dest="comando", required=True)
    comandos.add_parser("resumen", help="Muestra el total de ventas")
    args = parser.parse_args(argv)
    if args.comando == "resumen":
        filas = generar_reporte()
        print(f"Ventas: {len(filas)}")
        print(f"Total: {total_general(filas):.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
