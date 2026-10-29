# Recursos de una ejecución

`dirige` limpia por defecto los recursos que creó para el trabajo y que ya no hacen falta. `conservar`, por ejemplo «dirige este cambio y conserva los recursos al terminar», desactiva su eliminación durante esa ejecución. Una petición posterior de conservar prevalece antes de la siguiente eliminación; no recupera recursos ya retirados. Registra cambios de modo. La limpieza respeta los permisos del host y la coordinación existente; dentro de ese alcance no necesita una segunda confirmación rutinaria.

Esta política previene acumulación nueva. Una carpeta antigua, una rama publicada o un nombre parecido al de un hijo no prueban propiedad. La limpieza histórica del equipo, cachés compartidas, imágenes o volúmenes Docker y datos de otras aplicaciones requieren un encargo separado.

## Registrar antes de crear

El padre mantiene un registro pequeño y privado por iniciativa, fuera de los recursos que podría retirar. En un repositorio coordinador que vaya a conservarse, resuelve su directorio Git común y usa `<git-common-dir>/peqa/dirige/<id-ejecución>/recursos.md`; si el host ofrece un almacén durable de artefactos, puede usarlo. No escribas en rutas simbólicas o compartidas de procedencia dudosa. Si no hay almacén seguro, conserva los recursos e informa la limitación. Este registro operativo no activa el registro opcional de uso ni la memoria del proyecto.

Anota ID de ejecución, objetivo, modo y las siguientes columnas para **cada recurso**, incluidos los creados por hijos:

| Recurso y tipo | Propietario y origen | Identidad y estado inicial | Condición para retirarlo | Resultado y evidencia |
| --- | --- | --- | --- | --- |
| Ruta física exacta o ID del host; worktree, entorno, temporal, proceso o evidencia | Ejecución/agente y operación que lo creó | Ausencia previa o recurso preexistente; después, identidad de directorio/archivo, repositorio y registro Git o ID del host | Entrega e integración necesarias, consumidores y datos que deben conservarse | Pendiente, eliminado o conservado; motivo, referencias de commits y comprobación final |

Registra la intención y la ausencia previa antes de crear; confirma identidad y propiedad después. Para recursos que asigne el host, registra la solicitud y enlaza su recibo real al volver. Un recurso preexistente se marca ajeno a la limpieza, aunque se haya usado o modificado. Los hijos devuelven su inventario y el padre decide el retiro; no borres un checkout desde el hijo que aún lo está usando. Mantén un único escritor del registro y no guardes secretos ni contenidos de trabajo en él.

Usa directorios dedicados por ejecución para temporales y dependencias desechables. Evita reinstalar dependencias sin necesidad y respeta las cachés del gestor existente. Un recurso perdido del registro queda conservado; no reconstruyas propiedad por antigüedad ni escanees otros proyectos para ampliar la limpieza.

## Cerrar la ejecución

1. Consolida los recibos de los hijos y el resultado de integración. En `conservar`, registra todo como conservado y termina aquí, sin detener procesos ni eliminar archivos por esta política. Una instrucción específica de detener un servicio se atiende como parte de ese encargo, no como limpieza implícita.
2. Determina qué recursos ya no tienen consumidores. Finaliza o cancela únicamente tareas propias que el trabajo ya no necesite mediante la herramienta admitida y espera su terminación conforme a las reglas del host. Conserva recursos del checkout actual, de sesiones activas, de revisiones pendientes, de watchers que deben reanudar el trabajo o de una entrega aún bloqueada. Un hijo terminado o un PR abierto no bastan. No mates procesos ajenos para hacer posible la limpieza.
3. Conserva la entrega y su evidencia fuera de las rutas candidatas: código integrado, commits recuperables, informes, resultados de pruebas, capturas y artefactos necesarios. Una URL de PR o un enlace a un archivo local no prueban que exista una copia durable de la evidencia. Si se traslada evidencia, verifica contenido y acceso, actualiza enlaces y registra el destino antes de retirar el original. Esta política no borra ramas, stashes, refs de recuperación ni registros de review o memoria.
4. Revalida cada candidato inmediatamente antes de retirarlo con las condiciones siguientes. Si no se pueden comprobar todas, consérvalo con el motivo. Ante cambios concurrentes, errores de Git o permisos insuficientes, detén ese retiro; continúa con candidatos independientes.
5. Retira solo los candidatos aprobados por esa comprobación, de los más específicos hacia sus contenedores, y verifica el resultado. Conserva el registro final fuera de ellos. Al reanudar, un recurso ya ausente se marca así, sin borrar otra ruta que haya ocupado su lugar.

