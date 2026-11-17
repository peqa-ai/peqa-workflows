---
{
  "schema_version": 1,
  "id": "csv-separador-punto-y-coma",
  "title": "Los CSV del proyecto usan punto y coma como separador",
  "category": "formatos",
  "tags": [
    "csv",
    "excel"
  ],
  "source": "Decisión de contabilidad del 2026-09-04",
  "scope": "project",
  "machine": null,
  "verification": "user-confirmed",
  "environment": null,
  "recheck": null,
  "created_at": "2026-11-17T17:49:30.552966Z",
  "updated_at": "2026-11-17T17:49:30.552966Z"
}
---
Contabilidad abre los CSV del proyecto en Excel con la configuración regional en español, que usa la coma como separador decimal. Con la coma como separador de campos, Excel muestra cada fila en una sola columna.

Decisión: todo CSV que genere el proyecto usa `;` como separador de campos. Las comillas siguen las reglas habituales del módulo `csv` de Python.
