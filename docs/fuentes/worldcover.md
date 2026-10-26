# WorldCover (contexto, no entra en el índice)

ESA WorldCover 2021, versión v200, servida como COG en Planetary Computer (colección `esa-worldcover`). Clases usadas: 10 (árbol) y 20 (matorral). `frac_forestal` es la fracción de píxeles válidos del municipio en esas dos clases, leídos a unos 200 m (vecino más próximo, para no inventar clases intermedias).

No entra en COMB ni en ningún peso. Está en la ficha para leer si un VH alto ocurre en un término forestal o en otro tipo de cubierta. Si la lectura de las teselas falla, la columna queda vacía y no se sustituye por un porcentaje medio de Galicia.

Código: `sources/worldcover.py`, función `anadir_worldcover`.
