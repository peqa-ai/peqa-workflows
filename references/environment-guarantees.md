# Garantías del entorno

Un skill pide una conducta; no la garantiza. Cuando nadie aprueba cada paso, lo que no puede fallar lo sostiene el repositorio remoto, el cliente o el entorno donde corre la sesión. Esta referencia indica qué comprobar, en qué momento y qué proponer cuando falta. Comprobar es de solo lectura; el usuario decide y aplica cada ajuste.

## Qué necesita una garantía

Para cada acción del encargo pregunta: si sale mal una vez, ¿se puede deshacer?

- **Se puede deshacer:** código equivocado, un commit en la rama de trabajo, un PR en borrador. Bastan las instrucciones, las pruebas y la revisión.
- **No se puede deshacer o sale de la máquina:** push a la rama principal, reescritura de historia publicada, merge, despliegue o publicación, borrado de datos o de trabajo sin commit, mensajes a terceros y un secreto que llega a la transcripción o al código que ejecutan los comandos. Necesita una garantía fuera del prompt o la autorización expresa del usuario.

## Qué comprobar y cuándo

El helper incluido hace las consultas en modo lectura y devuelve JSON. Resuelve `PEQA_PLUGIN` desde la instalación del plugin y `PEQA_REPO` como raíz del proyecto.

```sh
python3 "$PEQA_PLUGIN/scripts/environment_guarantees.py" check --repo "$PEQA_REPO"
```

| Momento | Opción | Qué comprueba |
| --- | --- | --- |
| Al empezar | ninguna | Archivos `.env*` del checkout, por nombre y sin abrirlos, frente a las reglas `deny` y el sandbox de los ajustes de usuario, de proyecto y locales de Claude Code |
| Al empezar, si el encargo pide el merge | `--merge` | Checks requeridos en la rama principal, por protección clásica o por ruleset |
| Al empezar, si el encargo pide desplegar o publicar | `--deploy` | Entornos de despliegue con reglas de protección |
| Al preparar la entrega | `--pr <URL>` | La rama principal y los checks que corrieron en ese PR |

El helper detecta Codex por su entorno; `--runtime claude` o `--runtime codex` lo fijan a mano. Cada elemento de `checks` trae un `status`:

- `missing`: la garantía falta. Trae una `proposal` que nombra solo lo que falta.
- `not_verified`: no se pudo leer, por ejemplo sin `gh`, sin remoto en GitHub o sin permiso. Decláralo sin comprobar; no lo presentes como ausente.
- `ok` y `not_applicable`: nada que proponer.

La fila de secretos importa cuando la sesión ejecuta comandos que nadie aprueba uno a uno: modo automático, segundo plano o workers. Un despliegue por script local con credenciales locales no tiene más garantía que el usuario, aunque el repositorio defina entornos.

Sin Python, haz las consultas a mano: `gh api 'repos/{owner}/{repo}/branches/<rama>'` (campo `protection`), `gh api 'repos/{owner}/{repo}/rules/branches/<rama>'`, `gh pr view <URL> --json statusCheckRollup` y `gh api 'repos/{owner}/{repo}/environments'`. La ruta `branches/<rama>/protection` responde 404 a quien no administra el repositorio aunque la rama esté protegida; no la uses para concluir que falta.

## Checks en cada PR

Cada sesión decide qué comprueba. El CI aplica las mismas comprobaciones a todos los PRs, sin depender de cómo se configuró la sesión que los abrió. Si el proyecto tiene pruebas y ningún check las ejecuta en el PR, la entrega lo declara: lo que corrió en la sesión es entonces la única comprobación. Propón un workflow que ejecute los comandos que el proyecto ya tiene, sin añadir un framework de pruebas.

## En Claude Code