### Comprobación antes del retiro

- **Identidad y propiedad:** la ruta física o ID coincide con el recibo de creación y no fue sustituida, enlazada o reutilizada. Ni la raíz del proyecto, ni el checkout actual, ni sus antecesores son candidatos. Todos los descendientes quedan cubiertos por la comprobación; un recurso conservado protege los contenedores que lo borrarían. Las herramientas del host y la inspección local deben permitir descartar uso concurrente; un listado de sesiones vacío por sí solo no lo demuestra.
- **Contenido:** inspecciona cambios preparados y sin preparar, archivos nuevos y archivos ignorados. En worktrees incluye submódulos recursivos y repositorios anidados. No uses reset, stash o clean para convertir un candidato en limpio. Conserva cambios pendientes y archivos ignorados sin clasificar, incluidos `.env`, bases de datos y capturas. El nombre `node_modules`, `.venv` o `build` no prueba que todo su contenido sea reproducible: retira solo dependencias/salidas registradas como propias, reproducibles y sin datos únicos ni consumidores.
- **Commits:** antes de retirar un checkout, verifica que su HEAD y los de sus repositorios hijos sobreviven fuera de las rutas candidatas en referencias durables y objetos recuperables. Si falta una referencia, créala en el repositorio que se conserva y verifica el objeto; un HEAD detached o reflog temporal no basta. Con squash/rebase, verifica la integración del cambio sin exigir igualdad de SHA. Conserva el checkout si falta integración o recuperación comprobable.
- **Almacenes Git:** resuelve `.git`, `git-common-dir` y la administración de cada submódulo y worktree relacionado. Un directorio de administración puede contener los objetos de otros checkouts; conservar solo una rama en ese mismo directorio no protege sus objetos de un borrado. No retires ni purgues registros que mantengan almacenes o checkouts dependientes.
- **Operación admitida:** para recursos gestionados por T3, Codex o Claude, usa la operación documentada de su propietario, comprobando qué elimina y cómo afecta al hilo. Si falta una operación segura, conserva y explica. Para un worktree Git ordinario usa `git worktree remove` sin forzar. Si rechaza la operación, incluidos los casos con submódulos, consérvalo: no hagas fallback a `rm -rf`, `--force` ni `worktree prune` global. Los temporales ordinarios se retiran por su ruta exacta y comprobada, nunca mediante comodines o barridos del equipo.

La comprobación no es un lock contra terceros. Coordina el acceso y, si no puedes descartar una carrera, conserva el recurso. Ante interrupción abrupta no se garantiza el cierre: el registro permite reanudar y volver a comprobar, no autoriza a un hook a borrar por su cuenta.

### Informe de cierre

Informa modo, recursos eliminados, ausentes y conservados, motivos, referencias/destinos de recuperación y ubicación del registro. Verifica ausencia y desregistro cuando corresponda; una llamada que devolvió éxito no basta. Comprueba que commits y evidencia siguen accesibles. Si mides espacio, separa tamaño contabilizado de candidatos de variación de espacio libre antes/después: APFS, archivos compartidos y actividad simultánea impiden prometer que ambos coincidan. Si no mediste, informa «espacio recuperado no medido».

Ejemplo de cierre: «Modo automático. Retirados el worktree Git del verificador y sus datos de prueba; commit preservado en la rama indicada en el registro. Conservados el checkout actual y el entorno con una base de datos local. Capturas verificadas en el destino de evidencia. Espacio recuperado no medido. Registro: [ruta real]».
