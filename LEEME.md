# PUEBLOS 1.7.0 — la web de tus pueblos visitados

Programa para Windows que crea y publica tu web de pueblos: https://locometopa.github.io/pueblos/
También tienes un panel para el móvil: https://locometopa.github.io/pueblos/gestion/

## Qué hay en esta carpeta

| | |
|---|---|
| **PUEBLOS.bat** | Abre el programa (doble clic). La primera vez instala lo que haga falta. |
| PUEBLOS.exe | Opcional: lo mismo, como programa. Se crea con `crear_exe.bat`. |
| crear_exe.bat | Crea o vuelve a crear PUEBLOS.exe. |
| requirements.txt | Lista de librerías que necesita el programa. |
| LEEME.md | Este archivo. |
| pueblos.py, nucleo | El programa. No hace falta tocarlos. |
| config.json | Tus ajustes (y tus claves: no lo compartas). |
| repo | Tus pueblos y fotos, sincronizados con GitHub. **No lo borres.** |
| sitio | Vista previa de la web en tu PC. Se crea sola al pulsar «Vista previa»; se puede borrar. |

## Instalar (una sola vez)

1. Instala **Python** desde https://www.python.org/downloads/ (marca *Add python.exe to PATH*).
2. Instala **Git for Windows** desde https://git-scm.com/download/win (opciones por defecto).
3. Doble clic en **PUEBLOS.bat**. La primera vez tarda un poco porque instala lo necesario, y crea el acceso
   directo «PUEBLOS» (con su icono) en el escritorio y en el menú Inicio. Desde entonces, ábrelo con él.

## Uso

- **Mapa / Visitados / Por visitar**: tus pueblos. Clic en uno para editarlo.
- **Revisar**: lo que le falta a cada pueblo (ubicación, fecha, fotos, información…). Clic para arreglarlo.
- **＋ Añadir**: fotos de un viaje (lee el GPS y crea los pueblos solos), un pueblo visitado o uno por visitar,
  o **💡 Ideas de pueblos** (Los Pueblos más Bonitos de España y pueblos con patrimonio cerca de los tuyos).
- **Editor de un pueblo**: fotos (tuyas o de internet con licencia libre), Wikipedia, texto con IA,
  fiestas y tus notas («- » hace una lista, «★ » destaca una frase, **palabras** en negrita).
- **🎨 Diseño**: estilo de página (Clásica, Revista, Álbum de viaje, Moderna), cabecera, colores,
  modo claro/oscuro, tipografía, logo y qué secciones se muestran. «Vista previa» (abajo a la izquierda) lo enseña al momento.
- **Publicar**: sube los cambios (el botón dice cuántos tienes sin publicar); la web se actualiza en 1–2 minutos
  (abajo se ve 🟡 / ✅ / ❌). Al cerrar el programa te avisa si queda algo sin publicar.
- **🌐 Mi web ▾** (abajo): abrir tu web y copiar su enlace, abrir el panel del móvil y traer ya lo hecho
  en él (también llega solo al abrir el programa y al publicar), y ver tus archivos en GitHub.
  A su lado, **⚙** (Ajustes) y **?** (esta ayuda).
- **Ajustes** (⚙), en pestañas: **GitHub** (repositorio y token), **Inteligencia artificial** (la IA que uses: Claude,
  ChatGPT, Gemini u otra), **Copias** (un .zip semanal en tu NAS, un disco USB…) y **Programa** (aspecto claro/oscuro,
  tamaño de las fotos, acceso directo, y la versión con «Buscar actualizaciones» y las novedades).
- **Completar la información** de los pueblos (Wikipedia, Wikidata, web oficial, Wikivoyage, OpenStreetMap, fiestas…)
  está en **Revisar**, con el botón «📚 Completar la información de todos».

**En el móvil** (panel de gestión): «📌 Capturar» busca con el GPS los pueblos donde estás y te deja elegir
antes de guardarlo (sin cobertura guarda la posición y busca el pueblo al volver a tenerla). Luego, en «Revisar» (en el móvil o en el programa), decides si
lo visitaste, lo dejas «Por visitar» o lo descartas. «📍 Estoy aquí» marca como visitado hoy el pueblo donde estás (y te deja hacer una
foto), y la pestaña «✔ Revisar» enseña lo que le falta a cada pueblo.

## Actualizaciones

