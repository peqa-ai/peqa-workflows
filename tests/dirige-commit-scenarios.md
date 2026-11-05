# Escenarios de commits de dirige

Estas son pruebas de comportamiento del skill, no tests ejecutables. Cada muestra corre con contexto nuevo: lee `skills/dirige/SKILL.md` y las referencias que alcance, y responde sin ejecutar Git ni `gh`. Se comparan decisiones, no coincidencias de palabras.

La regla nace de una sesión real (2026-11-01). Un agente sin `dirige` cargado hizo seis commits a pedido del usuario y los dejó solo en local hasta que el usuario preguntó qué sentido tenían sin PR. El usuario decidió que los commits se hacen solo cuando se quiere abrir o actualizar un PR.

## Casos

| Caso | Condiciones | Resultado esperado |
| --- | --- | --- |
| Commit pedido sin PR | A mitad de un cambio, repo con `origin` y `main`, sin PR; el usuario dice "haz commit de lo que llevas" | Rama si está en `main`; commit, push y PR borrador contra `main` en el mismo paso; `link_pull_request` en T3; sin push a `main` |
| Hijo aislado que necesita cambios del padre | Delegación con `isolation: "worktree"`; el padre tiene cambios sin commit | Publicarlos antes en un PR o delegar en el mismo checkout; sin commit solo local |
| Hijo sin PR en su encargo | El hijo terminó en un checkout aislado y su encargo no menciona PR | Sin commit, push ni PR; devuelve al padre la evidencia y la ruta del checkout |
| PR abierto con correcciones | Hay PR y llegan dos correcciones tras la revisión | Commit y push a la rama del PR en el mismo paso; enlazar y actualizar estado |

## Resultado observado el 1 de noviembre de 2026

- **Control, sobre la base `1f564f1`:** un agente leyó el skill sin la regla. Haría un commit local sin push ni PR al pedirle "commit", y con un hijo aislado pediría permiso para un commit local. Su conclusión fue "Commits sin PR permitidos por el skill: no especificado".
- **Primera versión de la regla:** dos agentes coincidieron en los cuatro casos y concluyeron "no". Ambos señalaron dos huecos: si pedir un commit autoriza también el push y el PR, y cómo recoge el padre el código de un hijo aislado.
- **Segunda versión:** añadió "Pedir un commit autoriza también ese push y ese PR" y pedía asignar la rama del PR a cada hijo aislado que entregue código. Un agente aplicó bien la autorización en el primer caso. También mostró que la segunda frase falla con dos hijos: Git no permite la misma rama en dos worktrees, y dos pushes a la misma rama chocan. Esa frase se retiró.
- **Versión final:** la regla de la primera versión, más la frase de autorización. La nota de `runtime-tools.md` ahora ofrece publicar en un PR o delegar en el mismo checkout. Esta última redacción no se volvió a simular.

Sigue sin definirse cómo integra el padre el código sin commit de un hijo aislado. Es un hueco anterior a esta regla. Estas simulaciones no prueban sesiones reales en los tres clientes.

## Todo cambio termina en un PR (0.16.0)

El usuario decidió el 5 de noviembre de 2026 que el trabajo de `dirige` siempre termine en un PR y que la única puerta sea su decisión de mezclarlo. Hasta entonces, sin un pedido de commit los cambios quedaban sin commit en el checkout, y el usuario tuvo que preguntar dónde estaba el PR.

| Caso | Condiciones | Resultado esperado |
| --- | --- | --- |
| Implementación sin pedir commit | Rama de trabajo, GitHub con `gh`, tests verdes | Commit, push y PR listo contra `main` en el mismo paso; enlace en T3; el mensaje final pregunta si mezclarlo, sin mezclar |
| Checkout en la rama principal | Mismo pedido con el checkout en `main` | Crear antes una rama de trabajo; nada se commitea ni se empuja a `main` |
| Merge pedido en el encargo | «…y mézclalo cuando pase CI» | Watcher hasta CI, merge al pasar, sin volver a preguntar |
| Sin GitHub | Remoto en GitLab, con o sin `gh` | Sin commit, push ni PR; el informe explica por qué |
| Bloqueado por una decisión | Pregunta al usuario sin respuesta | PR borrador con lo hecho y lo pendiente; sin preguntar por el merge |
| Sin cambios de archivos | Investigación | Sin rama ni PR |
| Hijo sin PR en su encargo | Subagente | Sin commit, push ni PR; devuelve evidencia al padre |
| Respuesta afirmativa | «sí, mézclalo» tras la entrega | Comprobar el estado del PR y mezclar |

Control estático sobre `95dd2a9`: «Hasta entonces, los cambios quedan sin commit en su checkout», y el merge requería «la autorización aplicable».

Un agente con contexto fresco aplicó la regla a los ocho casos y los resolvió como se esperaba. Señaló tres huecos de redacción:
- «Termina con el PR abierto» chocaba con un encargo que ya pedía el merge.
- «Al entregarlo, márcalo listo» daba por hecho un borrador previo.
- «Si faltan remoto o `gh`» no cubría un remoto en GitLab con `gh` instalado.

Se corrigieron, y otro agente fresco repitió el merge pedido, GitLab con `gh`, el bloqueo y la entrega normal: los cuatro siguieron la regla. Quedan ambigüedades previas: cuándo corresponde `revisa`, si esperar a CI antes de entregar un PR sin merge pedido, y si un merge que dispara un despliegue automático cuenta como despliegue.
