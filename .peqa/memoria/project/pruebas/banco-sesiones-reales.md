---
{
  "schema_version": 1,
  "id": "banco-sesiones-reales",
  "title": "Cómo medir dirige con sesiones reales sin tocar GitHub",
  "category": "pruebas",
  "tags": [
    "costos",
    "dirige",
    "medicion"
  ],
  "source": "Sesión del 2026-11-12 y 13; PR #16 y #17 de peqa-ai/peqa-workflows; tests/environment-guarantees-scenarios.md",
  "scope": "project",
  "machine": null,
  "verification": "observed",
  "environment": "Claude Code 2.1.322 sin interfaz, modo automático; Opus 5.5 y Fable 5.2",
  "recheck": "Si el banco se añade al repositorio o cambian las opciones de claude -p",
  "created_at": "2026-11-13T22:21:28.775475Z",
  "updated_at": "2026-11-13T22:21:28.775475Z"
}
---
Receta usada el 12 y 13 de noviembre de 2026: 42 sesiones, unos 34 USD. El banco no está en el repositorio.

- Exporta cada versión del plugin con `git archive <ref>` a una carpeta y cárgala con `claude -p --plugin-dir`. Opciones usadas: `--permission-mode auto --output-format stream-json --verbose --setting-sources project,local --strict-mcp-config --no-session-persistence --max-budget-usd`.
- Cada sesión trabaja en un repositorio de ejemplo nuevo, con un remoto bare local. Un `gh` sustituto al inicio del `PATH` registra cada llamada y responde con un estado fijo.
- La implementación se mide con pruebas de aceptación que el agente no ve. La conducta sale del flujo de eventos y del registro de `gh`. Costo y tokens vienen en el evento `result` (`total_cost_usd`, `modelUsage`).
- Costo de referencia por sesión de una tarea pequeña: unos 0,45 USD con Opus 5.5 y 1 USD con Fable 5.2, entre uno y dos minutos.

Tropiezos:

- Al limpiar el entorno de la sesión hija, conserva las variables de credenciales del cliente. Sin ellas falla con «OAuth session expired».
- Las sesiones concurrentes se ven con `ListAgents`, y 3 de 42 escribieron a otra. Una pregunta recibida después de entregar produce un segundo evento `result`: usa el primero.
- Los agentes abren los archivos del plugin con `cat` o `sed` en Bash, no solo con `Read`. Cuenta ambos.
- Un valor canario en `.env` permite detectar si alguien lo abrió.
- Un remoto con ruta local delata el montaje: una sesión no abrió PR por eso.
- Alterna el orden de las versiones entre repeticiones.
