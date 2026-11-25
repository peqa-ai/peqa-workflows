---
{
  "schema_version": 1,
  "id": "medir-antes-de-construir",
  "title": "Antes de añadir un helper o una frase a un skill, mide si la conducta ya ocurre en main",
  "category": "skills",
  "tags": [
    "decisiones",
    "helpers",
    "medicion"
  ],
  "source": "Sesiones del 2026-11-12 al 14; PR #17, #20, #22 y #24 de peqa-ai/peqa-workflows; tests/environment-guarantees-scenarios.md, tests/revisa-blast-radius-scenarios.md y tests/patch-signals-scenarios.md",
  "scope": "project",
  "machine": null,
  "verification": "observed",
  "environment": "Claude Code sin interfaz, modo automático; Opus 5.5 y Fable 5.2",
  "recheck": "Al cambiar de modelos o al medir en un repositorio grande",
  "created_at": "2026-11-25T16:31:56.325829Z",
  "updated_at": "2026-11-25T16:31:56.325829Z"
}
---
De tres helpers construidos en noviembre de 2026, solo uno cambió la conducta medida.

- `environment_guarantees.py`: sí. Sin él, Fable 5.2 mezcló y desplegó sin que corriera ningún check en 3 de 3 sesiones; con él se detuvo y preguntó.
- `blast_radius.py`: no. Las 12 revisiones encontraron los archivos rotos, con y sin él.
- `patch_signals.py`: no. Las 12 sesiones arreglaron la causa, con y sin él, y en 54 sesiones guardadas no había ninguna señal.

Los dos que no cambiaron nada buscaban algo que Opus 5.5 y Fable 5.2 ya hacen solos en un proyecto pequeño. El que sí cambió entregaba hechos que la sesión no consultaba: la protección de la rama, los checks del PR y los ajustes del cliente.

Antes de construir:

1. Mira si el problema aparece en sesiones ya guardadas. `tests/bench/patch_signals.py` y `run.py reanalyse` las miden sin costo.
2. Si no hay datos, mide primero `main` en un escenario donde el fallo sea posible.
3. Construye solo si `main` falla.

Decisiones tomadas con estos datos: `patch_signals.py` quedó como instrumento del banco y `dirige` no lo ejecuta. `blast_radius.py` se mezcló en 0.22.0 por decisión del usuario, sabiendo que no había demostrado valor. Ninguna de las dos mediciones cubre un repositorio grande.
