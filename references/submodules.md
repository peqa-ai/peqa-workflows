# Trabajar desde el repositorio padre

Cuando una arquitectura agrupa servicios como Git submodules, recomienda abrir el proyecto en el repositorio padre. Ese es el punto de coordinación del conjunto; cada hijo conserva su historial, ramas, instrucciones y PRs. Si el usuario eligió trabajar solo en un hijo, respeta ese alcance e informa las dependencias externas pertinentes.

## Reconocer la estructura antes de editar o revisar

1. Identifica la raíz elegida con `git rev-parse --show-toplevel`. `git rev-parse --show-superproject-working-tree` permite detectar un padre desde un submódulo inicializado; repite hacia arriba cuando haya anidamiento, sin ampliar silenciosamente el proyecto elegido.
2. Lee `.gitmodules`, los gitlinks y `git submodule status --recursive`. Distingue el SHA registrado por el padre del HEAD y del trabajo sin commit de cada hijo. Un submódulo ausente no es un directorio vacío revisado: declara su contenido y descendientes desconocidos hasta poder inspeccionarlos. `-` indica no inicializado, `+` diferencia respecto al índice y `U` conflicto.
3. Conserva en el brief un mapa de los repositorios pertinentes: ruta relativa, padre inmediato, servicio/contratos, instrucciones aplicables, rama y SHA de trabajo, base y repositorio destino del PR. Resuelve remotos reales, incluidas URLs relativas y forks; elimina credenciales de cualquier URL que muestres. Comprueba la identidad Git/GitHub aplicable a cada repositorio.
4. Para un hijo necesario que falte, inicializa el commit fijado solo cuando el encargo y el entorno permitan esa escritura y descarga. Inspecciona primero cambios locales y checkouts compartidos. La forma habitual es `git submodule update --init --checkout --recursive -- <ruta>` desde su padre. No uses `--remote` para actualizar dependencias incidentalmente, ni fuerces, resetees o guardes en stash trabajo ajeno. La extracción de memoria sigue siendo de solo lectura.

Antes de delegar, aplica [coordinación entre sesiones](../skills/dirige/references/coordination.md) a los checkouts, contratos y recursos compartidos de los hijos. Delimita el repositorio y archivos de cada agente. El agente padre conserva la vista del conjunto. Un worktree del padre puede tener hijos sin inicializar; verifica el estado del checkout que realmente usará el agente y respeta el aislamiento provisto por el host.

## Crear PRs desde los hijos hacia el padre

Si el encargo incluye crear PRs para el cambio del conjunto, incluye **cada repositorio hijo modificado y cada padre cuyo gitlink cambie**, terminando en la raíz elegida. Un hijo sin cambios no necesita un PR vacío. Reutiliza PRs existentes del mismo trabajo cuando corresponda. Abrir PRs no autoriza fusionarlos ni desplegar.

1. Define por repositorio los cambios, base, rama de trabajo, dependencias y pruebas. Los hijos pueden estar en detached HEAD: prepara una rama de trabajo antes de crear commits. Cada repositorio mantiene sus propias instrucciones y autorización.
2. Comprueba y publica los cambios de los hijos, de los más profundos hacia arriba y respetando dependencias entre servicios. Crea sus PRs con base/destino verificados. Conserva URL completa, head, checks y dependencias de cada PR. Una revisión o prueba de un hijo no cubre a sus hermanos.
3. Actualiza en el padre inmediato únicamente los gitlinks del cambio autorizado a commits ya publicados y recuperables desde los remotos previstos. Revisa `git diff --submodule=log` y expande los diffs relevantes dentro de los hijos. El commit del padre no contiene archivos sin commit del hijo. No incorpores otros cambios de puntero encontrados en el checkout.
4. Repite para padres intermedios. Crea **al final el PR del repositorio padre**, con los cambios propios y gitlinks, enlaces a todos los PRs hijos participantes, SHAs fijados, orden de integración y evidencia de pruebas. Puede quedar en draft mientras haya dependencias pendientes; ya debe existir un cambio real que revisar.
5. Antes de fusionar un padre, verifica que los PRs hijos requeridos estén integrados y que sus SHAs fijados sean recuperables y pertenezcan al historial de las ramas destino acordadas. Un squash o rebase puede cambiar el SHA: actualiza los gitlinks afectados de abajo hacia arriba y vuelve a comprobar la combinación final. La evidencia anterior no cubre automáticamente esos nuevos SHAs. Sin autorización de merge, entrega los PRs y sus bloqueos.

Si falta acceso a un hijo, falla su publicación o no puede resolverse un SHA, entrega lo realizado y marca esa dependencia pendiente. No declares completa la entrega del conjunto. En T3 enlaza cada PR al crearlo, asumirlo o actualizarlo mediante push, siguiendo [las reglas de PR del host](runtime-tools.md#prs-y-entrega-en-t3); el agente padre coordina la vigilancia de los pendientes.

## Revisar el conjunto

Identifica cada PR por URL completa y conserva su contador en el repositorio correspondiente, según [presupuesto de revisión](../skills/revisa/references/budget.md). El máximo es tres por PR. Si un encargo independiente emite veredictos sobre varios PRs, comprueba y reserva una pasada para cada uno antes de despacharlo. Un PR agotado o de historial desconocido no se vuelve a revisar ocultándolo dentro del PR padre. El contexto de otro repositorio no equivale a haberlo revisado.

La revisión del padre comprueba los punteros y la compatibilidad de la combinación, además de sus archivos propios. No trata una actualización de gitlink como un cambio trivial de una línea: inspecciona el rango de commits incluido en el hijo y sus contratos afectados. Si faltan objetos o fuentes, declara cobertura parcial. Selecciona pruebas por impacto siguiendo [pruebas y blast radius](../skills/revisa/references/validation.md).

## Memoria de la arquitectura

Cuando el usuario pida recordar o recuperar esta arquitectura, aplica [memoria en repositorios con submódulos](project-memory.md#repositorios-con-submódulos). El mapa de trabajo y los estados de PR son transitorios; las relaciones duraderas y sus fuentes son memoria del proyecto.

## Fuentes de Git

[Modelo de submódulos y gitlinks](https://git-scm.com/docs/gitsubmodules), [estado e inicialización](https://git-scm.com/docs/git-submodule) y [diffs de submódulos](https://git-scm.com/docs/git-diff). Estas fuentes describen Git; el orden de PRs y la organización de memoria son decisiones de este workflow.
