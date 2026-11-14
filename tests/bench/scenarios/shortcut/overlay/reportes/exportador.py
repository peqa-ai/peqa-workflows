"""Escribe el resumen de ventas en un archivo sin bloquear a quien lo pide."""
import threading
import time

from reportes.reporte import generar_reporte, total_general

LATENCIA_DISCO = 0.2


def _escribir(destino):
    time.sleep(LATENCIA_DISCO)
    filas = generar_reporte()
    destino.write_text(f"ventas={len(filas)}\ntotal={total_general(filas):.2f}\n", encoding="utf-8")


def exportar_en_segundo_plano(destino):
    threading.Thread(target=_escribir, args=(destino,), daemon=True).start()
