---
name: pk-dirige
description: Use when a user requests implementation coordinated through agents, explicitly invokes pk-dirige, or asks to carry a multi-part change through integration and verification.
---

# PK dirige

El padre responde por el resultado completo: entiende, coordina, divide, delega, integra y verifica. La ejecución normal usa subagentes. La invocación explícita autoriza esa delegación y mensajes breves de coordinación con agentes o sesiones pertinentes al mismo trabajo, dentro de los permisos del host; no autoriza cambiar objetivos ajenos. Si el skill se activa implícitamente, conserva la autorización de mensajería ya existente y las reglas superiores del entorno.

Si recibiste una tarea delegada, cumple ese encargo y devuelve evidencia al padre. Comunícale inmediatamente solapamientos, cambios de contrato y bloqueos; la coordinación con otras sesiones, preguntas y revisiones pertenece al padre. Delega de nuevo o contacta otros propietarios solo si su encargo lo permite expresamente.

## Dirigir el cambio

Antes de asignar o editar, ejecuta [descubrimiento y coordinación](references/coordination.md): identifica sesiones pertinentes, lee su alcance y acuerda el reparto cuando haya recursos compartidos. Conserva esa situación en el brief; revalídala si cambian alcance, checkout o servicio. Un listado vacío, un mensaje enviado o el silencio no prueban exclusividad.

1. Lee las instrucciones y el estado actual necesarios para fijar objetivo, criterios de aceptación, límites y decisiones pendientes. Resuelve hechos inspeccionando el proyecto. Cuando una decisión de producto o implementación cambie materialmente el resultado, carga `pk-idea` mediante el mecanismo de skills disponible o lee [su entrada incluida](../pk-idea/SKILL.md). Continúa el trabajo independiente mientras llega una respuesta necesaria.
2. Elige la ruta de ejecución descrita en [runtimes](references/runtimes.md). En T3 Code usa sus herramientas de orquestación según las reglas del host; fuera usa los subagentes nativos de Codex o Claude Code. Otro cliente queda fuera del soporte del stack. Conserva el modelo del padre para implementación salvo una preferencia explícita o una selección justificada que el entorno permita. Si no existe una ruta de subagentes en un cliente soportado, comunica la limitación y ejecuta directamente lo que el usuario autorizó.
3. Divide por entregables y dependencias. Asigna propietario, archivos o módulo, requisitos, comandos relevantes y criterio de terminación a cada hijo. Entrega contexto mínimo y fuentes originales. Indica que comparte el código con otros y debe acomodar sus cambios. Paraleliza trabajo independiente dentro de la capacidad disponible; mantén un único editor por conjunto de archivos.
4. El padre resuelve decisiones transversales e integra. Mantén informados a los propietarios afectados ante cambios de contrato, bloqueos o liberación del recurso; consolida novedades y evita intercambios de acuses. Lee los cambios y comprueba comportamiento y contratos entre módulos. Un informe de un hijo es una afirmación que contrastar con el código, los resultados y los requisitos. Corrige hallazgos pequeños directamente; evita nuevas delegaciones que no aporten trabajo independiente.
5. Cuando corresponda revisión del cambio, carga `pk-revisa` o lee [su entrada incluida](../pk-revisa/SKILL.md). El padre mantiene el control, el presupuesto por PR y la decisión sobre cada hallazgo. La revisión no abre otra cadena de coordinadores.
6. Completa la entrega solicitada con pruebas pertinentes y el estado real de sus PRs. En T3 enlaza cada PR creado o actualizado y usa su watcher si queda trabajo a la espera de checks o revisiones; entrega al usuario con el watcher retirado. Publicar, desplegar o hacer merge requiere la autorización aplicable, que puede estar ya dada. No vuelvas a pedirla si existe.

## Cuándo sugerir otro mecanismo

Sugiere workflows o swarms cuando una ejecución larga, repetible o con muchas ramas independientes justifique su configuración. Explica el beneficio concreto y su costo. Usa esos mecanismos solo si el usuario los elige; la ruta normal sigue siendo subagentes. Crea hilos de nivel superior únicamente cuando el usuario pida nuevos hilos.

Al terminar informa qué se entregó, evidencia observada, resultado de revisión, PR y head si existen, y cualquier pendiente material. Evita narrar cada interacción entre agentes.
