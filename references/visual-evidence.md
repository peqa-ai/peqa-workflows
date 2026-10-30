# Evidencia visual

La evidencia visual permite entender de un vistazo un cambio o un defecto. El padre la prepara desde el estado que realmente comprobó: base, head del PR o cambio integrado. Un hijo la aporta si su encargo lo incluye, y el padre la contrasta antes de usarla.

## Elegir el formato

| Cambio | Evidencia |
| --- | --- |
| Interfaz visible: pantallas, componentes, estilos, textos o estados de error | Screenshots del estado nuevo de cada pantalla afectada. Añade el anterior cuando el cambio modifica algo existente y puedes obtenerlo sin preparar otro entorno |
| Comportamiento sin superficie visual: API, datos, colas, permisos, configuración o arquitectura | Diagrama Mermaid antes/después del flujo afectado |
| Ambos | Las dos |

Explica con texto los cambios de documentación, formato, renombres o versiones de dependencias.

## Screenshots

- Captura con un navegador automatizado ya disponible, como Playwright, o con las pruebas E2E del proyecto; para apps móviles, con el simulador o dispositivo que exponga el host. Si no puedes ejecutar la interfaz, declara la evidencia visual pendiente y continúa.
- Usa datos de prueba. Antes de mostrar o subir una imagen, comprueba que no muestra secretos, datos personales, tokens ni rutas privadas; vuelve a capturar si hace falta.
- Guarda las imágenes en un directorio temporal de la ejecución, fuera del árbol de trabajo. Con `dirige`, anótalas como evidencia en [el registro de recursos](../skills/dirige/references/cleanup.md).
- Escribe un texto alternativo que describa lo que se ve: `![Formulario con el botón Guardar deshabilitado tras un error de red](/ruta/absoluta/guardar-error.png)`.

## Diagramas antes/después

- Deriva «Antes» de la base y «Después» del head o del cambio integrado. Cita los archivos que sustentan cada parte y marca como supuesto lo que no comprobaste. Si el cambio crea algo nuevo, «Antes» indica que no existía.
- Dibuja solo el flujo que cambia, en dos bloques Mermaid etiquetados «Antes» y «Después», con `accTitle` y `accDescr` como texto alternativo. Resalta lo añadido o retirado.

## En la sesión

Muestra la evidencia al verificar el cambio y en el informe final. Si el cliente muestra imágenes locales, como T3 Code, usa una imagen Markdown con ruta absoluta; si no, entrega la ruta del archivo. Los diagramas van como bloque Mermaid.

## En el PR

Cuando el cambio tenga evidencia visual, añade una sección «Evidencia visual» a la descripción de cada PR que crees o actualices; un PR sin ella omite la sección. Los bloques Mermaid van como texto y GitHub los dibuja. Las imágenes se suben con `--attach`, disponible desde `gh` 2.99.0; comprueba `gh --version`.

```sh
gh pr create --title "$TITULO" --body-file "$CUERPO" --attach "$EVIDENCIA/guardar-error.png"
gh pr edit "$PR_URL" --body-file "$CUERPO" --attach "$EVIDENCIA/guardar-error.png"
gh pr comment "$PR_URL" --body-file "$CUERPO" --attach "$EVIDENCIA/guardar-error.png"
```

Escribe en el cuerpo la misma ruta absoluta que pasas a `--attach`. `gh` reemplaza la referencia por la URL subida y añade al final las imágenes que el cuerpo no mencione. Una imagen subida no puede borrarse, por eso la revisión de su contenido va antes. `gh pr review` no admite adjuntos: [el review publicado](../skills/revisa/references/report.md#publicar-en-el-pr) usa `gh pr comment`.

Después de publicar, comprueba que el cuerpo o comentario contiene las URLs subidas y ninguna ruta local; corrígelo si una subida falló. Esa copia es el destino durable de la evidencia: desde entonces el archivo local es un candidato ordinario de limpieza.

Si `gh` es anterior a 2.99.0 o rechaza la subida, conserva las imágenes en local, muéstralas en la sesión y declara en el PR y en el informe que no se subieron. Otro destino, como un commit en la rama, requiere que el usuario lo elija.

## En el review

Cuando el cambio revisado modifica comportamiento, el consolidado incluye su diagrama antes/después (base y head) y marca dónde falla cada hallazgo. Un hallazgo de interfaz lleva el screenshot del head revisado que lo muestra. El revisor señala la pantalla o el flujo de cada hallazgo y puede proponer el borrador del diagrama; el padre captura, verifica y coloca la evidencia según [el consolidado](../skills/revisa/references/report.md#plantilla-adaptable).

Fuentes: [ayuda de `gh pr comment`](https://cli.github.com/manual/gh_pr_comment), [notas de `gh` 2.99.0](https://github.com/cli/cli/releases/tag/v2.99.0) y [resolución de referencias de adjuntos](https://github.com/cli/cli/blob/trunk/internal/attachments/references.go), consultadas el 2026-10-30.
