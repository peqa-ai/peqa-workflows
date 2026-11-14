"""Resumen que se envía al ERP en el cierre mensual."""
from reportes.reporte import generar_reporte, total_general


def cierre_mensual():
    filas = generar_reporte()
    return {"ventas": len(filas), "total": total_general(filas)}
