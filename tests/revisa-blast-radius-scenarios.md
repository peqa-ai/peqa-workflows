# Escenarios del mapa de blast radius

Medición del 13 de noviembre de 2026 con [el banco](bench/README.md), escenario `review`. No son tests ejecutables.

`revisa` recibe una rama cuyo commit renombra una clave y una función del reporte. La suite del proyecto pasa, pero el cambio rompe `reportes/facturas.py` e `integraciones/erp/cierre.py`, que no están en el diff ni tienen pruebas. Se compara `main` (0.21.0) con la rama que añade `blast_radius.py`. El sustituto de `codex` obliga a usar el revisor de reserva del motor actual. Tres sesiones por celda.

| Modelo | Versión | Nombra los dos archivos rotos | Usó `blast_radius.py` | Dejó correcciones sin commit | Costo USD |
| --- | --- | --- | --- | --- | --- |
| Opus 5.5 | `main` | 3/3 | no existía | 0/3 | 0,51 ± 0,10 |
| Opus 5.5 | con helper | 3/3 | 3/3 | 0/3 | 0,51 ± 0,07 |
| Fable 5.2 | `main` | 3/3 | no existía | 2/3 | 1,41 ± 0,17 |
| Fable 5.2 | con helper | 3/3 | 3/3 | 1/3 | 1,46 ± 0,22 |

- **El helper no cambió el resultado.** Las doce revisiones encontraron los dos consumidores rotos y recomendaron cambios. Sin el helper, los dos modelos ya buscan quién usa lo que cambió.
- **Tampoco cambió el costo**: las diferencias quedan dentro de una desviación estándar.
- **Las sesiones con la rama nueva sí lo usaron**, las seis.
- **Fable 5.2 aplicó las correcciones en el árbol de trabajo en 3 de 6 sesiones**, sin commit, como permite el paso 4 de `revisa`. Opus 5.5 no editó en ninguna.

Límite: el repositorio de ejemplo tiene una decena de archivos, y encontrar dos consumidores ahí es fácil para cualquier revisor. La prueba no dice nada de un repositorio grande, que es donde el mapa podría aportar.

Corrección del banco hecha durante esta medición: una sesión que espera a un revisor en segundo plano emite varios eventos `result`. El banco tomaba el primero, que en Fable era un «espero al revisor», y contaba dos informes como si no nombraran los archivos.
