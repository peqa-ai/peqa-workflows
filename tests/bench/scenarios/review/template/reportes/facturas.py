"""Importe a facturar por cliente, a partir del reporte de ventas."""
from collections import defaultdict

from reportes.reporte import generar_reporte


def facturas_por_cliente(ventas=None):
    totales = defaultdict(float)
    for fila in generar_reporte(ventas):
        totales[fila["cliente"]] += fila["total"]
    return {cliente: round(total, 2) for cliente, total in totales.items()}
