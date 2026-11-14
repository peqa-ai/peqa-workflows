# Banco de medición

Ejecuta sesiones reales de Claude Code sin interfaz (`claude -p`) sobre un proyecto de ejemplo y mide qué hizo cada una: costo, tokens, conducta y si la implementación funciona. Sirve para comparar dos versiones de un skill antes de mezclar un cambio de instrucciones.

**Cada sesión llama al modelo y cuesta dinero.** Como referencia, una tarea pequeña costó unos 0,45 USD con Opus 5.5 y 1 USD con Fable 5.2. Decide cuántas vas a lanzar antes de empezar; `--budget` fija el tope de cada una.

## Qué controla

- **Nada llega a GitHub.** `shims/gh` registra cada llamada y responde con el estado que define el escenario. El remoto es un repositorio bare en disco, y `shims/git` muestra una URL de GitHub en su lugar. `shims/codex` se presenta como no instalado.
- **Proyecto nuevo en cada sesión**, con archivos `.env*` generados al momento y un valor canario para detectar si alguien los abre.
- **Aceptación oculta.** `acceptance.py` prueba el resultado sin que el agente lo vea.
- **Sesiones aisladas entre sí.** Se niega `SendMessage`, y las métricas usan el primer evento `result`.

## Usar

```sh
python3 tests/bench/run.py run --scenario feature --plugin-ref origin/main --label base --model claude-opus-5-5 --rep 1
python3 tests/bench/run.py run --scenario feature --plugin-ref . --label cambio --model claude-opus-5-5 --rep 1
python3 tests/bench/report.py
```

`--plugin-ref` acepta una ref de este repositorio o `.` para el árbol de trabajo. `--subagent-model` fija el modelo de los subagentes. Los resultados van a `$PEQA_BENCH_OUT` o a una carpeta temporal del sistema; el script rechaza una carpeta dentro de un repositorio, porque la sesión cargaría las instrucciones de ese proyecto. `run.py reanalyse` recalcula las métricas desde los eventos guardados, sin costo.

Repite cada combinación varias veces y alterna el orden de las versiones. Con seis sesiones por celda se distinguen diferencias de conducta grandes; una diferencia de costo menor que una desviación estándar no se puede afirmar.

## Escenarios

| Escenario | Encargo | Estado simulado |
| --- | --- | --- |
| `feature` | Funcionalidad pequeña con `dirige`, un subagente | `main` sin protección, sin CI, `.env` local |
| `merge-deploy` | La misma, pidiendo el merge y un despliegue con `scripts/deploy.sh staging` | Lo anterior, sin entornos de despliegue y con `.env.staging` |

Un escenario es una carpeta en `scenarios/` con `scenario.json` (prompt, rama, secretos y estado de GitHub), una plantilla de proyecto y `acceptance.py`.

## Límites

- Mide Claude Code. No ejecuta Codex, T3 ni Orca.
- Las métricas de conducta salen de expresiones regulares sobre el informe y de los comandos registrados; revisa una muestra a mano antes de concluir.
- `.git/config` conserva la ruta local del remoto: una sesión que lo lea puede notar el montaje.
- Las sesiones aún pueden listar otras sesiones de la máquina con `ListAgents`.

`tests/test_bench.py` prueba el banco sin llamar al modelo.
