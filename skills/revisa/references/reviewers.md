# Selección y ejecución del revisor

Elige la sección según el entorno del agente principal que coordina la revisión. Cada sección indica cómo ejecutar al revisor desde ese entorno.

La preferencia fija es `gpt-6.1-sol` en `xhigh`. Esto expresa nuestra elección, no una búsqueda del modelo más reciente. Registra selección solicitada, selección admitida y la identidad de ejecución que exponga el host; no infieras identidad de lo que el modelo dice de sí mismo.

## Agente principal en T3 Code

Lee primero la selección, preguntas pendientes y ciclo de tareas de [herramientas del entorno](../../../references/runtime-tools.md). Usa el catálogo y la ruta de orquestación del host, también cuando el padre sea Claude. Consulta `orchestrator_capabilities` según su política de una consulta por hilo; no la repitas si ya hay un resultado válido para esa ejecución.

Selecciona el proveedor que realmente ofrezca `gpt-6.1-sol`, verifica que acepte `xhigh` y envía las opciones con los IDs de configuración que exponga el esquema, dentro de `target.options`. Para esta configuración solicitada utiliza `delegate_task` con rol de revisión y brief de solo lectura. Cada pasada es una nueva tarea. Conserva taskId y sigue su `next`; el padre retoma la adjudicación cuando llegue la finalización.

Una ruta deshabilitada o rechazada en T3 no se elude con un CLI. Si la ruta Sol no está disponible, el fallback ya autorizado por este skill es un revisor independiente del motor actual a través de una ruta que el host permita. Respeta sus reglas para elegir delegación T3 o subagente nativo. Informa la limitación y el modelo efectivo. Si tampoco existe esa ruta, informa revisión incompleta.

## Agente principal en Orca, fuera de T3 Code

Aplica esta sección, con Claude o Codex como padre, cuando [herramientas del entorno](../../../references/runtime-tools.md#detectar-y-elegir) identifica Orca. Es la ruta preferida dentro de Orca porque la revisión queda visible como un worker. Antes de reservar comprueba que `"$ORCA" status` responde, donde `$ORCA` es el ejecutable de `ORCA_CLI_COMMAND`; carga la guía con `"$ORCA" skills get orchestration`, y verifica que Codex está instalado y autenticado con `codex --version` y `codex login status`, sin leer archivos de autenticación. Si algo falla, usa la sección del cliente del padre sin consumir una pasada por Orca.

Lanza cada pasada como un worker nuevo en el checkout del padre:

```sh
"$ORCA" orchestration worker-start --agent codex \
  --model gpt-6.1-sol --effort xhigh \
  --worktree current --task-title "revisa: PR $PR_NUMBER" \
  --spec-file "$REVIEW_PROMPT" --json
```

`$REVIEW_PROMPT` vive fuera del código revisado. Ajusta las opciones a la guía de `skills get orchestration` de la versión instalada. Un `worker-start` iniciado consume la pasada aunque falle después. Si su recibo trae `failedStage`, no lo repitas: sigue la recuperación de esa guía y, si queda presupuesto, reserva otra pasada para la ruta del cliente del padre.

Orca no limita al worker a solo lectura, así que el brief lo prohíbe: no edita, no hace commit ni push, no publica comentarios ni revisiones en GitHub y no inicia workers ni subagentes. Antes de lanzarlo, el padre anota HEAD y `git status --porcelain` del checkout y de sus submódulos, y no edita mientras el revisor trabaja. Si ejecuta pruebas que el revisor pide, anota los archivos que esas ejecuciones generan. Al recibir `worker_done` repite la comprobación. Si algo cambió y no viene de esas ejecuciones, la pasada no vale como revisión independiente: informa qué cambió, consérvalo sin restaurarlo por tu cuenta y decide con el usuario.

El informe llega en el `worker_done` del revisor; si el aviso indica un `check`, ejecútalo para leerlo completo. Registra el modelo y el esfuerzo solicitados y lo que `worker-show` exponga del efectivo; si no lo expone, decláralo desconocido. Un worker que se detiene sin `worker_done`, un timeout o un informe incompleto no constituyen aprobación. Una comprobación posterior es otro worker, nunca un `send` al anterior.

Si Orca no responde, sigue la sección del cliente del padre: subagente nativo en Codex, o `codex exec` desde Claude Code con su fallback.

## Agente principal en Codex, fuera de T3 Code

Usa un subagente nativo con selección explícita de `gpt-6.1-sol` y `xhigh` cuando esos controles estén disponibles. Si el cliente no puede seleccionar o ejecutar la combinación, utiliza el fallback independiente del motor actual. Registra el esfuerzo como desconocido si el host no lo expone; no lo anuncies como xhigh.

## Agente principal en Claude Code, fuera de T3 Code

Primero comprueba si hay una ruta nativa verificada al modelo exacto. Un `Agent` de Claude no es un revisor Sol. Si no hay ruta nativa a Sol, usa un Codex CLI ya instalado y autenticado; no instales otro proveedor, inicies login ni pidas credenciales como parte de una revisión.

Comprueba `codex --version`, `codex exec --help` y `codex login status` sin leer archivos de autenticación. Esta forma se verificó con CLI 0.164.0; ajusta las opciones solo a lo que indique la instalación real:

```sh
codex -a never exec \
  --model gpt-6.1-sol \
  -c 'model_reasoning_effort="xhigh"' \
  --sandbox read-only --ephemeral \
  --cd "$REVIEW_REPO" --json --color never \
  --output-last-message "$REVIEW_REPORT" \
  - < "$REVIEW_PROMPT" > "$REVIEW_EVENTS" 2> "$REVIEW_ERRORS"
```

El padre prepara un prompt fresco de solo lectura, con fuentes y requisitos, y rutas de resultados fuera del código revisado. Mantén las reglas del proyecto y limita conectores y herramientas del revisor a inspección autorizada. El sandbox de shell no concede permiso para mutaciones mediante conectores.

Inspecciona exit code, integridad del informe, eventos y revisión cubierta. Configurar modelo y esfuerzo demuestra qué se solicitó; si el backend no expone identidad de ejecución, declara ese límite. Un fallo, timeout o informe incompleto no constituye aprobación.

Si falta el binario, autenticación, modelo, esfuerzo o ejecución, usa un subagente fresco del motor actual. Este fallback está autorizado por el usuario y no requiere otra pregunta. Si el intento Sol ya empezó, reserva otra pasada para el fallback. Si no queda presupuesto, entrega revisión incompleta y evidencia del padre.

## Contexto que recibe el revisor

Incluye objetivo y requisitos originales, ruta de fuentes, base y revisión exactas, diff y archivos nuevos, alcance, mapa de repositorios y checks observados o pendientes. Pide la búsqueda de pruebas disponibles, solicitudes de ejecución al padre, análisis de blast radius y veredicto según [pruebas e impacto](validation.md), además de hallazgos materiales con evidencia, condiciones, corrección mínima y la pantalla o el flujo que hace visible cada uno. Si el cambio modifica comportamiento, pide un borrador Mermaid del flujo antes/después que el padre verificará. Incluye [los controles de seguridad](security.md), las ediciones y fuentes contrastadas y los mínimos aplicables; pide evidencia suficiente para que el padre prepare [el consolidado](report.md). La revisión es de solo lectura, sin más agentes, edición ni acciones en GitHub. Para una comprobación posterior añade hallazgos abiertos y cambios desde la pasada anterior, manteniendo la misma base del cambio.
