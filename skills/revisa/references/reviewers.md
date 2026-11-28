# Selección y ejecución del revisor

Elige primero el modelo revisor y la profundidad (`lite` o `deep`), y luego aplica la sección correspondiente al entorno del agente principal que coordina la revisión. Registra siempre el modelo y el esfuerzo solicitados, los admitidos y la identidad efectiva que exponga el host; nunca infieras identidad a partir de lo que el modelo diga de sí mismo.

## Selección de modelo y profundidad

`revisa` ofrece cuatro modelos revisores y dos profundidades:

| Modelo | Cuándo se recomienda |
| --- | --- |
| **Astra 6.2** | Backend, lógica de negocio compleja, esquemas, integridad de datos y seguridad, salvo que la sesión actual ya corra en Astra 6.2. |
| **Opus 5.5** | Uso general, frontend y full-stack; alternativa sólida para backend al diversificar respecto al modelo de la sesión. |
| **Neon 4** | Uso general, frontend y full-stack; alternativa sólida para backend al diversificar respecto al modelo de la sesión. |
| **Sol 6.2** | Tareas simples, cambios pequeños y revisiones ligeras. |

Profundidades disponibles:

| Profundidad | Cobertura | Cuándo se recomienda |
| --- | --- | --- |
| **`lite`** | Requisitos funcionales, defectos materiales, regresiones, casos borde y pruebas. Omite la auditoría completa OWASP/NIST SSDF salvo que se detecte un defecto de seguridad obvio. | Cambios pequeños, directos o de bajo riesgo. |
| **`deep`** | Todo lo de `lite` más seguridad dedicada (OWASP Top 10, NIST SSDF, autenticación, autorización, aislamiento de tenants, concurrencia, integridad de datos, secretos y dependencias) y blast radius completo. | Backend, autenticación, dinero o contabilidad, migraciones, cambios multirrepositorio o alto riesgo. |

### Regla de diversidad con la sesión actual

1. Cuando el host (Orca o T3 Code) exponga el modelo de la sesión actual, recomienda un modelo **distinto al de la sesión** que además encaje con el dominio y la complejidad del cambio. Por ejemplo, en backend con sesión Opus 5.5 o Neon 4 se recomienda Astra 6.2; si la sesión ya corre en Astra 6.2, se diversifica a Opus 5.5 (con Neon 4 como alternativa inmediata). En frontend o uso general con sesión Opus 5.5 se recomienda Neon 4, y viceversa.
2. Si el host no expone el modelo de la sesión actual, decláralo de forma expresa y recomienda solo por dominio y complejidad.
3. Usa el helper incluido para calcular de forma determinista el orden de opciones y la recomendación:

```sh
python3 "$REVIEW_PLAN_SCRIPT" recommend \
  --domain backend --complexity standard --risk auth \
  --session-model "$SESSION_MODEL"
```

`REVIEW_PLAN_SCRIPT` apunta a `scripts/review_plan.py` de este skill. Acepta `--domain` (`backend`, `frontend`, `fullstack`, `simple`, `general`), `--complexity` (`simple`, `standard`, `complex`), `--risk` repetible (`auth`, `money`, `ledger`, `migration`, `security`, `multi_repo`, `concurrency`, `schema`, `high_risk`), `--session-model`, `--requested-model` y `--requested-depth`.

### Pregunta en una sola ronda

