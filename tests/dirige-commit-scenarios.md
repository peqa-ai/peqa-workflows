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
