# Puntuación con revisores

Revisado el 2026-11-03. Después de la crítica, dos revisores independientes puntúan la interfaz con la misma rúbrica: un subagente de Claude Opus y uno de Codex. Cargar `ui-design` autoriza a lanzarlos en cada cambio visual; su coste forma parte del encargo. Las notas son de los revisores: el autor decide qué hallazgos acepta e informa las notas tal como llegaron. Esta puntuación es aparte de [revisa](../../revisa/SKILL.md): no consume sus CR ni sustituye la revisión del código.

## Revisores

| Padre en | Claude Opus | Codex |
| --- | --- | --- |
| Claude Code, en cualquier host | `Agent` de propósito general con `model: "opus"` | En T3, `delegate_task`; en Orca, un worker de Orca; fuera de ambos, Codex CLI. Las dos formas están abajo |
| Codex, en cualquier host | En T3, `delegate_task` con el Opus más reciente del catálogo; en Orca, un worker de Orca; fuera de ambos, Claude Code CLI. Las dos formas están abajo | Subagente nativo, o `delegate_task` en T3 si el padre no usa ya esa configuración |

Codex usa el modelo y el esfuerzo de [revisa](../../revisa/references/reviewers.md): `gpt-6.1-sol` en `xhigh`. Opus usa el esfuerzo por defecto del host. En T3, `delegate_task` sigue [subagentes en T3](../../../references/runtime-tools.md#subagentes-en-t3), con un encargo nuevo por revisor y ronda.

Un revisor está disponible cuando su ruta existe y la ejecución termina con una respuesta completa. Usa solo CLIs ya instalados y autenticados: Codex se comprueba como indica [revisa](../../revisa/references/reviewers.md#agente-principal-en-claude-code-fuera-de-t3-code), y Claude Code con `claude --version` y `claude auth status`. Lanza los dos a la vez. Solo cuentan Claude Opus y Codex: si uno falta, puntúa el otro y el informe dice cuál faltó y por qué; sin ninguno, el informe declara pendiente la puntuación. Registra para cada uno el modelo y el esfuerzo solicitados y los efectivos que exponga el host.

`$NOTAS` y `$EVIDENCIA` son carpetas fuera del checkout, y `$UI_DESIGN` es la carpeta de este skill.

El host se elige como indica [herramientas del entorno](../../../references/runtime-tools.md#detectar-y-elegir): T3, después Orca y después el cliente nativo. En Orca, el revisor del otro proveedor es un worker nuevo por revisor y ronda, en el checkout del cambio y sin `--keep-open`; el del mismo proveedor sigue siendo el `Agent` o subagente nativo de la tabla. `$ORCA` es el ejecutable de `ORCA_CLI_COMMAND`. Con padre Claude Code, el worker es Codex; con padre Codex, es Claude:

```sh
# Padre Claude Code
"$ORCA" orchestration worker-start --agent codex --model gpt-6.1-sol --effort xhigh \
  --worktree "path:$REPO" --task-title "ui-design: puntuación" \
  --spec-file "$NOTAS/encargo.md" --json
# Padre Codex
"$ORCA" orchestration worker-start --agent claude --model opus \
  --worktree "path:$REPO" --task-title "ui-design: puntuación" \
  --spec-file "$NOTAS/encargo.md" --json
```

`worker-start` no adjunta imágenes. El encargo lista las rutas absolutas de cada captura en `$EVIDENCIA` y pide abrirlas con la herramienta de lectura de imágenes del agente. Si el revisor no puede verlas, por ejemplo porque su cliente no lee fuera del checkout, su nota no cuenta: repite ese revisor con la forma CLI de abajo, que adjunta las capturas, y el informe lo dice. Orca tampoco limita al worker a solo lectura: el encargo lo prohíbe y el padre compara HEAD y `git status --porcelain` antes y después, como en [revisa](../../revisa/references/reviewers.md#agente-principal-en-orca-fuera-de-t3-code). Para lanzarlos a la vez, inicia primero el worker y después el `Agent` o subagente nativo; cuando este termine, termina el turno hasta el `worker_done`, que trae las notas. Ajusta las opciones a la guía de `skills get orchestration` de la versión instalada. Si Orca no responde, o si `worker-start` falla o trae `failedStage`, no lo repitas y usa la forma CLI de abajo.

Fuera de T3 y de Orca, Codex desde Claude Code, con una opción `-i` por captura antes de `--model`:

```sh
codex -a never exec \
  -i "$EVIDENCIA/375.png" -i "$EVIDENCIA/1440.png" \
  --model gpt-6.1-sol -c 'model_reasoning_effort="xhigh"' \
  --sandbox read-only --ephemeral --cd "$REPO" --json --color never \
  --output-last-message "$NOTAS/codex.json" \
  - < "$NOTAS/encargo.md" > "$NOTAS/codex-eventos.jsonl" 2> "$NOTAS/codex-errores.log"
```

Claude Opus desde Codex, con herramientas de lectura:

```sh
cd "$REPO" && claude -p --model opus \
  --tools Read,Grep,Glob --allowedTools Read,Grep,Glob \
  --add-dir "$EVIDENCIA" --add-dir "$UI_DESIGN" --output-format json \
  < "$NOTAS/encargo.md" > "$NOTAS/opus.json" 2> "$NOTAS/opus-errores.log"
```

Comprobadas con Codex CLI 0.166.0 y Claude Code 2.1.314; ajusta las opciones a lo que indique la instalación real.

## Encargo

Cada revisor empieza con contexto fresco y solo lee: no edita, no captura y no delega. Su encargo lleva:

- el brief original y la frase de encuadre
- la ruta de cada captura con su ancho o dispositivo y, si las hay, su apariencia y su tamaño de texto; en un rediseño, también las de antes
- base y head, o el diff, y los archivos de tokens y componentes
- las secciones Rúbrica, Escala y Respuesta de este archivo, copiadas, y las rutas absolutas de [señales de UI generada](tells.md) y [textos de interfaz](copy.md)
- desde la segunda ronda, los hallazgos anteriores y lo que cambió

Sus conclusiones parten de la pantalla: el encargo deja fuera la autocrítica, las justificaciones del plan y las notas de otros revisores. Si le falta una captura para juzgar un criterio, lo dice en la evidencia de ese criterio.

## Rúbrica

Cada criterio recibe una nota entera de 0 a 10.

| Criterio | Qué se mira |
| --- | --- |
| Encargo | La persona puede hacer lo que pide el brief, y la acción o el dato principal se ve primero |
| Jerarquía | Orden de lectura, agrupación, alineación y ritmo del espaciado |
| Tipografía | Escala, pesos, interlineado, longitud de línea y cifras alineadas donde se comparan |
| Color | Roles coherentes, contraste del mínimo de calidad y apariencia oscura cuando existe |
| Sistema | Tokens y componentes del proyecto reutilizados; las pantallas existentes solo cambian donde lo piden el brief o el mínimo de calidad |
| Adaptación | Cada ancho, dispositivo y tamaño de texto capturado, sin cortes, solapes ni scroll horizontal |
| Interacción | Estados, foco visible, áreas táctiles y movimiento |
| Textos | Claros y específicos, según textos de interfaz |
| Carácter | La pantalla pertenece a este producto, sin señales de UI generada que el brief no pida |

Un criterio que no aplica, como Textos en un cambio que no toca texto, lleva `null` y el motivo, y queda fuera de la media.

## Escala

Las notas altas se ganan con evidencia. Ante la duda entre dos notas, pon la más baja.

- 10: ninguna captura tiene nada que mejorar en este criterio; resérvalo para lo excepcional
- 9: sin defectos visibles, solo detalles que hay que buscar
- 8: correcto, con un defecto visible menor
- 6 y 7: varios defectos visibles, o uno que entorpece el uso
- 4 y 5: falla en partes importantes
- 0 a 3: ausente o roto

Un criterio con algún hallazgo tiene como mucho 8, y cada nota de 8 o menos tiene al menos un hallazgo. Un 9 o un 10 explica en su evidencia por qué no merece uno menos; cualquier otra nota por debajo de 10 nombra lo que falta.

## Respuesta

Un único objeto JSON con los nueve criterios, con la evidencia y los hallazgos en el idioma del brief:

```json
{
  "notas": {
    "encargo": {"nota": 9, "evidencia": "375.png: el botón Reservar queda en la primera pantalla"},
    "textos": {"nota": null, "evidencia": "El cambio no toca textos"}
  },
  "hallazgos": [
    {"id": "V1", "criterio": "tipografia", "captura": "375.png", "problema": "…", "correccion": "…"}
  ]
}
```

Las claves de `notas` son los criterios en minúsculas y sin tildes: `encargo`, `jerarquia`, `tipografia`, `color`, `sistema`, `adaptacion`, `interaccion`, `textos` y `caracter`. Una respuesta completa tiene los nueve, cada uno con nota y evidencia, y cumple las reglas de la escala: un criterio con hallazgo y nota de 9 o 10 la deja incompleta.

## Resultado

Si una respuesta llega incompleta, relanza a ese revisor una vez con un encargo nuevo en la misma ronda; si vuelve a fallar, esa ronda cuenta como sin él.

La nota de cada revisor es la media de sus criterios con nota, y el resultado es la media de las notas de los revisores. Compara el valor sin redondear con los umbrales y muéstralo con dos decimales:

- más de 9, con todas las notas en 8 o más: prácticamente perfecto
- más de 8 y hasta 9, con todas las notas en 8 o más: bueno
- 8 o menos, o alguna nota por debajo de 8 de cualquier revisor: corrige y vuelve a puntuar

Un hallazgo de una nota por debajo de 8 solo se descarta con evidencia de las capturas, del código o del brief, y la ronda siguiente recibe el motivo. Si corregirlo depende de una decisión de la persona, como adónde lleva un botón, pregúntala si el host admite preguntas. Aplica entretanto los demás hallazgos aceptados, sin lanzar otra ronda; la puntuación queda abierta y el informe lo dice. Con la respuesta, la siguiente ronda continúa la cuenta.

Un incumplimiento del [mínimo de calidad](critique.md#mínimo-de-calidad) se corrige con cualquier resultado. Si los revisores difieren en más de 2 puntos en un criterio, mira las capturas de ese criterio y di en el informe qué lectura sigues y por qué; esa lectura decide qué hallazgos aceptas, y las notas quedan como llegaron.

## Rondas

1. Clasifica cada hallazgo como aceptado o descartado, con un motivo tomado de las capturas, del código o del brief. Un único editor aplica los aceptados. Tras cualquier corrección, también fuera de una ronda, repite las comprobaciones del paso 5 y las capturas afectadas.
2. Con la banda de corregir, puntúa de nuevo con encargos nuevos.
3. Con la banda de bueno o de prácticamente perfecto, la puntuación termina. Las correcciones posteriores se marcan como no puntuadas.
4. Hay tres rondas como máximo por cambio. Si la tercera no cierra, corrige igualmente los hallazgos aceptados, márcalos como no puntuados y deja a la persona decidir si acepta el resultado o pide más rondas; solo ella amplía el máximo.

El informe da, por ronda, la nota de cada criterio y revisor, la media de cada revisor, el resultado y su banda, el modelo y el esfuerzo solicitados y efectivos, y cada hallazgo con su decisión. Un revisor ausente aparece con su motivo.
