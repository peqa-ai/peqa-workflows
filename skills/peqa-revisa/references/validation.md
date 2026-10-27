# Pruebas y alcance del impacto

Toda revisión comprueba qué mecanismos de validación existen y evalúa el blast radius: qué comportamiento, consumidores y datos pueden verse afectados, también fuera de los archivos modificados. El informe distingue evidencia ejecutada de análisis estático y de resultados comunicados por otros.

## Descubrir y ejecutar pruebas

1. Lee instrucciones del repositorio, documentación de desarrollo, manifiestos, scripts, configuración de CI y pruebas cercanas al cambio. Busca los comandos reales de unitarias, integración, contratos, E2E, smoke tests u otras pruebas disponibles. Lint, tipos y build son evidencia complementaria; no sustituyen una prueba funcional.
2. Usa el mapa de impacto de abajo para elegir pruebas pertinentes y ampliar a consumidores o integración cuando haga falta. En submódulos, identifica el comando y directorio de trabajo de cada repositorio afectado, además de las pruebas del padre. Un padre sin runner no implica que sus hijos carezcan de pruebas.
3. El padre ejecuta los comandos seguros dentro del alcance autorizado, o usa un ejecutor de pruebas permitido por el host. El revisor permanece de solo lectura: inspecciona la cobertura, pide las ejecuciones faltantes al padre y analiza los resultados. No relajes el sandbox del revisor para generar caches, builds o fixtures. Una solicitud al padre no concede permiso adicional.
4. Lee lo que hará el comando antes de ejecutarlo. Usa modo no interactivo y una ejecución acotada. Las pruebas que escriben datos usan un entorno de pruebas aislado y recursos autorizados. No dirijas E2E, migraciones o fixtures a producción ni ejecutes scripts de despliegue disfrazados de checks. Si faltan dependencias, servicios, credenciales o permisos, informa el bloqueo y continúa las comprobaciones independientes posibles; no cambies cuentas ni instales herramientas por cuenta propia.
5. Registra repositorio, comando, cwd, entorno, revisión exacta, exit code, resumen y ruta del resultado. Incluye hashes de diffs y archivos nuevos si revisas trabajo sin commit, y los SHAs reales de los submódulos utilizados. Conserva evidencia de fallos y omisiones. La CI debe corresponder al head o combinación revisados; un resultado anterior o de otro checkout no demuestra el estado actual.
6. Ante un fallo, distingue regresión del cambio, fallo previo e impedimento del entorno con evidencia. Compara con una base solo si puedes hacerlo sin alterar trabajo ajeno. No lo llames preexistente sin comprobarlo ni repitas indefinidamente una suite inestable. Tras una corrección o cambio de SHA, repite las comprobaciones afectadas; el padre puede ejecutar pruebas sin consumir otra revisión independiente.

Si no hay pruebas, informa dónde buscaste y qué comportamiento queda sin comprobar. Puedes proponer o ejecutar una comprobación mínima segura dentro del encargo; no inventes una suite aprobada ni amplíes el proyecto con un framework de testing para conseguir un indicador verde.

## Analizar blast radius

Parte del diff real, los gitlinks y las dependencias observadas. Sigue las conexiones pertinentes; no conviertas cada revisión en una auditoría completa del sistema.

- **Cambio directo:** funciones, servicios, configuración, dependencias o esquema que cambian, y quién consume sus resultados.
- **Propagación:** API, eventos, colas, clientes, librerías compartidas, permisos, datos persistidos y orden de despliegue que puedan transmitir el efecto a otros servicios. Incluye consumidores relevantes aunque no tengan diff ni PR.
- **Condiciones e impacto:** rutas y usuarios afectados, exposición, compatibilidad entre versiones, posibilidad de pérdida de datos o indisponibilidad, reversibilidad y rollback. Una migración irreversible requiere más evidencia que un cambio local reversible.
- **Evidencia y cobertura:** fuente de cada relación, pruebas que la ejercitan, límites del análisis y dependencias que no pudiste inspeccionar. No deduzcas bajo impacto de pocas líneas cambiadas ni de unitarias verdes.

Resume el impacto como acotado, compartido, amplio o indeterminado, con una razón concreta y sin puntuaciones inventadas. Separa el alcance del impacto de la severidad de un defecto y del estado de las pruebas. Un cambio amplio puede estar bien validado; una dependencia desconocida mantiene incertidumbre.

## Veredicto

Entrega una tabla breve por repositorio o superficie: `revisión | pruebas/comando | estado | evidencia | cobertura pendiente`. Estados: `pasó`, `falló`, `parcial`, `no ejecutado` o `sin pruebas encontradas`. Un código de salida cero con cero pruebas, skips relevantes o cobertura ajena al cambio no permite afirmar validación funcional completa.

Añade el mapa de impacto con afectados, conexión causal, evidencia, prueba pertinente e incertidumbre, y la cobertura de [seguridad aplicable](security.md). Usa [la recomendación y evaluación de mínimos](report.md#recomendación-y-mínimos) en la parte superior del consolidado, explicando qué se ha demostrado que funciona y qué falta. Pruebas fallidas o carencias materiales impiden sugerir aprobación; cero hallazgos estáticos no demuestra funcionamiento. No equipares tests verdes con validación de producción.
