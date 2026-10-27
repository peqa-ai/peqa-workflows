# Mantener PEQA workflows

Estas reglas aplican al desarrollo de este plugin. El comportamiento de cada skill vive en su `SKILL.md` y en las referencias que enlaza.

## Nombres y distribución

- Todo skill usa el prefijo `pk-`, seguido de palabras en minúsculas separadas por guiones. Ejemplos: `pk-dirige`, `pk-memoria-recuerda`, `pk-memoria-extraer`.
- La carpeta `skills/<nombre>/` y el campo `name` de `SKILL.md` deben coincidir. Mantén el mismo nombre en invocaciones, enlaces, diagramas y `agents/openai.yaml`; su `default_prompt` referencia `$<nombre>`.
- Al renombrar, actualiza también los consumidores de scripts y los ejemplos de instalación. Evita registrar entradas duplicadas como aliases. Explica los cambios de comandos en el README.
- Conserva nombre, versión y licencia coherentes en los tres manifiestos del plugin. Aumenta la versión cuando cambie el paquete instalable; un cambio de nombres de skills en la serie `0.x` aumenta la versión menor.
- El prefijo de skills no determina las rutas de datos. Conserva `.peqa/memoria`, `.peqa-stack/memoria` y el registro de revisiones; cambiar esos contratos requiere una migración explícita.

## Escribir skills

- Mantén cada entrada pequeña: cuándo aplica, qué debe lograr y los límites que cambian sus decisiones. Lleva los detalles condicionales a referencias enlazadas y las reglas compartidas a una sola fuente.
- Diseña para cualquier persona y proyecto. Resuelve rutas, cuentas y recursos desde el entorno de uso. Los ejemplos usan datos sintéticos; las memorias pertenecen al proyecto elegido.
- El soporte se limita a T3 Code, Codex y Claude Code. Antes de cambiar preguntas, delegación o selección de modelos, lee [herramientas del entorno](references/runtime-tools.md). Para mensajería entre sesiones, lee [coordinación](skills/pk-dirige/references/coordination.md). Usa capacidades reales y respeta las reglas del host.
- Al modificar la revisión, conserva los límites y la elección de modelo de [pk-revisa](skills/pk-revisa/SKILL.md). Al modificar preguntas, conserva el presupuesto de [pk-idea](skills/pk-idea/SKILL.md). El padre sigue siendo responsable de integrar y decidir.
- Añade scripts o agentes reutilizables cuando resuelvan una necesidad concreta. Los helpers actuales usan la biblioteca estándar de Python; justifica cualquier dependencia nueva.
- Escribe instrucciones propias. Cita las fuentes de los contratos y conserva las atribuciones y licencias de cualquier material reutilizado.

## Documentar y comprobar

- Usa español en la documentación para personas. El README explica el uso con ejemplos y diagramas Mermaid que aclaren relaciones o decisiones; enlaza los detalles en lugar de repetirlos.
- Al tocar nombres o empaquetado, comprueba frontmatter, metadatos de interfaz, enlaces relativos y manifiestos. Conserva la política de invocación existente salvo un cambio solicitado.
- Si cambias un helper o su ruta, ejecuta `python3 -m unittest discover -s tests -v`. Para instrucciones, comprueba escenarios que puedan cambiar de comportamiento. Distingue validación estática, simulaciones y pruebas entre sesiones reales al informar resultados.
