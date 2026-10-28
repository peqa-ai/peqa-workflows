# Validadores portables y hooks opcionales

La ruta normal ejecuta los scripts directamente. Los hooks añaden comprobaciones cuando el host los admite; su ausencia, timeout o rechazo no elimina la validación del skill. Requisitos: Python 3.10+, Git y macOS/Linux, sin servicios ni dependencias nuevas.

Resuelve `PEQA_PLUGIN` como ruta absoluta de esta instalación y `PEQA_REPO` como raíz elegida del proyecto. Usa artefactos privados por revisión, fuera del workingtree:

```sh
python3 "$PEQA_PLUGIN/scripts/peqa_hooks.py" artifact-dir --repo "$PEQA_REPO"
```

El resultado indica `<git-common-dir>/peqa/checks`. Elige dentro un nombre único para `PEQA_REPORT`; varios worktrees comparten ese almacén. Los hooks se registran por sesión y raíz del checkout, no globalmente.

## Validar el consolidado y su evidencia

Al fijar la revisión, antes de ejecutar las pruebas, crea el registro inicial. El template comienza honestamente incompleto:

```sh
python3 "$PEQA_PLUGIN/scripts/review_checks.py" template --repo "$PEQA_REPO" --language es > "$PEQA_REPORT"
```

Completa el JSON con evidencia observada y decisiones del padre. Usa `en` para inglés. El contrato `schema_version: 1` incluye:

- `recommendation`: `approval_recommended`, `changes_required` o `review_incomplete`; `minimums`: `met`, `not_met` o `not_verified`.
- `requester`: nombre confirmado o `null`; `reason` e `impact`: explicación y alcance causal.
- `criteria`: `requirements`, `tests`, `security`, `compatibility`; cada uno tiene `status` y `evidence`. Los estados añaden `not_applicable`, que necesita justificación.
- `findings`: objetos con `id`, `material`, `status` (`open`, `resolved`, `dismissed`) y `evidence`.
- `tests`: objetos con `command`, `cwd` relativo al proyecto, `status` (`passed`, `failed`, `not_run`, `partial`, `no_tests`) y `evidence`. Incluye resultados y pendientes relevantes.
- `security`: listas de texto `standards`, `controls`, `limitations`, con versiones, IDs, resultados y fuentes según [seguridad del review](../skills/revisa/references/security.md).
- `trace`: listas de texto `models` y `cr`, y texto `route`; distingue configuración solicitada y efectiva, contador por PR y sus fuentes.
- `scope`: captura generada por el helper. Conserva este objeto junto a la evidencia que se obtuvo sobre ese estado.

Después de integrar las conclusiones, ejecuta:

```sh
python3 "$PEQA_PLUGIN/scripts/review_checks.py" validate --repo "$PEQA_REPO" --report "$PEQA_REPORT"
python3 "$PEQA_PLUGIN/scripts/review_checks.py" render --repo "$PEQA_REPO" --report "$PEQA_REPORT"
```

`validate` devuelve `valid` y códigos de error; exit 0 significa registro coherente y vigente, no aprobación. Un informe que requiere cambios o declara revisión incompleta también puede ser válido. `render` valida antes de producir el [consolidado](../skills/revisa/references/report.md), conservando la recomendación y sus límites. Entrega ese resultado o adapta su presentación manteniendo los mismos datos.

La captura compara HEAD, índice, archivos rastreados y no rastreados, y submódulos anidados con sus punteros y HEAD reales. Usa hashes; no imprime contenidos. Al terminar vuelve a comprobar enumeraciones, estados Git e identidades de archivos y repositorios, incluidos hijos ya recorridos; si detecta una edición durante la lectura devuelve `SNAPSHOT_CHANGED_DURING_READ`. No bloquea a otros procesos ni garantiza una captura atómica del sistema de archivos: coordina las escrituras y valida de nuevo antes de usar el informe. Submódulos ausentes, archivos inseguros o límites de lectura dejan cobertura incompleta. No inicializa hijos ni ejecuta los comandos declarados en el informe. Archivos ignorados por Git y repositorios externos están fuera de la captura: si afectan a las pruebas, conserva su evidencia aparte y declara esa limitación material. Para otros repositorios independientes usa un registro por raíz y consolida sus resultados.

Si cambia la captura, el registro queda obsoleto. No reemplaces `scope` para conservar tests verdes de una revisión anterior: vuelve a ejecutar o justificar las comprobaciones pertinentes, crea una nueva captura y liga cada resultado al estado realmente probado. Un fichero JSON editable no prueba que un comando se ejecutó, que la evidencia es suficiente o que el análisis de seguridad es correcto; el padre sigue comprobándolo. Si el helper falla, informa validación automatizada pendiente y entrega la evidencia disponible; no declares que pasó.

## Presupuesto antes de despachar

Después de reservar una única vez con [el controlador existente](../skills/revisa/references/budget.md), verifica el recibo inmediatamente antes de despachar:

```sh
python3 "$PEQA_PLUGIN/skills/revisa/scripts/review_budget.py" verify \
  --repo "$PEQA_REPO" --pr-url "$PEQA_PR_URL" --head "$PEQA_HEAD" --token "$PEQA_TOKEN"
python3 "$PEQA_PLUGIN/skills/revisa/scripts/review_budget.py" claim \
  --repo "$PEQA_REPO" --pr-url "$PEQA_PR_URL" --head "$PEQA_HEAD" --token "$PEQA_TOKEN"
```