Al abrir el programa, si hay una versión nueva en GitHub te lo pregunta, se actualiza solo y se reinicia
(también si lo abres con PUEBLOS.exe). Tus pueblos, fotos y ajustes no se tocan. También puedes pulsar
**la versión** (arriba a la izquierda, bajo «PUEBLOS») → «Acerca de» → **Buscar actualizaciones**.

## Historial

- **1.7.0** Menús y Ajustes reorganizados: Ajustes en pestañas por tema (GitHub · IA · Copias · Programa), la versión y novedades dentro de «Programa», y sin opciones repetidas.
- **1.6.8** El PUEBLOS.exe (opcional) ya se crea con todo dentro (se arreglaba «No module named requests»). Añadido requirements.txt.
- **1.6.7** Arreglado «Algo ha fallado» al sincronizar en un PC nuevo cuando ya existía una carpeta «repo» vacía.
- **1.6.6** En el móvil, el crédito de la foto de portada de cada pueblo va al pie, sin tapar el nombre ni la fecha.
- **1.6.5** Mapa de la web con más espacio arriba y a los lados; el globo con el nombre ya no se corta en los bordes.
- **1.6.4** Ubicación más precisa al añadir un pueblo (pueblos de España antes que calles o lugares de fuera, el punto del
  núcleo y no el centro del término; si hay varios, lista con mapa y distancia a tus pueblos). Mapa pequeño en la ficha
  (programa y móvil) que se actualiza al momento; si cambias el nombre o la provincia se vuelve a ubicar solo.
- **1.6.3** Panel del móvil con nuevo diseño «Cuaderno» (de noche por defecto; en Ajustes del panel: Noche, Día o Automático) e iconos planos de color.
- **1.6.2** «Capturar» enseña la lista de pueblos posibles (y los tuyos cercanos) antes de confirmar.
- **1.6.1** Botón «📌 Capturar» en el móvil: guarda el pueblo por el que pasas para revisarlo luego.
- **1.6** El dibujo de la cabecera cambia con la hora de quien visita (amanecer, día, atardecer y noche) y
  botón ☀/☾ en la web para pasar de claro a oscuro (se recuerda). Los dos se pueden quitar en Diseño.
- **1.5.4** Icono propio (la casita con campanario) en la ventana, la barra de tareas y el .exe; accesos directos
  en el escritorio y el menú Inicio (se crean solos; también en Ajustes → General).
- **1.5.3** Menús con el estilo del programa y sin repetir: «Mi web ▾» agrupa todo lo de la web y el móvil;
  «Acerca de» solo versión, actualizaciones y novedades; Mi web, Ajustes y Ayuda en una fila.
- **1.5.2** Botón «❓ Ayuda» en la barra lateral, con estas instrucciones dentro del programa.
- **1.5.1** Ajustes en pestañas (General, Inteligencia artificial, Copia de seguridad).
- **1.5** «Acerca de» al pulsar la versión, con «Buscar actualizaciones», enlaces y novedades.
- **1.4** «Escapadas posibles» con tus pendientes cercanos; «Estoy aquí» y «Revisar» en el móvil; ideas de
  pueblos; copia de seguridad automática.
- **1.3** «Última visita» en la portada; programa más ordenado (botón «＋ Añadir», menú «Mi web», sin botones
  repetidos), apartado «Revisar» y aviso de cambios sin publicar.
- **1.2** Limpieza: menos archivos (PUEBLOS.bat instala lo necesario; crear_exe.bat no deja restos);
  el .exe también se actualiza solo.
- **1.1** Estilos de página entera; artículo de otra Wikipedia (traducido con IA) si la española es corta; más datos de Wikidata.
- **1.0** Web oficial del ayuntamiento, guía de Wikivoyage, distinciones, lugares de OpenStreetMap; fotos de Flickr y otras (Openverse).
- **0.9** Fiestas de cada pueblo sin IA y «Próximas fiestas»; notas como cuaderno; tiempo compacto y fichas de «Qué ver».
- **0.8** Varias IAs; el tiempo, mapa y pueblos cercanos en cada ficha.
- **0.7** Vista previa al compartir por WhatsApp; web y panel instalables en el móvil; línea del tiempo.
- **0.6** Apartado Diseño, vista previa en vivo, token de GitHub, actualizaciones automáticas.
- **0.5 y anteriores** Mapa que se destapa, panel del móvil, cabecera ilustrada, información ampliada.
