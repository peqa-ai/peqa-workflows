# Registro de uso opcional

Registra únicamente invocaciones observadas de los cinco skills PEQA. El usuario activa este registro explícitamente por repositorio; instalar el plugin o guardar memoria no lo activa. No es telemetría remota ni una auditoría de otros plugins.

```sh
python3 "$PEQA_PLUGIN/scripts/peqa_usage.py" enable --repo "$PEQA_REPO"
python3 "$PEQA_PLUGIN/scripts/peqa_usage.py" status --repo "$PEQA_REPO"
python3 "$PEQA_PLUGIN/scripts/peqa_usage.py" disable --repo "$PEQA_REPO"
```

Sin activación, `status`, `summary` y `record` no crean directorios ni archivos; `record` devuelve `skipped`. `disable` detiene nuevas escrituras y conserva el historial. Los worktrees del repositorio comparten `<git-common-dir>/peqa/usage`, con permisos privados. Otro clon o computadora tiene un registro independiente.

## Durante una invocación

Si `status` indica activación, el agente que ejecuta el skill genera un UUIDv4 aleatorio para esa invocación y lo conserva hasta terminar. Usa el nombre canónico del skill y el runtime observado: `t3-codex`, `t3-claude`, `codex` o `claude`. No atribuyas invocaciones de herramientas o lecturas de archivos a un skill que no se ejecutó.

```sh
python3 "$PEQA_PLUGIN/scripts/peqa_usage.py" record --repo "$PEQA_REPO" \
  --skill revisa --runtime t3-codex --phase started --invocation-id "$PEQA_INVOCATION"
```

Al terminar, repite con `completed` o `failed` y el mismo ID. Un informe de review completo que recomienda cambios es `completed`; `failed` significa que falló la ejecución del skill, no que se rechazó el código. Duplicados del mismo ID/fase no aumentan el conteo. Si el flujo se interrumpe, puede quedar solo `started`; no inventes un cierre. Cada invocación real nueva recibe otro UUID; un reintento del mismo evento conserva el suyo.

El registro guarda fecha UTC, identificador aleatorio del proyecto y de la invocación, skill, runtime y fase. No guarda prompts, código, transcripciones, rutas absolutas, remotos, cuentas, IDs del host ni errores libres. Los eventos son declaraciones del ejecutor; no prueban corrección, tokens consumidos o una captura exhaustiva. La escritura requiere un entorno que permita esos efectos: extraer memoria en solo lectura no autoriza registrar un evento; omite el registro si no hay permiso y conserva esa limitación.

## Consultar

```sh
python3 "$PEQA_PLUGIN/scripts/peqa_usage.py" summary --repo "$PEQA_REPO" --since 2026-10-01
```

El filtro es inclusivo y usa fechas UTC. El resultado agrupa inicios, cierres y fallos por skill/runtime para el repositorio consultado. Para comparar proyectos, consulta sus raíces explícitas y etiqueta los resultados en el análisis; el log no contiene rutas que permitan descubrirlos automáticamente. No reconstruye meses anteriores a su activación.

El archivo admite hasta 50.000 eventos y 16 MiB; al alcanzar el límite informa el error sin borrar datos ni rotar en silencio. Un fallo de registro no interrumpe el trabajo principal: comunica que ese evento no se guardó. El registro no lee memorias ni añade comentarios en GitHub.

Desde 0.9.0, registra nombres sin `peqa-`. El lector conserva los eventos históricos con ese prefijo y los agrupa bajo el nombre actual; las consultas no reescriben el archivo y los nuevos eventos usan el nombre canónico.
