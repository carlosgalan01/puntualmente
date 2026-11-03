# Andén · puntualmente

Prototipo del Trabajo Fin de Máster (Máster en Inteligencia Artificial, Instituto Europeo de Posgrado): todos los trenes de Renfe en un mapa, con su retraso real, y modelos de IA que aprenden de lo que se va grabando.

**Web:** https://puntualmente-web.vercel.app

## Qué hace

- **Mapa en directo.** Cada 15 segundos se piden los datos abiertos de Renfe y cada tren aparece en su sitio, coloreado según su retraso.
- **Previsión IA.** Una red neuronal pequeña estima cuánto retraso llevará cada tren unos minutos después. Se compara siempre con la apuesta más simple, «seguirá igual».
- **Posibles incidencias.** Un detector de anomalías marca las líneas que van mucho peor que el resto de la red y dice si Renfe ya ha publicado un aviso.
- **Familias de líneas.** Un agrupamiento con k-medias reúne las líneas de Cercanías según cómo se comportan.
- **Moviola.** Reproduce acelerado lo grabado durante el día.

## Cómo está montado

| Pieza | Dónde | Qué hace |
|---|---|---|
| Caja negra | `grabar.py` + `.github/workflows/grabar.yml` | Cada 5 minutos guarda una foto de toda la red en `datos/AAAA-MM-DD.csv` y los avisos en `datos/avisos.json`. |
| Entreno nocturno | `modelo/entrenar.py`, `modelo/agrupar.py` + `.github/workflows/entrenar.yml` | Cada noche vuelve a entrenar la red y las familias con todo lo grabado y publica los resultados en `web/base/`. |
| Web | `web/` (Vercel) | `api/trenes.js` junta las fuentes en directo, `api/historia.js` sirve lo grabado para la moviola, e `index.html` es la página. La red neuronal se ejecuta en el navegador. |

## Los datos

Fuentes abiertas de Renfe: posiciones y retrasos de Cercanías (formato GTFS-Realtime, `gtfsrt.renfe.com`), el visor de larga y media distancia, y los horarios programados (GTFS). Cada fila de `datos/*.csv` es un tren en una foto:

`foto_utc, tipo, tren, lat, lon, retraso_min, siguiente_parada, extra, hora_dato`

En Cercanías, `extra` lleva el estado del tren y, desde el 3/11/2026 a las 21:05, el identificador del viaje (con él se sabe el núcleo). En larga distancia lleva origen>destino|producto.

## Limitaciones

- Renfe sólo publica el momento presente; la historia existe porque este repositorio la va guardando desde el 3/11/2026.
- El visor de larga distancia no está documentado como servicio público y puede cambiar sin aviso.
- La primera versión de los modelos se entrenó con 10 minutos de datos; sus números están en la web, sin maquillar.
- Prototipo académico. No es una herramienta de Renfe ni está relacionado con la compañía.

Hecho con ayuda de Claude (Anthropic) para el código y el análisis.
