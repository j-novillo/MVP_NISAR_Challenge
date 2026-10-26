# Accesibilidad: OpenStreetMap

No existe un fichero nacional abierto de bases de brigada, helipuertos y parques. El enunciado lo dice y propone OSM más los planes autonómicos. Este MVP usa solo OSM, vía Overpass, y lo etiqueta como proxy.

## Consultas

`sources/osm.py`. Servidores, en este orden, hasta que uno responde: `overpass.openstreetmap.fr`, `overpass-api.de`, `overpass.kumi.systems`. El de Francia fue el que contestó en las pruebas; el alemán devolvió 502 por saturación.

Parques: nodos y vías con `amenity=fire_station` dentro del bbox de Galicia, con `out center`. No se añaden `rescue_station` ni nombres de planes (INFOGA, PLADIGA) geocodificados a mano: eso sería inventar una coordenada.

Vías: `highway` igual a `motorway`, `trunk`, `primary` o `secondary`, con geometría (`out geom`). No entran las calles locales: hinchan la consulta y dicen poco sobre si un camión de extinción atraviesa el monte.

## Indicadores

- `dist_parque_km`. Distancia euclídea en EPSG:25830 desde `representative_point` del municipio al parque más cercano (`scipy.spatial.cKDTree`). Es línea recta, no tiempo de viaje. Un fiordo o un embalse no alarga el número.
- `densidad_viaria`. Kilómetros de esas vías que caen dentro del término, partido por el área en km². El cruce es `overlay` de líneas con polígonos.

Si Overpass no devuelve parques, `dist_parque_km` queda vacía. Si no devuelve vías, `densidad_viaria` queda vacía. El componente ACCES se apoya en el que exista. Si no existe ninguno, el peso de ACCES se reparte entre el resto y el manifiesto lo dice.

La fecha del extracto es la que declara el servidor Overpass en `osm3s.timestamp_osm_base` de la respuesta (no se copia aquí porque cambia). OSM se edita cada día: un parque nuevo no aparece hasta que alguien lo mapea.
