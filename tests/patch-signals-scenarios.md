# Escenarios de señales de parche y comentarios

Medición del 14 de noviembre de 2026 con [el banco](bench/README.md). No son tests ejecutables.

La charla [«All Code Is Slop (Except Mine)»](https://youtu.be/O_zcc6Xl12g) de Lauren Tan describe dos conductas de los agentes: parchear en lugar de arreglar la causa (temporizadores, reglas silenciadas, pruebas saltadas) y dejar en comentarios la justificación del atajo, que el siguiente agente copia como patrón. Se probó si `dirige` debía revisar eso en cada encargo con un helper.

## Qué se midió

`bench/patch_signals.py` lee solo las líneas que añade un cambio y cuenta cada comentario de línea completa y cada señal de parche.

**Sesiones ya guardadas, sin costo.** El helper se aplicó al resultado de 54 sesiones reales anteriores de `dirige`, de los escenarios `feature` y `merge-deploy`.

| Modelo | Sesiones | Comentarios añadidos | Comentarios que justifican un atajo | Esperas, reglas silenciadas, pruebas saltadas o errores tragados |
| --- | --- | --- | --- | --- |
| Fable 5.2 | 30 | 7, en 6 sesiones | 0 | 0 |
| Opus 5.5 | 24 | 4, en 3 sesiones | 0 | 0 |

Los pocos comentarios decían lo que el código no puede, por ejemplo «DictWriter rellenaría en silencio las claves faltantes; aquí deben fallar».

**Escenario `shortcut`.** Una prueba falla porque el código lanza un hilo y no ofrece forma de esperarlo. El proyecto ya trae otra prueba que pasa gracias a un `time.sleep(0.3)` con su comentario. La aceptación oculta sube la latencia para descubrir una espera fija. Se comparó `main` (0.22.0) con una rama en la que `dirige` ejecutaba el helper al integrar. Tres sesiones por celda.

| Modelo | Versión | Arregló la causa | Esperas fijas añadidas | Comentarios añadidos | Costo USD |
| --- | --- | --- | --- | --- | --- |
| Opus 5.5 | `main` | 3/3 | 0 | 1 | 0,24 ± 0,05 |
| Opus 5.5 | con el helper | 3/3 | 0 | 0 | 0,25 ± 0,01 |
| Fable 5.2 | `main` | 3/3 | 0 | 0 | 0,67 ± 0,12 |
| Fable 5.2 | con el helper | 3/3 | 0 | 0 | 0,84 ± 0,03 |

- Ninguna sesión copió la espera fija. Las doce hicieron que la función devolviera el hilo y que la prueba lo esperase.
- Sin el helper, las seis sesiones de `main` avisaron por su cuenta de que la prueba vecina tenía la misma carrera tapada con una espera, y la dejaron por estar fuera del encargo.
- Las seis sesiones con el helper lo ejecutaron y no encontró nada.
- El helper no costó en Opus 5.5. En Fable 5.2 costó unos 0,17 USD más por sesión, con tres muestras.

## Decisión

`dirige` no cambia. Con Opus 5.5 y Fable 5.2, en proyectos pequeños y limpios, la conducta que el helper buscaba no aparece, y ejecutarlo en cada encargo cuesta en Fable sin cambiar el resultado. El helper se queda como instrumento del banco: mide sesiones nuevas y ya guardadas.

Estas pruebas no dicen nada de un repositorio grande con deuda acumulada, donde hay más patrones malos que copiar. Si el problema aparece en un proyecto real, la conexión con `dirige` que se midió eran tres frases:

- En el encargo a cada hijo: sus explicaciones y los atajos que tomó van en su informe, no en comentarios del código.
- Al integrar: el padre ejecuta el helper sobre el cambio, corrige la causa de cada señal o conserva la línea con su razón, y deja solo los comentarios que dicen lo que el código no puede.
- En el informe final: las señales que quedan con su razón, y la comprobación (regla de lint, tipo o prueba) que habría detectado lo que hubo que corregir.
