# Selección del revisor

La preferencia fija es `gpt-6.1-sol` en `xhigh`. Esto expresa nuestra elección, no una búsqueda del modelo más reciente. Registra selección solicitada, selección admitida y la identidad de ejecución que exponga el host; no infieras identidad de lo que el modelo dice de sí mismo.

## En T3 Code

Lee primero la selección, preguntas pendientes y ciclo de tareas de [herramientas del entorno](../../../references/runtime-tools.md). Usa el catálogo y la ruta de orquestación del host, también cuando el padre sea Claude. Consulta `orchestrator_capabilities` según su política de una consulta por hilo; no la repitas si ya hay un resultado válido para esa ejecución.

Selecciona el proveedor que realmente ofrezca `gpt-6.1-sol`, verifica que acepte `xhigh` y envía las opciones con los IDs de configuración que exponga el esquema, dentro de `target.options`. Para esta configuración solicitada utiliza `delegate_task` con rol de revisión y brief de solo lectura. Cada pasada es una nueva tarea. Conserva taskId y sigue su `next`; el padre retoma la adjudicación cuando llegue la finalización.

Una ruta deshabilitada o rechazada en T3 no se elude con un CLI. Si la ruta Sol no está disponible, el fallback ya autorizado por este skill es un revisor independiente del motor actual a través de una ruta que el host permita. Respeta sus reglas para elegir delegación T3 o subagente nativo. Informa la limitación y el modelo efectivo. Si tampoco existe esa ruta, informa revisión incompleta.

## Fuera de T3, padre Codex

Usa un subagente nativo con selección explícita de `gpt-6.1-sol` y `xhigh` cuando esos controles estén disponibles. Si el cliente no puede seleccionar o ejecutar la combinación, utiliza el fallback independiente del motor actual. Registra el esfuerzo como desconocido si el host no lo expone; no lo anuncies como xhigh.

## Fuera de T3, padre Claude Code

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

## Brief de revisión

Incluye objetivo y requisitos originales, ruta de fuentes, base y revisión exactas, diff y archivos nuevos, alcance, mapa de repositorios y checks observados o pendientes. Pide la búsqueda de pruebas disponibles, solicitudes de ejecución al padre, análisis de blast radius y veredicto según [pruebas e impacto](validation.md), además de hallazgos materiales con evidencia, condiciones y corrección mínima. La revisión es de solo lectura, sin más agentes, edición ni acciones en GitHub. Para una comprobación posterior añade hallazgos abiertos y cambios desde la pasada anterior, manteniendo la misma base del cambio.