Pregunta al usuario qué modelo y qué profundidad quiere en **una única ronda**, usando [la interfaz de preguntas](../../../references/runtime-tools.md#preguntas-al-usuario), colocando la opción recomendada primero en cada campo. Si el usuario ya indicó el modelo o la profundidad en su pedido, respeta esa elección y pregunta solo lo que falte; si indicó ambos, no preguntes. Esta selección no consume rondas de `idea` ni pasadas de revisión.

En una ejecución no interactiva donde nadie puede responder, aplica la recomendación de modelo y profundidad y decláralo en la trazabilidad del informe.

Resuelve `$REVIEW_AGENT`, `$REVIEW_MODEL` y `$REVIEW_EFFORT` a partir del catálogo vivo del host elegido (catálogo de T3, guía instalada de Orca o CLIs disponibles). No inventes identificadores de modelo ni aliases de esfuerzo no confirmados por el host.

## Agente principal en T3 Code

Lee primero la selección, preguntas pendientes y ciclo de tareas de [herramientas del entorno](../../../references/runtime-tools.md). Usa el catálogo y la ruta de orquestación del host, también cuando el padre sea Claude. Consulta `orchestrator_capabilities` según su política de una consulta por hilo; no la repitas si ya hay un resultado válido para esa ejecución.

Localiza en el catálogo el proveedor que ofrezca el modelo elegido (`$REVIEW_MODEL`), verifica las opciones de esfuerzo admitidas (`$REVIEW_EFFORT`) y envía los IDs exactos dentro de `target.providerInstanceId`, `target.model` y `target.options`. Utiliza `delegate_task` con rol de revisión y brief de solo lectura. Cada pasada es una nueva tarea. Conserva `taskId` y sigue su `next`; el padre retoma la adjudicación cuando llegue la finalización.

Una ruta deshabilitada o rechazada en T3 no se elude con un CLI. Si la ruta del modelo elegido no está disponible, el fallback ya autorizado por este skill es un revisor independiente del motor actual a través de una ruta que el host permita. Respeta sus reglas para elegir delegación T3 o subagente nativo. Informa la limitación, el modelo solicitado y el modelo efectivo. Si tampoco existe esa ruta, informa revisión incompleta.

## Agente principal en Orca, fuera de T3 Code

Aplica esta sección cuando [herramientas del entorno](../../../references/runtime-tools.md#detectar-y-elegir) identifica Orca. Es la ruta preferida dentro de Orca porque la revisión queda visible como un worker. Antes de reservar comprueba que `"$ORCA" status` responde, donde `$ORCA` es el ejecutable de `ORCA_CLI_COMMAND`; carga la guía con `"$ORCA" skills get orchestration`, y verifica que el agente seleccionado (`$REVIEW_AGENT`) está disponible y autenticado sin leer archivos de credenciales. Si algo falla, usa la sección del cliente del padre sin consumir una pasada por Orca.

Lanza cada pasada como un worker nuevo en el checkout revisado, `$REVIEW_REPO`, que puede no ser el workspace de Orca de la sesión:

```sh
"$ORCA" orchestration worker-start --agent "$REVIEW_AGENT" \
  --model "$REVIEW_MODEL" --effort "$REVIEW_EFFORT" \
  --worktree "path:$REVIEW_REPO" --task-title "revisa ($REVIEW_DEPTH): PR $PR_NUMBER" \
  --spec-file "$REVIEW_PROMPT" --json
```

`$REVIEW_PROMPT` vive fuera del código revisado. Omite `--effort` si el agente o la versión de Orca no admiten ese parámetro según `skills get orchestration`. Un `worker-start` iniciado consume la pasada aunque falle después. Si su recibo trae `failedStage`, no lo repitas: sigue la recuperación de esa guía y, si queda presupuesto, reserva otra pasada para la ruta del cliente del padre.

Orca no limita al worker a solo lectura, así que el brief lo prohíbe: no edita, no hace commit ni push, no publica comentarios ni revisiones en GitHub y no inicia workers ni subagentes. Antes de lanzarlo, el padre anota HEAD y `git status --porcelain` del checkout y de sus submódulos, y no edita mientras el revisor trabaja. Si ejecuta pruebas que el revisor pide, anota los archivos que esas ejecuciones generan. Al recibir `worker_done` repite la comprobación. Si algo cambió y no viene de esas ejecuciones, la pasada no vale como revisión independiente: informa qué cambió, consérvalo sin restaurarlo por tu cuenta y decide con el usuario.

El informe llega en el `worker_done` del revisor; si el aviso indica un `check`, ejecútalo para leerlo completo. Registra el modelo y el esfuerzo solicitados y lo que `worker-show` exponga del efectivo; si no lo expone, decláralo desconocido. Un worker que se detiene sin `worker_done`, un timeout o un informe incompleto no constituyen aprobación. Una comprobación posterior es otro worker, nunca un `send` al anterior.

Si Orca no responde, sigue la sección del cliente del padre con el modelo elegido o su fallback autorizado.

## Agente principal en Codex, fuera de T3 Code

Usa un subagente nativo con selección explícita de `$REVIEW_MODEL` y `$REVIEW_EFFORT` cuando el cliente los admita. Si el modelo elegido pertenece a otro proveedor y hay un CLI ya instalado y autenticado (por ejemplo `claude -p` con herramientas de solo lectura `Read,Grep,Glob`), puedes usarlo sin instalar proveedores ni iniciar login. Si el cliente no puede ejecutar el modelo seleccionado, utiliza el fallback independiente del motor actual y decláralo. Registra el esfuerzo como desconocido si el host no lo expone.

## Agente principal en Claude Code, fuera de T3 Code

Primero comprueba si hay una ruta nativa verificada al modelo elegido (`Agent` cuando corresponda a un modelo Claude admitido por el host). Si el modelo elegido pertenece a otro proveedor y hay un CLI ya instalado y autenticado (por ejemplo Codex CLI comprobado con `codex --version`, `codex exec --help` y `codex login status`, sin leer archivos de autenticación), ejecútalo en modo solo lectura; no instales otro proveedor, inicies login ni pidas credenciales como parte de una revisión.

Ejemplo parametrizado con Codex CLI (ajusta las opciones a lo que indique la instalación real):

```sh
codex -a never exec \
  --model "$REVIEW_MODEL" \
  -c "model_reasoning_effort=\"$REVIEW_EFFORT\"" \
  --sandbox read-only --ephemeral \
  --cd "$REVIEW_REPO" --json --color never \
  --output-last-message "$REVIEW_REPORT" \
  - < "$REVIEW_PROMPT" > "$REVIEW_EVENTS" 2> "$REVIEW_ERRORS"
```

El padre prepara un prompt fresco de solo lectura, con fuentes y requisitos, y rutas de resultados fuera del código revisado. Mantén las reglas del proyecto y limita conectores y herramientas del revisor a inspección autorizada. El sandbox de shell no concede permiso para mutaciones mediante conectores.

Inspecciona exit code, integridad del informe, eventos y revisión cubierta. Configurar modelo y esfuerzo demuestra qué se solicitó; si el backend no expone identidad de ejecución, declara ese límite. Un fallo, timeout o informe incompleto no constituye aprobación.

Si falta el binario, autenticación, modelo, esfuerzo o ejecución, usa un subagente fresco del motor actual. Este fallback está autorizado por el usuario y no requiere otra pregunta. Si el intento anterior ya empezó, reserva otra pasada para el fallback. Si no queda presupuesto, entrega revisión incompleta y evidencia del padre.

## Contexto que recibe el revisor

Incluye objetivo y requisitos originales, profundidad elegida (`lite` o `deep`), ruta de fuentes, base y revisión exactas, diff y archivos nuevos, alcance, mapa de repositorios y checks observados o pendientes. Adjunta el [mapa de partida del blast radius](validation.md#analizar-blast-radius) que ejecutó el padre. Pide la búsqueda de pruebas disponibles, solicitudes de ejecución al padre, análisis de blast radius y veredicto según [pruebas e impacto](validation.md), además de hallazgos materiales con ID estable, severidad, `archivo:línea`, evidencia, condiciones, impacto, corrección mínima y la pantalla o el flujo que hace visible cada uno. Si el cambio modifica comportamiento, pide un borrador Mermaid del flujo antes/después que el padre verificará. En `deep`, incluye [los controles de seguridad](security.md), las ediciones y fuentes contrastadas y los mínimos aplicables; en `lite`, indica que se omite la auditoría completa OWASP/NIST SSDF salvo que aparezca un defecto de seguridad obvio. Pide evidencia suficiente para que el padre prepare [el consolidado](report.md). La revisión es de solo lectura, sin más agentes, edición ni acciones en GitHub. Para una comprobación posterior añade hallazgos abiertos y cambios desde la pasada anterior, manteniendo la misma base del cambio.
