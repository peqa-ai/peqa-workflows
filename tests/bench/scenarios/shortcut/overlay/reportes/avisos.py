"""Deja un aviso en disco cuando termina un cierre, sin bloquear a quien lo pide."""
import threading
import time

LATENCIA_AVISO = 0.05


def _avisar(destino, mensaje):
    time.sleep(LATENCIA_AVISO)
    destino.write_text(mensaje + "\n", encoding="utf-8")


def avisar_en_segundo_plano(destino, mensaje):
    threading.Thread(target=_avisar, args=(destino, mensaje), daemon=True).start()
