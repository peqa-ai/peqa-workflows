---
{
  "schema_version": 1,
  "id": "medir-instrucciones-con-sesiones-reales",
  "title": "La simulación en papel no dice qué frases cambian la conducta; mídelo con sesiones reales contra main",
  "category": "skills",
  "tags": [
    "medicion",
    "pruebas",
    "simulaciones"
  ],
  "source": "Sesión del 2026-11-12 y 13; PR #16 y #17 de peqa-ai/peqa-workflows; tests/environment-guarantees-scenarios.md",
  "scope": "project",
  "machine": null,
  "verification": "observed",
  "environment": "Claude Code 2.1.322 sin interfaz, modo automático; Opus 5.5 y Fable 5.2",
  "recheck": "Al cambiar de modelos o de forma de validar instrucciones",
  "created_at": "2026-11-13T22:21:28.652271Z",
  "updated_at": "2026-11-13T22:21:28.652271Z"
}
---
Las simulaciones de contexto fresco encuentran ambigüedades de redacción, pero no predicen el efecto de una frase frente a `main`.

En el PR #16, ocho agentes en papel indicaron que `main` ya pedía a los hijos la salida de sus comandos y ya avisaba de que el PR no tenía checks. Doce sesiones reales de `main` mostraron lo contrario: ninguna avisó de la falta de checks, y con Opus 5.5 solo 2 de 6 encargos pedían comando y salida.

Antes de quitar o conservar una frase porque «no cambia nada», compara sesiones reales con y sin ella. Seis sesiones por celda bastaron para ver diferencias de 0/6 contra 5/6. Una diferencia de costo menor que una desviación estándar no se puede afirmar.

Complementa la nota `validar-instrucciones-con-simulaciones`: las simulaciones siguen sirviendo para pulir la redacción antes de gastar en sesiones reales.
