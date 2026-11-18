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
  "source": "Sesión del 2026-11-12 y 13; PR #16 y #17 de peqa-ai/peqa-workflows; tests/environment-guarantees-scenarios.md; tests/bench/run.py en 1a70a15",
  "scope": "project",
  "machine": null,
  "verification": "observed",
  "environment": "Claude Code 2.1.322 sin interfaz, modo automático; Opus 5.5 y Fable 5.2",
  "recheck": "Si cambian las opciones de claude -p o la lectura de eventos de tests/bench/run.py",
  "created_at": "2026-11-13T22:21:28.775475Z",
  "updated_at": "2026-11-18T20:47:38.385543Z"
}
---
Receta usada el 12 y 13 de noviembre de 2026: 42 sesiones, unos 34 USD. Desde v0.22.0 el banco vive en `tests/bench/` y su guía es `tests/bench/README.md`; esta nota conserva los tropiezos que lo motivaron.

- Exporta cada versión del plugin con `git archive <ref>` a una carpeta y cárgala con `claude -p --plugin-dir`. Opciones usadas: `--permission-mode auto --output-format stream-json --verbose --setting-sources project,local --strict-mcp-config --no-session-persistence --max-budget-usd`.
- Cada sesión trabaja en un repositorio de ejemplo nuevo, con un remoto bare local. Un `gh` sustituto al inicio del `PATH` registra cada llamada y responde con un estado fijo.
- La implementación se mide con pruebas de aceptación que el agente no ve. La conducta sale del flujo de eventos y del registro de `gh`. Costo y tokens vienen en el evento `result` (`total_cost_usd`, `modelUsage`).
- Costo de referencia por sesión de una tarea pequeña: unos 0,45 USD con Opus 5.5 y 1 USD con Fable 5.2, entre uno y dos minutos.

Tropiezos:

- Al limpiar el entorno de la sesión hija, conserva las variables de credenciales del cliente. Sin ellas falla con «OAuth session expired».
- Las sesiones concurrentes se ven con `ListAgents`, y 3 de 42 escribieron a otra. Una sesión puede emitir varios eventos `result` (al esperar a un subagente en segundo plano o al responder a otra sesión): `run.py` toma el costo del último y el informe del más largo.
- Los agentes abren los archivos del plugin con `cat` o `sed` en Bash, no solo con `Read`. Cuenta ambos.
- Un valor canario en `.env` permite detectar si alguien lo abrió.
- Un remoto con ruta local delata el montaje: una sesión no abrió PR por eso.
- Alterna el orden de las versiones entre repeticiones.
