# Evals de activación

Miden si una petición en lenguaje natural carga el skill correcto. Lo que enruta es el campo `description` del frontmatter de cada `SKILL.md`; aquí se comprueba con sesiones reales de Claude Code sin interfaz (`claude -p`) y se comparan descripciones alternativas sin tocar el repositorio.

**Cada sesión llama al modelo y cuesta dinero.** `run` imprime cuántas sesiones va a lanzar y no empieza hasta que `--confirm-sessions N` coincide con ese número. `validate`, `split`, `score` y `select` no llaman al modelo.

## Consultas

`queries/<skill>.json` tiene unas veinte consultas por skill, la mitad debe activarlo y la otra mitad no, en español e inglés. Las que no deben activarlo son casi aciertos: peticiones que le tocan a un skill hermano (`expected`) o a ninguno (`expected: null`), con su `why`. Por ejemplo, «recuerda que…» activa `memoria-guardar` y «¿recuerdas…?» activa `memoria-extraer`. Las consultas no nombran el skill ni usan comandos: la invocación explícita no es lo que se mide. Todos los datos son sintéticos.

La partición 60/40 entre `train` y `holdout` no se guarda: sale de un hash del `id` y una semilla, estratificada por `should_trigger` e idioma. Añadir una consulta mueve como mucho la que está en el corte de su estrato.

## Usar

```sh
python3 tests/evals/triggering/trigger_eval.py validate
python3 tests/evals/triggering/trigger_eval.py split
python3 tests/evals/triggering/trigger_eval.py run --model claude-opus-5-5 --split train --dry-run
python3 tests/evals/triggering/trigger_eval.py run --model claude-opus-5-5 --split train --confirm-sessions 144
python3 tests/evals/triggering/trigger_eval.py score
python3 tests/evals/triggering/trigger_eval.py select
```

`run` lanza cada consulta `--reps` veces (3 por defecto) en un proyecto de ejemplo nuevo, con el plugin exportado a una copia y el mismo aislamiento que [el banco de medición](../../bench/README.md). Lee los eventos según llegan y detiene la sesión cuando ya se sabe el resultado: cargó un skill, terminó o hizo `--max-tools` llamadas a herramientas sin cargar ninguno. `--skill`, `--split` y `--variant` acotan el plan; `--jobs` fija cuántas sesiones corren a la vez. Las sesiones ya guardadas no se repiten. Los resultados van a `$PEQA_BENCH_OUT/triggering` o a una carpeta temporal; el script rechaza una carpeta dentro de un repositorio.

Un skill cuenta como cargado cuando el hilo principal llama a la herramienta `Skill` con su nombre o abre su `SKILL.md` con `Read` o desde la terminal. Lo que hagan los subagentes no cuenta.

## Comparar descripciones

`--descriptions variantes.json` recibe `{"variante": {"skill": "descripción nueva"}}`. Cada variante reescribe solo el `description` de esos skills en la copia exportada y corre únicamente sus conjuntos de consultas; `actual` es la descripción del repositorio.

Ajusta las descripciones mirando `train` y elige con `select`, que decide **solo por `holdout`**. Una variante gana a `actual` si su ventaja en `holdout` supera una desviación estándar de la exactitud por repetición (la mayor de las dos) con al menos tres repeticiones en cada lado. Lo demás es empate y se conserva `actual`.

## Qué informa `score`

Por modelo, skill, variante y partición: precisión, recall, exactitud y la exactitud por repetición con su desviación. Una consulta pasa si activó el skill en la mayoría de las repeticiones cuando debía, o en menos de la mitad cuando no. Las consultas que fallan aparecen con el primer skill que cargó cada sesión, para ver con cuál se confunde. `--json` da los mismos datos para otras herramientas.

## Límites

- Mide Claude Code. No ejecuta Codex, T3 ni Orca.
- Una sesión detenida al conocer el resultado no informa costo; el tope de cada una es `--budget`.
- Con `--max-skills 1` solo se registra el primer skill cargado. Súbelo para ver cadenas como `idea` seguido de `dirige`.
- El proyecto de ejemplo no tiene remoto. Los sustitutos de `gh`, `git` y `codex` del banco van primero en `PATH`, sin su guarda para shells de login: una sesión que llame a `gh` por su ruta completa o desde un shell de login antes de detenerse usaría el real.
- La forma de los eventos de `stream-json` se asume igual a la que lee el banco; revisa una muestra de los `.jsonl` guardados en la primera corrida.

`tests/test_trigger_eval.py` prueba el arnés sin llamar al modelo.
