# PEQA workflows

Plugin de cinco skills originales para **Codex y Claude Code**, reutilizable por cualquier persona y proyecto. T3 Code tiene una integración preferente cuando está disponible; fuera de T3 se usan las herramientas nativas del cliente. El plugin no depende de skills ni scripts de TStack.

Versión `0.3.0`, borrador público para revisión manual. Repositorio: [peqa-ai/peqa-workflows](https://github.com/peqa-ai/peqa-workflows). La publicación no instala ni activa el plugin en los clientes.

| Skill | Función |
| --- | --- |
| [peqa-dirige](skills/peqa-dirige/SKILL.md) | El padre descubre sesiones pertinentes, coordina recursos y subagentes, integra y verifica. Puede llamar a idea y revisa. |
| [peqa-revisa](skills/peqa-revisa/SKILL.md) | Revisión adversarial, Sol 6.1/xhigh preferido y máximo tres ejecuciones por PR. |
| [peqa-idea](skills/peqa-idea/SKILL.md) | Decisiones de producto e implementación, recomendaciones contextuales y máximo tres rondas. |
| [memoria-recuerda](skills/memoria-recuerda/SKILL.md) | Guarda conceptos pequeños y duraderos del proyecto con procedencia. |
| [memoria-extraer](skills/memoria-extraer/SKILL.md) | Recupera todas las categorías o un tema, con referencias y verificación registrada. |

`peqa-revisa` es el nombre canónico; la mención inicial de `peqa-review` se resuelve aquí. El paquete mantiene cinco entradas.

## Instalar y reutilizar

La unidad de distribución es **el plugin completo**. Sus skills comparten referencias y un helper; copiar solo una carpeta de skill perdería esos recursos. La instalación puede servir a todos los proyectos del usuario. El directorio de trabajo, sus cuentas, infraestructura, instrucciones y memorias se resuelven en cada uso, sin rutas personales incorporadas.

Para probar una copia descargada en Claude Code sin instalarla globalmente:

```sh
claude --plugin-dir /ruta/al/peqa-workflows
```

Para instalarla desde GitHub en Claude Code:

```sh
claude plugin marketplace add peqa-ai/peqa-workflows
claude plugin install peqa-workflows@peqa --scope user
```

En Codex CLI con soporte para plugins:

```sh
codex plugin marketplace add peqa-ai/peqa-workflows
codex plugin add peqa-workflows@peqa
```

Los catálogos incluidos `.claude-plugin/marketplace.json` y `.agents/plugins/marketplace.json` apuntan al paquete con rutas relativas. El manifiesto portable `plugin.json` y los dos manifiestos de compatibilidad conservan nombre y versión. Para registrar una copia local, sustituye `peqa-ai/peqa-workflows` por su ruta en el comando `marketplace add`. Los comandos anteriores son instrucciones de instalación: no se han ejecutado sobre la configuración del usuario durante la creación del borrador. Inicia una nueva sesión tras instalar y selecciona el skill del plugin con la sintaxis que muestre el cliente; en Claude Code, por ejemplo, `/peqa-workflows:peqa-dirige`.

La licencia de distribución está pendiente de la elección del autor. El borrador aún no tiene licencia declarada ni se afirma aprobación de ningún directorio oficial. La instalación integral entre clientes sigue pendiente de validación.

## Cómo trabaja

El soporte del stack se concentra en T3 Code, Codex y Claude Code. Antes de implementar, `peqa-dirige` descubre agentes/sesiones visibles, lee el alcance de candidatos pertinentes y comunica qué archivos o recursos compartidos tocará. Negocia un editor o un orden de integración, recibe riesgos de los demás y avisa ante cambios materiales o cierre. La [referencia de coordinación](skills/peqa-dirige/references/coordination.md) distingue mensajería entre sesiones de la coordinación de hijos, así como visibilidad parcial de ausencia de trabajo concurrente.

El padre conserva la responsabilidad por la entrega y adjudica hallazgos con evidencia. Los hijos reciben encargos delimitados y no crean nuevas cadenas de coordinadores. Los workflows y swarms se sugieren cuando aportan un beneficio concreto y se usan si el usuario los elige.

Las preguntas nuevas utilizan la interfaz del proveedor. En T3, las preguntas existentes de hijos se leen y responden con `t3_pending_request`. El ciclo de delegación, cancelación y PRs está en una única [referencia de herramientas](references/runtime-tools.md), contrastada contra un commit de T3; el esquema vivo y las reglas del host prevalecen.

La revisión prefiere exactamente `gpt-6.1-sol` con `xhigh`. En T3 usa su catálogo y ruta de orquestación. Fuera, usa selección nativa o un Codex CLI ya autenticado desde un padre Claude. Si no está disponible, el diseño autoriza un subagente fresco del motor actual, declarado como fallback. No instala proveedores, inicia logins ni cambia credenciales. Los revisores responden al padre y no publican comentarios ni reviews en GitHub.

El [controlador de presupuesto](skills/peqa-revisa/references/budget.md) conserva un máximo total de tres revisiones independientes por PR, incluyendo fallos, cancelaciones y rechecks. Comparte contador entre worktrees; clones independientes necesitan importar historia verificada. La tercera pasada no constituye aprobación automática. `peqa-idea` mantiene su contador por iniciativa entre sesiones y agentes.

## Memoria por proyecto

La instalación del plugin contiene instrucciones y scripts. Cada proyecto conserva sus propios datos:

```text
cualquier-proyecto/.peqa/memoria/
  project/<categoria>/<concepto>.md
  local/<maquina>/<categoria>/<concepto>.md
```

Se reutiliza `.peqa-stack/memoria` si es el único almacén existente. La memoria de proyecto puede compartirse deliberadamente mediante Git; la memoria de máquina se ignora. Guardar no hace commits ni publica datos. Cada nota conserva fuente, fechas, entorno y verificación. No se ha identificado todavía una referencia concreta para el nombre OKF; el formato actual es Markdown con metadata JSON.

Ejemplos de petición, aplicables a cualquier repositorio:

- «Recuerda la convención que decidimos para desplegar este servicio».
- «Guarda como memoria de esta máquina qué identidad debe firmar los commits aquí».
- «Extrae todas las categorías de memoria de este proyecto».
- «Recupera solo lo relacionado con DevOps para el trabajo de hoy».

La extracción es de solo lectura. Una nota no prueba que una cuenta siga autenticada, no ejecuta comandos anotados ni autoriza despliegues. El helper excluye otras máquinas al recuperar y exige el SHA leído antes de cambiar una nota existente. Consulta [formato, comandos y límites](references/project-memory.md).

## Requisitos y validación

Los flujos requieren las herramientas que exponga el cliente: acceso al proyecto, preguntas y subagentes cuando corresponda. El plugin no incluye modelos, credenciales, MCP propio, hooks ni servidores. La ruta Codex CLI para revisión es opcional; su falta permite el fallback descrito.

Los helpers requieren Python 3.10+. **El helper de memoria funciona actualmente en macOS/Linux**: usa operaciones POSIX para bloqueo y protección de rutas; Windows falla con un mensaje claro y queda pendiente. Guardar y recuperar requieren shell local, por lo que estas funciones no son flujos exclusivos de un chat sin acceso a archivos. Los skills de dirigir, revisar e idea no dependen de un proyecto o sistema operativo concreto.

Desde la raíz del plugin:

```sh
python3 -m unittest discover -s tests -v
```

Las pruebas usan datos sintéticos y repositorios temporales. La validación de instrucciones y la prueba previa de un Codex CLI se conservan fuera del plugin, en la carpeta de validación de esta sesión. No prueban por sí solas la instalación y ejecución integral en todos los clientes o sistemas operativos.

## Fuentes

La entrevista por decisiones reconoce la referencia conceptual de [Matt Pocock](https://github.com/mattpocock/skills). Las instrucciones son propias, con tres rondas y atención al producto y la implementación. La integración T3 cita sus fuentes en [runtime-tools.md](references/runtime-tools.md).

El empaquetado sigue la [documentación oficial de plugins de OpenAI](https://developers.openai.com/plugins/build/plugins) y la [referencia de plugins de Claude Code](https://code.claude.com/docs/en/plugins-reference). Las opciones de instalación se contrastaron con las ayudas locales de los clientes. La revisión CLI se contrastó con [ejecución no interactiva de Codex](https://learn.chatgpt.com/docs/non-interactive-mode) y Codex CLI 0.164.0.
