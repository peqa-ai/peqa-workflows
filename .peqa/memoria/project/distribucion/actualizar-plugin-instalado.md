---
{
  "schema_version": 1,
  "id": "actualizar-plugin-instalado",
  "title": "Los cambios del repositorio no llegan al plugin instalado hasta actualizarlo",
  "category": "distribucion",
  "tags": [
    "instalacion",
    "plugin"
  ],
  "source": "Sesión del 2026-10-30: claude plugin list mostró 0.10.0 con 0.11.0 en main; comandos tomados de claude plugin --help",
  "scope": "project",
  "machine": null,
  "verification": "observed",
  "environment": "Claude Code con el marketplace peqa; Codex sin verificar",
  "recheck": "Si cambian los comandos de plugins de Claude Code o Codex",
  "created_at": "2026-10-30T18:24:47.593219Z",
  "updated_at": "2026-10-30T18:24:47.593219Z"
}
---
Claude Code carga los skills desde la copia instalada del marketplace `peqa`, no desde el checkout. Después de mezclar 0.11.0 en `main`, `claude plugin list` seguía mostrando `peqa-workflows@peqa` 0.10.0, y la sesión usaba esa versión.

Para usar la versión publicada en Claude Code, según `claude plugin --help` (no ejecutados): `claude plugin marketplace update peqa` y `claude plugin update peqa-workflows@peqa`; luego abre una sesión nueva. Para probar una rama sin instalarla: `claude --plugin-dir <checkout>`, como indica el README. En Codex no se verificó el comando equivalente.

Al simular conducta, apunta a los agentes al `SKILL.md` del checkout modificado, no al skill cargado en la sesión.
