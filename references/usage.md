# Registro de uso opcional

Registra únicamente invocaciones observadas de los seis skills PEQA. El usuario activa este registro explícitamente por repositorio; instalar el plugin o guardar memoria no lo activa. No es telemetría remota ni una auditoría de otros plugins.

```sh
python3 "$PEQA_PLUGIN/scripts/peqa_usage.py" enable --repo "$PEQA_REPO"
python3 "$PEQA_PLUGIN/scripts/peqa_usage.py" status --repo "$PEQA_REPO"
python3 "$PEQA_PLUGIN/scripts/peqa_usage.py" disable --repo "$PEQA_REPO"
```

Sin activación, `status`, `summary` y `record` no crean directorios ni archivos; `record` devuelve `skipped`. `disable` detiene nuevas escrituras y conserva el historial. Los worktrees del repositorio comparten `<git-common-dir>/peqa/usage`, con permisos privados. Otro clon o computadora tiene un registro independiente.

El helper responde `UNSAFE_STORAGE` si el directorio común de Git pertenece a otro usuario o admite escritura de otros. Acepta que el grupo escriba en él, como lo deja `git init` con umask 002, porque quien escribe ahí ya controla el repositorio. Debajo no cede: `peqa` rechaza la escritura del grupo, `usage` exige 0700 y sus archivos 0600.

## Durante una invocación

Si `status` indica activación, el agente que ejecuta el skill genera un UUIDv4 aleatorio para esa invocación y lo conserva hasta terminar. Usa el nombre canónico del skill y el runtime observado: `t3-codex`, `t3-claude`, `orca-codex`, `orca-claude`, `codex` o `claude`. El runtime sigue el host que [herramientas del entorno](runtime-tools.md#detectar-y-elegir) identifica: T3, después Orca y después el cliente nativo. No atribuyas invocaciones de herramientas o lecturas de archivos a un skill que no se ejecutó.

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

Desde 0.9.0, registra nombres sin `peqa-`, desde 0.16.0 `memoria-guardar` en lugar de `memoria-recuerda`, y desde 0.18.0 los runtimes `orca-codex` y `orca-claude`. El lector conserva los eventos históricos con los nombres anteriores y los agrupa bajo el nombre actual; las consultas no reescriben el archivo y los nuevos eventos usan el nombre canónico. Un helper anterior no reconoce los nombres nuevos y rechaza el registro que los contenga; actualiza todas las instalaciones de Codex y Claude Code que usen el mismo repositorio.
