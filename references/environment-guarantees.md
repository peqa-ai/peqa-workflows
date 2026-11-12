# Garantías del entorno

Un skill pide una conducta; no la garantiza. Cuando nadie aprueba cada paso, lo que no puede fallar lo sostiene el repositorio remoto, el cliente o el entorno donde corre la sesión. Esta referencia indica qué comprobar, en qué momento y qué proponer cuando falta. Comprobar es de solo lectura; el usuario decide y aplica cada ajuste.

## Qué necesita una garantía

Para cada acción del encargo pregunta: si sale mal una vez, ¿se puede deshacer?

- **Se puede deshacer:** código equivocado, un commit en la rama de trabajo, un PR en borrador. Bastan las instrucciones, las pruebas y la revisión.
- **No se puede deshacer o sale de la máquina:** push a la rama principal, reescritura de historia publicada, merge, despliegue o publicación, borrado de datos o de trabajo sin commit, mensajes a terceros y un secreto que llega a la transcripción o al código que ejecutan los comandos. Necesita una garantía fuera del prompt o la autorización expresa del usuario.

## Qué comprobar y cuándo

Comprueba solo las filas cuya condición cumple el encargo, una vez por encargo y en el momento que indica cada una.

| Aplica cuando | Momento | Garantía | Cómo comprobarla |
| --- | --- | --- | --- |
| El checkout guarda secretos, reconocibles por el nombre de archivos como `.env*` sin abrirlos, y la sesión ejecuta comandos que nadie aprueba uno a uno: modo automático, segundo plano o workers | Al empezar | Regla del cliente que niega su lectura y sandbox para los comandos, o un entorno desechable sin esos secretos | Ajustes del cliente, según su sección |
| El encargo pide desplegar o publicar | Al empezar | Aprobación en la plataforma que despliega, o credenciales limitadas a ese destino | `gh api 'repos/{owner}/{repo}/environments'` lista los entornos y sus reglas. Un script local con credenciales locales no tiene más garantía que el usuario |
| El encargo pide el merge | Al empezar | Protección de la rama principal con checks requeridos | `gh api 'repos/{owner}/{repo}/branches/<rama>/protection'` y `gh api 'repos/{owner}/{repo}/rules/branches/<rama>'`: un 404 y una lista vacía indican que nada la protege |
| La entrega va a preguntar por el merge | Al preparar la entrega | La misma protección, y checks que corrieron en ese PR | Las dos consultas anteriores y `gh pr checks <URL>`; si no lista ninguno, ningún check corrió |

Las garantías del servidor valen para cualquier cliente y sesión; por eso van primero. Lo que no puedas leer, decláralo sin comprobar.

## Checks en cada PR

Cada sesión decide qué comprueba. El CI aplica las mismas comprobaciones a todos los PRs, sin depender de cómo se configuró la sesión que los abrió. Si el proyecto tiene pruebas y ningún check las ejecuta en el PR, la entrega lo declara: lo que corrió en la sesión es entonces la única comprobación. Propón un workflow que ejecute los comandos que el proyecto ya tiene, sin añadir un framework de pruebas.

## En Claude Code

