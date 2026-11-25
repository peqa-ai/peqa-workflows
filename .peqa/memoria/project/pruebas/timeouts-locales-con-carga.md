---
{
  "schema_version": 1,
  "id": "timeouts-locales-con-carga",
  "title": "Pruebas con tiempo límite fallan en una máquina cargada: compara con una copia intacta de main",
  "category": "pruebas",
  "tags": [
    "ci",
    "timeouts"
  ],
  "source": "Sesión del 2026-11-14; PR #24 de peqa-ai/peqa-workflows",
  "scope": "project",
  "machine": null,
  "verification": "observed",
  "environment": "macOS con carga alta de otras aplicaciones; CI de GitHub Actions",
  "recheck": "Si cambian los tiempos límite de los helpers o de sus pruebas",
  "created_at": "2026-11-25T16:31:56.523292Z",
  "updated_at": "2026-11-25T16:31:56.523292Z"
}
---
El 14 de noviembre de 2026, dos pruebas de `tests/test_ui_checks.py` (`TransportTests`) fallaron en local con `TimeoutExpired` en un `git diff` con límite de 20 segundos, en una rama que no tocaba `ui_checks`. La máquina tenía una carga media de entre 9 y 30 por otras aplicaciones. Las mismas pruebas fallaron igual sobre una copia intacta de `main`, y el CI del PR pasó en los tres trabajos.

Cuando falle por tiempo una prueba que tu cambio no toca:

1. Ejecútala sola.
2. Ejecútala sobre una copia intacta: `git archive origin/main | tar -x -C <carpeta temporal>`.
3. Si falla igual, es la máquina. Dilo en el PR y deja que el CI decida.
