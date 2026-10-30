---
{
  "schema_version": 1,
  "id": "validar-instrucciones-con-simulaciones",
  "title": "Validar cambios de instrucciones con simulaciones de contexto fresco",
  "category": "skills",
  "tags": [
    "pruebas",
    "redaccion",
    "simulaciones"
  ],
  "source": "PR #1 de peqa-ai/peqa-workflows (2026-10-30), tests/visual-evidence-scenarios.md; precedente tests/dirige-cleanup-scenarios.md",
  "scope": "project",
  "machine": null,
  "verification": "observed",
  "environment": "Desarrollo de skills de este plugin",
  "recheck": "Si AGENTS.md cambia la forma de validar instrucciones",
  "created_at": "2026-10-30T18:24:47.696693Z",
  "updated_at": "2026-10-30T18:24:47.696693Z"
}
---
Los tests unitarios del plugin solo cubren helpers. Un cambio de instrucciones se valida con simulaciones: agentes de contexto fresco leen el `SKILL.md` del checkout modificado y describen qué harían, citando archivo:línea y marcando lo que hacen por iniciativa propia.

Lo que funcionó en el PR #1 (evidencia visual):
- Prompts neutrales: describir pedido y entorno sin nombrar la conducta que se prueba. Así se distingue la instrucción de la iniciativa del modelo.
- Repetir con otro agente fresco solo los casos corregidos.
- Registrar casos, fallos y correcciones en `tests/<tema>-scenarios.md`, separando simulaciones, tests y pruebas reales.

Dos fallos de redacción aparecieron solo al simular:
- Una regla incondicional («en cada PR») produjo secciones vacías en cambios triviales. Escribe la condición.
- Mencionar una herramienta para limitarla («sigue las reglas del host sobre sus herramientas de vista previa») hizo que el agente la eligiera. Nombra en positivo la herramienta que quieres.