- **Reglas `deny` y `ask`.** Viven en `permissions` dentro de `.claude/settings.json`; con commit llegan a todo el equipo. Se resuelven antes que el clasificador del modo automático, y `deny` bloquea en todos los modos. Una regla `ask` conserva a una persona en ese paso aunque el resto de la sesión corra en modo automático.
- **Límite de las reglas de Bash.** Comparan el texto del comando: `Bash(git push *)` detiene `git push origin main` y deja pasar `git -C . push origin main`. El push a la rama principal se garantiza en el servidor; la regla es una segunda capa. El modo automático permite por defecto el push a cualquier rama del repositorio, incluida la principal, y bloquea el force push.
- **Archivos.** `Read(./.env)` cubre las herramientas de archivo y los comandos que el cliente reconoce, como `cat`. Un script que abre el archivo por su cuenta queda fuera salvo con el sandbox activo, que aplica esas rutas en el sistema operativo a cada comando y a sus procesos hijos.
- **Sandbox.** `sandbox.enabled` limita archivos y red de los comandos de shell. Las herramientas de archivo, los servidores MCP y los hooks corren fuera de él.
- **Dónde leerlos.** Reglas y sandbox pueden venir de los ajustes de usuario, del proyecto o locales: lee los tres antes de darlos por ausentes.
- **Hooks para lo que debe correr siempre.** Un hook de `Stop`, `SubagentStop` o `TaskCompleted` que termina con código 2 devuelve el trabajo a Claude con su stderr. Con código 1 la acción continúa: un runner de pruebas que falla con 1 necesita un envoltorio que salga con 2. En `PostToolUse` el código 2 muestra el stderr sin deshacer la edición. Los hooks de este plugin siguen [su propia referencia](checks-and-hooks.md).
- **Confianza del modo automático.** Los repositorios, dominios y buckets de confianza se describen en `autoMode`, que el cliente lee de los ajustes de usuario y no de los del proyecto. `claude auto-mode config` muestra la configuración efectiva.
- **Sesión en la nube.** Corre sobre un clon nuevo, sin los ajustes ni los secretos de la máquina. Con un solo repositorio lee su `.claude/settings.json`; en los hilos de un proyecto no. Antes de recomendarla para un encargo, comprueba que este plugin carga en ese entorno.

Propuesta para el `.claude/settings.json` del proyecto, que el usuario ajusta a sus rutas y a su flujo:

```json
{
  "permissions": {
    "deny": ["Read(./.env)", "Read(./.env.*)", "Bash(git push --force *)", "Bash(git push -f *)"],
    "ask": ["Bash(gh pr merge *)"]
  },
  "sandbox": {"enabled": true}
}
```

## En Codex

`--sandbox` elige la política de los comandos que genera el modelo: `read-only`, `workspace-write` o `danger-full-access`. `--ask-for-approval` fija cuándo pide aprobación. Informa la combinación efectiva de la sesión; estas instrucciones no la cambian. Esta referencia no verificó una regla de Codex que niegue la lectura de un archivo concreto: si el checkout guarda secretos, declara que solo los protegen el sandbox y las instrucciones, sin proponer un ajuste que no puedas respaldar.

## En T3 y Orca

Los hijos heredan las reglas del cliente que ejecuta a cada uno. Un worker de Orca no tiene modo de solo lectura ni sandbox propio, como indica [herramientas del entorno](runtime-tools.md#subagentes-en-orca): su brief delimita los efectos y el padre comprueba el resultado.

## Informar y proponer

Menciona solo las garantías que faltan en las filas que aplican, con una línea por cada una: qué falta y el ajuste propuesto como texto revisable. Las que se comprueban al empezar se informan entonces, en un mensaje que no pregunta nada. Las que se comprueban al preparar la entrega van dentro del informe final. Propón cada ajuste una vez por iniciativa: el informe final nombra las ya propuestas sin repetir el ajuste. Con todo en su lugar basta una línea en ese informe.

La falta de una garantía no detiene el trabajo reversible ni añade una pregunta. Pedir la acción en el encargo es la autorización expresa: ejecútala cuando se cumplan sus condiciones y deja dicho en el informe qué la sostenía y qué no.

## Fuentes

Consultadas el 2026-11-12 en la documentación de Claude Code: [permisos](https://code.claude.com/docs/en/permissions), [modos de permiso](https://code.claude.com/docs/en/permission-modes), [sandbox](https://code.claude.com/docs/en/sandboxing), [hooks](https://code.claude.com/docs/en/hooks) y [ajustes](https://code.claude.com/docs/en/settings#settings-in-cloud-sessions). Las reglas por defecto del modo automático se contrastaron con `claude auto-mode defaults` en la versión 2.1.322, y las opciones de Codex con `codex --help` en la versión 0.167.1. El criterio de reversibilidad y el papel del CI vienen de la charla [«Rethinking Claude Code Best Practices»](https://youtu.be/vlfCjWuv4es) de Lydia Hallie, de Anthropic. Comprueba la instalación efectiva antes de proponer un ajuste.