- **Reglas `deny` y `ask`.** Viven en `permissions` dentro de `.claude/settings.json`; con commit llegan a todo el equipo. Se resuelven antes que el clasificador del modo automático, y `deny` bloquea en todos los modos. Una regla `ask` conserva a una persona en ese paso aunque el resto de la sesión corra en modo automático.
- **Límite de las reglas de Bash.** Comparan el texto del comando: `Bash(git push *)` detiene `git push origin main` y deja pasar `git -C . push origin main`. El push a la rama principal se garantiza en el servidor; la regla es una segunda capa. El modo automático permite por defecto el push a cualquier rama del repositorio, incluida la principal, y bloquea el force push.
- **Archivos.** `Read(./.env)` cubre las herramientas de archivo y los comandos que el cliente reconoce, como `cat`. Un script que abre el archivo por su cuenta queda fuera salvo con el sandbox activo, que aplica esas rutas en el sistema operativo a cada comando y a sus procesos hijos.
- **Sandbox.** `sandbox.enabled` limita archivos y red de los comandos de shell. Las herramientas de archivo, los servidores MCP y los hooks corren fuera de él.
- **Dónde viven.** Reglas y sandbox pueden venir de los ajustes de usuario, del proyecto o locales; el helper lee los tres. Los ajustes gestionados por la organización y los de línea de comandos quedan fuera de su lectura.
- **Hooks para lo que debe correr siempre.** Un hook de `Stop`, `SubagentStop` o `TaskCompleted` que termina con código 2 devuelve el trabajo a Claude con su stderr. Con código 1 la acción continúa: un runner de pruebas que falla con 1 necesita un envoltorio que salga con 2. En `PostToolUse` el código 2 muestra el stderr sin deshacer la edición. Los hooks de este plugin siguen [su propia referencia](checks-and-hooks.md).
- **Confianza del modo automático.** Los repositorios, dominios y buckets de confianza se describen en `autoMode`, que el cliente lee de los ajustes de usuario y no de los del proyecto. `claude auto-mode config` muestra la configuración efectiva.
- **Sesión en la nube.** Corre sobre un clon nuevo, sin los ajustes ni los secretos de la máquina. Con un solo repositorio lee su `.claude/settings.json`; en los hilos de un proyecto no. Antes de recomendarla para un encargo, comprueba que este plugin carga en ese entorno.

## En Codex

`--sandbox` elige la política de los comandos que genera el modelo: `read-only`, `workspace-write` o `danger-full-access`. `--ask-for-approval` fija cuándo pide aprobación. Informa la combinación efectiva de la sesión; estas instrucciones no la cambian. Esta referencia no verificó una regla de Codex que niegue la lectura de un archivo concreto: si el checkout guarda secretos, declara que solo los protegen el sandbox y las instrucciones, sin proponer un ajuste que no puedas respaldar.

## En T3 y Orca

Los hijos heredan las reglas del cliente que ejecuta a cada uno. Un worker de Orca no tiene modo de solo lectura ni sandbox propio, como indica [herramientas del entorno](runtime-tools.md#subagentes-en-orca): su brief delimita los efectos y el padre comprueba el resultado.

## Informar y proponer

El informe final lleva una línea por cada elemento de `missing`: qué falta y su `proposal` completa, como texto revisable. Escríbelo ahí aunque ya lo hayas mencionado: una nota de progreso puede no llegar al usuario. Si el encargo pide merge, despliegue o publicación y falta su garantía, dilo también antes de ejecutar esa acción. Con todo en su lugar basta una línea en ese informe.

La falta de una garantía no detiene el trabajo reversible ni añade una pregunta. Pedir la acción en el encargo es la autorización expresa: ejecútala cuando se cumplan sus condiciones y deja dicho en el informe qué la sostenía y qué no.

## Fuentes

Consultadas el 2026-11-12 en la documentación de Claude Code: [permisos](https://code.claude.com/docs/en/permissions), [modos de permiso](https://code.claude.com/docs/en/permission-modes), [sandbox](https://code.claude.com/docs/en/sandboxing), [hooks](https://code.claude.com/docs/en/hooks) y [ajustes](https://code.claude.com/docs/en/settings#settings-in-cloud-sessions). Las reglas por defecto del modo automático se contrastaron con `claude auto-mode defaults` en la versión 2.1.322, y las opciones de Codex con `codex --help` en la versión 0.167.1. Las respuestas de GitHub que lee el helper se contrastaron el 2026-11-13 con `gh` 2.102.0. El criterio de reversibilidad y el papel del CI vienen de la charla [«Rethinking Claude Code Best Practices»](https://youtu.be/vlfCjWuv4es) de Lydia Hallie, de Anthropic. Comprueba la instalación efectiva antes de proponer un ajuste.
