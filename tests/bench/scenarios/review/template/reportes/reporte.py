"""Reporte de ventas: una fila por venta, con su total."""
from reportes.datos import VENTAS


def generar_reporte(ventas=None):
    filas = []
    for venta in VENTAS if ventas is None else ventas:
        filas.append({
            "fecha": venta["fecha"],
            "cliente": venta["cliente"],
            "producto": venta["producto"],
            "unidades": venta["unidades"],
            "total": round(venta["unidades"] * venta["precio"], 2),
        })
    return filas


def total_general(filas):
    return round(sum(fila["total"] for fila in filas), 2)
