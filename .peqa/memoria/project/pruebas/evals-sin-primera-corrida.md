---
{
  "schema_version": 1,
  "id": "evals-sin-primera-corrida",
  "title": "Los evals de activación y las piezas nuevas del banco aún no tienen ninguna sesión real",
  "category": "pruebas",
  "tags": [
    "banco",
    "evals",
    "medicion"
  ],
  "source": "Sesión del 2026-11-18; PR #27 de peqa-ai/peqa-workflows",
  "scope": "project",
  "machine": null,
  "verification": "observed",
  "environment": "main en 1a70a15, plugin 0.23.0",
  "recheck": "Tras la primera corrida real de trigger_eval.py o del banco con las opciones nuevas",
  "created_at": "2026-11-18T20:47:37.408455Z",
  "updated_at": "2026-11-18T20:47:37.408455Z"
}
---
El PR #27 añadió `tests/evals/triggering/` y, en el banco, `--no-plugin`, `--iteration`, `viewer.py`, `judge.py`, `--host codex` y los escenarios `idea` y `memoria-grande`. Todo se probó sin modelo: ninguna sesión real los ha usado.

La primera corrida debe confirmar a mano, leyendo una muestra de los `.jsonl`:

- que el skill cargado llega como `Skill` con `input.skill` igual a `peqa-workflows:<nombre>`;
- que `--setting-sources project,local` deja fuera el plugin instalado en la cuenta en la celda sin plugin;
- que las expresiones del escenario `idea` aciertan sobre informes reales;
- la forma de la respuesta que lee el juez.

Propuesta sin decidir: empezar por un solo skill en holdout (24 sesiones, tope 0,50 USD cada una) antes de las 96 del holdout completo.

No se hizo release: el PR solo tocó `tests/` y dos frases de documentación. La release espera al primer cambio que los evals produzcan en un skill.
