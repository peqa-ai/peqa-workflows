---
{
  "schema_version": 1,
  "id": "informe-final-completo",
  "title": "Lo que el usuario debe recibir va en el informe final, no en un aviso intermedio",
  "category": "skills",
  "tags": [
    "fable",
    "informe",
    "redaccion"
  ],
  "source": "Sesión del 2026-11-12 y 13; PR #16 y #17 de peqa-ai/peqa-workflows; tests/environment-guarantees-scenarios.md",
  "scope": "project",
  "machine": null,
  "verification": "observed",
  "environment": "Claude Code 2.1.322 sin interfaz, modo automático; Opus 5.5 y Fable 5.2",
  "recheck": "Al cambiar de modelos",
  "created_at": "2026-11-13T22:21:28.906460Z",
  "updated_at": "2026-11-13T22:21:28.906460Z"
}
---
Una instrucción que pide «avisar al empezar» y no repetirlo en el informe final pierde el contenido con Fable 5.2.

En seis sesiones reales del PR #16, Fable escribió el aviso como nota de progreso, sin el ajuste propuesto, y en 4 de 6 informes lo dio por «ya propuesto al empezar». El ajuste no llegó al usuario en ninguna. Opus 5.5 lo puso todo en el informe final y funcionó en 6 de 6.

Al pedir que el informe final lleve cada elemento completo, el ajuste llegó en 5 de 6 sesiones de Fable. Con el helper que devuelve la propuesta ya redactada, en 6 de 6.

Al escribir un skill: el informe final es el único texto que el usuario recibe con seguridad. Un aviso anterior puede sumarse a él, pero el informe lo lleva completo.
