# NoPorForEmule

Programa local para Windows que revisa la carpeta `Incoming` de eMule y, si la configuras, los archivos `*.part` de su carpeta `Temp`. Muestra un aviso cuando detecta un posible indicio de contenido pornográfico mientras se descarga un archivo. Lee el nombre de la descarga en el `*.part.met` correspondiente y muestra también el número del temporal. Si los metadatos faltan o no se pueden interpretar, muestra solo el nombre `*.part`.

## Inicio

1. Instala Python 3.14 en Windows y ejecuta **Iniciar.bat**. La primera ejecución instala las dependencias y el detector local; requiere conexión. Después, el análisis no envía imágenes ni vídeos a Internet.
2. Selecciona en la ventana las carpetas `Incoming` y `Temp` que figuran en las preferencias de eMule. Elige también `eMule.exe` si quieres usar el inicio conjunto.
3. Para abrir un archivo terminado con aviso previo, selecciónalo en la lista y pulsa **Abrir seleccionado…**. No se abren archivos `.part` desde este programa.
4. Si quieres iniciar ambos programas juntos, pulsa **Crear acceso directo en escritorio**. Si quieres que arranquen al entrar en Windows, activa **Iniciar ambos al entrar en Windows**. La opción puede desactivarse desde la misma ventana. Configúrala después de situar el programa en su carpeta definitiva.

El detector [NudeNet](https://github.com/notAI-tech/NudeNet) identifica partes del cuerpo expuestas. Un indicio no es una clasificación infalible de pornografía; pueden existir falsos positivos y falsos negativos. En vídeos terminados se prueban hasta cinco fotogramas. En los `.part` solo se avisa si hay contenido visual que se pueda decodificar y presente un indicio. La ausencia de aviso durante la descarga **no significa** que el archivo sea seguro: eMule puede no haber recibido todavía los fragmentos necesarios. En ese caso figura como «No analizado».

El programa lee los archivos de descarga y no los modifica, mueve ni borra. Guarda la configuración y la caché en `%LOCALAPPDATA%\NoPorForEmule` y puede recuperar la antigua carpeta `Incoming` de `%LOCALAPPDATA%\EmuleAviso\config.json`. Revisa los temporales cambiantes como máximo una vez cada 30 segundos por archivo. El aviso previo a la apertura solo funciona desde la ventana de NoPorForEmule; no intercepta los dobles clics en eMule, el Explorador ni otros programas.

Código: paquete `noporforemule`. Dependencias: `requirements.txt`. Para repetir las pruebas funcionales después del primer inicio: `".venv\Scripts\python.exe" -m unittest discover -s tests -v`. Licencia del proyecto: MIT (`LICENSE`); las dependencias de terceros conservan sus propias licencias.
