# Escenarios del PR de memoria

Pruebas de comportamiento de `memoria-recuerda`, no tests de un recolector ejecutable. Ejecutar cada muestra con contexto fresco, leyendo `skills/memoria-recuerda/SKILL.md` y las referencias que alcance. Usar datos sintéticos y simulación explícita: sin worktrees, commits, push, `gh` ni `save`. Los prompts dicen solo «recuerda…» y piden describir todo lo que el agente haría, sin mencionar PRs.

## Casos

| Caso | Condiciones | Resultado esperado |
| --- | --- | --- |
| Nota de proyecto y de máquina | GitHub con `gh`; checkout en una rama de trabajo con cambios sin commit | Worktree temporal desde la rama principal remota; nota `project` guardada ahí; commit solo de `.peqa/memoria`; push, PR abierto sin merge; verificación con `ls-remote` y retirada del worktree; nota `machine` en el checkout actual; la rama de trabajo queda intacta |
| Sin GitHub | Remoto en GitLab y sin `gh` | Guardar en el checkout actual e informar por qué no hay PR |
| Actualizar una nota existente | La nota está en la rama principal | Leer la nota y su SHA en el worktree temporal; `save` con `--expected-sha`; PR con el cambio |
| PR de memoria abierto | Una rama `memoria/` del mismo repositorio toca el mismo concepto | Crear el worktree desde esa rama y actualizar su PR; si es de un fork, abrir uno propio |
| T3 | Host T3 | Enlazar el PR creado o actualizado, sin watcher |
| Actualizar el checkout | El checkout tiene sin rastrear el `.gitignore` del almacén | Explicar que las notas llegan tras el merge y que hay que retirar esa copia, si coincide con la de la rama principal, antes de actualizar |

## Control previo

Base: `6e6a4ad`. Control estático: `memoria-recuerda` decía «Guardar no añade ni confirma archivos, modifica identidades ni ejecuta operaciones remotas», y `project-memory.md` excluía `git add`, commit y push.

Prueba con Git en repositorios temporales: un archivo sin rastrear idéntico al que trae el merge hace fallar el `pull` con «untracked working tree files would be overwritten». Por eso las notas de proyecto se guardan en el worktree del PR y no en el checkout del usuario.

## Resultado observado el 30 de octubre de 2026

Dos agentes con contexto fresco cubrieron los seis casos. Siguieron el flujo nuevo en todos: worktree desde la rama principal remota, nota de proyecto en el PR y de máquina en local, PR sin merge, retirada del worktree, guardado local sin GitHub, actualización con SHA y enlace en T3.

Señalaron dos huecos de redacción: no se decía cómo retomar una rama `memoria/` existente, incluido un PR de un fork, y el `.gitignore` se comparaba «con la del PR» en lugar de con la rama principal. Se corrigieron en la referencia.

Los 107 tests existentes pasan; el helper no cambió. Se comprobaron enlaces, anclas y `git diff --check`. Queda pendiente la primera ejecución real del flujo con el skill instalado.