Para un cambio sin PR usa `--id change-nombre`. `verify` es de solo lectura: exige reserva pendiente del mismo head y sin despacho admitido, respeta el máximo de tres y no crea registros ni consume otra pasada. `claim` admite atómicamente un único despacho por token, compartido entre sesiones y worktrees, sin incrementar el contador. Si falla cualquiera, no despaches al revisor. Conserva el consumo de una reserva ya hecha aunque falle el envío; una admisión fallida o parcial no se reinicia. Ningún comando inicia revisores ni sustituye `finish`.

En la ruta directa, incluyendo Codex, llama `claim` antes de enviar. Si usas el guard de hooks de Claude, deja que ese guard haga `claim` al interceptar: no hagas ambas admisiones. En un encargo multirrepositorio, verifica todas las reservas antes de admitirlas; si una admisión falla tras otras exitosas, marca el intento fallido y conserva los consumos.

## Activar hooks por proyecto

La distribución no declara hooks en los manifiestos ni incluye un `hooks/hooks.json` autodetectable. Instalar el plugin deja estos adaptadores inactivos. Genera una configuración revisable sin escribir ajustes del cliente:

```sh
python3 "$PEQA_PLUGIN/scripts/peqa_hooks.py" config --repo "$PEQA_REPO" --runtime claude
python3 "$PEQA_PLUGIN/scripts/peqa_hooks.py" config --repo "$PEQA_REPO" --runtime codex
```

Integra el objeto `hooks` de Claude en `.claude/settings.local.json`, preservando el resto de ajustes y hooks existentes. En Codex, el JSON puede integrarse en `.codex/hooks.json` si esa instalación lo soporta. Revisa confianza y carga con `/hooks`; no saltes la confianza del host ni habilites características globales por cuenta propia. Las rutas generadas son absolutas y citadas para shell; regenera la configuración si cambia la ubicación de la instalación.

El modo inicial es `warn`. Claude permite generar `--mode enforce`, que puede negar un despacho registrado sin reserva válida o solicitar una corrección del informe al cerrar. Codex **siempre usa `warn`**, incluso si se solicita `enforce`: no bloquea herramientas ni crea continuaciones. Su adaptador es experimental hasta validarlo en la instalación real; prefiere admisión directa y deja el guard sin armar. En T3, comprueba la carga y los eventos del proveedor concreto; no supongas que las herramientas de orquestación pasan por el hook.

`SessionStart` informa el ID de sesión como dato. Usa ese ID real en `PEQA_SESSION`; no inventes un ID de hilo T3 o un identificador de tarea como sustituto. Si no lo obtienes, conserva la ruta directa.

Para comprobar el cierre de un review ya preparado:

```sh
python3 "$PEQA_PLUGIN/scripts/peqa_hooks.py" arm --repo "$PEQA_REPO" \
  --session-id "$PEQA_SESSION" --report "$PEQA_REPORT"
```

`Stop` valida únicamente ese registro. Un resultado válido desarma el cierre. Si es inválido, Claude en `enforce` solicita como máximo una continuación por registro; una segunda evaluación avisa y desarma. Codex avisa y desarma desde la primera. El hook no inicia agentes, pruebas, scanners ni memoria automática. Un error del adaptador avisa y deja continuar: la obligación de ejecutar la validación directa permanece.

Para reforzar un despacho, prepara un JSON privado con las reservas de todos los PRs que cubrirá. Cada entrada usa una ruta relativa a la raíz elegida:

```json
[{"repo":".","identity":"https://github.com/equipo/proyecto/pull/42","head":"SHA_RESERVADO","token":"TOKEN_DE_RESERVA"}]
```

```sh
python3 "$PEQA_PLUGIN/scripts/peqa_hooks.py" guard --repo "$PEQA_REPO" \
  --session-id "$PEQA_SESSION" --tool-name "$PEQA_REVIEW_TOOL" --reservations "$PEQA_RESERVATIONS"
```

Arma el guard justo antes de la llamada de revisión. `PEQA_REVIEW_TOOL` debe ser el nombre exacto que emite el host, por ejemplo `Agent` o el nombre MCP real de `delegate_task`. La primera llamada coincidente admite las reservas con `claim`; otra con el mismo guard se señala como repetida. Rearmar o cambiar de sesión no permite reutilizar tokens ya admitidos. El guard no adivina la intención del prompt ni garantiza interceptar rutas que el host omita. En `warn` informa fallos pero no puede impedir la herramienta: respeta el resultado y usa la ruta directa si necesitas una admisión comprobada antes de enviar. Tras despachar, antes de usar esa herramienta para otro trabajo, limpia el registro; arma el cierre del informe después:

```sh
python3 "$PEQA_PLUGIN/scripts/peqa_hooks.py" clear --repo "$PEQA_REPO" --session-id "$PEQA_SESSION"
```

`clear` retira guard y cierre de esa sesión, sin borrar informes ni modificar el presupuesto. Para desactivar la integración retira solo estas entradas de hooks del cliente. Los tests del paquete simulan eventos y usan repositorios reales temporales; no demuestran carga entre sesiones reales en los tres clientes.

Fuentes de contrato consultadas el 2026-10-27: [hooks de Claude Code](https://code.claude.com/docs/en/hooks), [hooks de Codex](https://learn.chatgpt.com/docs/hooks) y [distribución de hooks de plugins](https://developers.openai.com/plugins/build/plugins#bundled-mcp-servers-and-lifecycle-hooks). Comprueba la instalación efectiva antes de activar.
