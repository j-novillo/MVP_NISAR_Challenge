"""Descargas HTTP con reintentos. No registra cabeceras ni tokens."""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

from prioridad_galicia.config import USER_AGENT

logger = logging.getLogger(__name__)

SESION = requests.Session()
SESION.headers["User-Agent"] = USER_AGENT


def obtener(
    url: str,
    *,
    params: dict | None = None,
    timeout: int = 90,
    intentos: int = 4,
    headers: dict | None = None,
    data: Any = None,
    method: str = "GET",
) -> requests.Response:
    ultimo: Exception | None = None
    for intento in range(intentos):
        try:
            respuesta = SESION.request(
                method,
                url,
                params=params,
                data=data,
                timeout=timeout,
                headers=headers,
            )
            if respuesta.status_code == 429 or respuesta.status_code >= 500:
                raise requests.HTTPError(
                    f"HTTP {respuesta.status_code} en {url}", response=respuesta
                )
            respuesta.raise_for_status()
            return respuesta
        except requests.HTTPError as exc:
            codigo = exc.response.status_code if exc.response is not None else None
            if codigo is not None and 400 <= codigo < 500 and codigo != 429:
                raise
            ultimo = exc
        except requests.RequestException as exc:
            ultimo = exc
        espera = 2 ** intento
        logger.warning("Reintento %s/%s de %s en %ss (%s)", intento + 1, intentos, url, espera, ultimo)
        time.sleep(espera)
    raise RuntimeError(f"No se pudo descargar {url}: {ultimo}") from ultimo


def obtener_json(url: str, **kwargs: Any) -> Any:
    return obtener(url, **kwargs).json()
