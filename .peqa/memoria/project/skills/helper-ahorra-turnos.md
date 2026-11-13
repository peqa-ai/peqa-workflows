---
{
  "schema_version": 1,
  "id": "helper-ahorra-turnos",
  "title": "Un helper sustituye inferencia, pero cada ejecución es un turno: el ahorro depende del modelo",
  "category": "skills",
  "tags": [
    "costos",
    "helpers",
    "hooks"
  ],
  "source": "Sesión del 2026-11-12 y 13; PR #16 y #17 de peqa-ai/peqa-workflows; tests/environment-guarantees-scenarios.md",
  "scope": "project",
  "machine": null,
  "verification": "observed",
  "environment": "Claude Code 2.1.322 sin interfaz, modo automático; Opus 5.5 y Fable 5.2",
  "recheck": "Al cambiar de modelos o al añadir otro helper o un hook",
  "created_at": "2026-11-13T22:21:28.992060Z",
  "updated_at": "2026-11-13T22:21:28.992060Z"
}
---
`environment_guarantees.py` (0.21.0) sustituyó cuatro o cinco consultas que `dirige` hacía por inferencia. Medido con seis sesiones reales por celda:

- Fable 5.2: de 1,14 a 1,00 USD por sesión y de 13 a 10 turnos. Antes hacía cada consulta en un turno propio.
- Opus 5.5: de 0,46 a 0,50 USD y de 10 a 12 turnos, cerca de una desviación estándar. Ya agrupaba las consultas en un solo comando, y las dos ejecuciones del helper añadieron turnos.

Cada turno relee el contexto desde la caché: unos 40 mil tokens en estas sesiones, calculados como tokens totales entre turnos. Un helper ahorra cuando reemplaza varios turnos. Si el modelo ya agrupaba, puede costar algo más.

La conducta mejoró en ambos modelos: 6 de 6 sesiones usaron el helper, y su `proposal` evitó que copiaran reglas ajenas al encargo.

Decisión del 13 de noviembre de 2026: primero el helper llamado directamente, que funciona en los cuatro clientes. Un hook opcional solo si el helper no cierra el hueco; con 6 de 6 no se añadió.
