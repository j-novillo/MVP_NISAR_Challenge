"""Comandos del pipeline, del catálogo NISAR y del procesado con token."""

from __future__ import annotations

import argparse
import logging
import sys

from dotenv import load_dotenv


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Priorización territorial de incendios forestales en Galicia (SAR)."
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    pipeline = sub.add_parser("pipeline", help="Ejecuta todas las fases y escribe el índice.")
    pipeline.add_argument("--max-escenas-s1", type=int, default=8)
    pipeline.add_argument("--resolucion", type=float, default=400, help="Metros de la rejilla Sentinel-1.")
    pipeline.add_argument("--forzar", action="store_true", help="Ignora la caché de municipios y de escenas.")

    sub.add_parser("nisar-buscar", help="Lista escenas NISAR L2 GCOV sobre Galicia (sin token).")

    nisar = sub.add_parser("nisar-procesar", help="Descarga y agrega NISAR GCOV. Exige EARTHDATA_TOKEN.")
    nisar.add_argument("--max-escenas", type=int, default=2)
    nisar.add_argument("--resolucion", type=float, default=200)
    nisar.add_argument("--conservar", action="store_true", help="No borra los HDF5 descargados.")
    nisar.add_argument("--escenas", nargs="+", default=None, help="Títulos (o prefijos) de gránulos concretos a procesar.")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    if args.comando == "pipeline":
        from prioridad_galicia.pipeline import ejecutar_pipeline

        ejecutar_pipeline(
            max_escenas_s1=args.max_escenas_s1,
            resolucion=args.resolucion,
            forzar=args.forzar,
        )
        return 0
    if args.comando == "nisar-buscar":
        from prioridad_galicia.sources.nisar import buscar_nisar

        catalogo = buscar_nisar()
        print(f"Escenas NISAR GCOV sobre Galicia: {catalogo['n_escenas']}")
        for coleccion, resumen in catalogo["colecciones"].items():
            print(f"  {coleccion}: {resumen}")
        return 0
    if args.comando == "nisar-procesar":
        from prioridad_galicia.sources.nisar import procesar_nisar
        from prioridad_galicia.sources.territorio import cargar_municipios

        municipios = cargar_municipios(forzar=False)
        procesar_nisar(
            municipios,
            max_escenas=args.max_escenas,
            resolucion_m=args.resolucion,
            conservar=args.conservar,
            escenas=args.escenas,
        )
        return 0
    parser.error(f"Comando desconocido: {args.comando}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
