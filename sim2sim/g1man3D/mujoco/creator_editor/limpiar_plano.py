#!/usr/bin/env python3
"""
Deja visibles solo unas capas (OCGs) concretas en un PDF con Optional Content Groups.

Uso:
    python3 keep_pdf_layers.py entrada.pdf salida.pdf

Por defecto mantiene encendidas solo estas capas:
    - 1-PAREDES1
    - 1-PAREDES2

También puedes cambiarlas:
    python3 keep_pdf_layers.py entrada.pdf salida.pdf --keep 1-PAREDES1 1-PAREDES2

Y puedes listar primero las capas detectadas:
    python3 keep_pdf_layers.py entrada.pdf /tmp/salida.pdf --list-only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

try:
    import pymupdf  # PyMuPDF moderno
except ImportError:  # compatibilidad con instalaciones antiguas
    import fitz as pymupdf  # type: ignore

DEFAULT_KEEP = ["1-PAREDES1", "1-PAREDES2"]


class LayerError(Exception):
    """Error controlado para problemas de capas OCG."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Genera un PDF donde solo quedan visibles por defecto las capas OCG "
            "indicadas en --keep. El resto se apaga."
        )
    )
    parser.add_argument("input_pdf", help="Ruta del PDF de entrada")
    parser.add_argument("output_pdf", help="Ruta del PDF de salida")
    parser.add_argument(
        "--keep",
        nargs="+",
        default=DEFAULT_KEEP,
        help=(
            "Nombres exactos de las capas a mantener visibles. "
            "Por defecto: 1-PAREDES1 1-PAREDES2"
        ),
    )
    parser.add_argument(
        "--password",
        default=None,
        help="Contraseña del PDF si está protegido",
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="Solo lista las capas detectadas y termina",
    )
    return parser.parse_args()


def authenticate_if_needed(doc, password: str | None) -> None:
    if not getattr(doc, "needs_pass", False):
        return

    if not password:
        raise LayerError(
            "El PDF está protegido con contraseña. Usa --password 'tu_clave'."
        )

    ok = doc.authenticate(password)
    if ok == 0:
        raise LayerError("La contraseña proporcionada no es válida.")


def get_ocgs(doc) -> Dict[int, dict]:
    ocgs = doc.get_ocgs()
    if not ocgs:
        raise LayerError(
            "Este PDF no contiene capas OCG (Optional Content Groups) detectables."
        )
    return ocgs


def summarize_layers(ocgs: Dict[int, dict]) -> List[Tuple[int, str, bool]]:
    rows: List[Tuple[int, str, bool]] = []
    for xref, info in ocgs.items():
        name = str(info.get("name", "<sin_nombre>"))
        on = bool(info.get("on", False))
        rows.append((xref, name, on))
    rows.sort(key=lambda item: (item[1].lower(), item[0]))
    return rows


def find_target_xrefs(ocgs: Dict[int, dict], keep_names: Iterable[str]) -> Tuple[List[int], List[str]]:
    keep_names_set = set(keep_names)
    found_xrefs: List[int] = []
    found_names: set[str] = set()

    for xref, info in ocgs.items():
        name = str(info.get("name", ""))
        if name in keep_names_set:
            found_xrefs.append(xref)
            found_names.add(name)

    missing = [name for name in keep_names if name not in found_names]
    return sorted(found_xrefs), missing


def set_only_selected_layers_visible(doc, ocgs: Dict[int, dict], keep_xrefs: List[int]) -> None:
    all_xrefs = sorted(ocgs.keys())
    off_xrefs = [xref for xref in all_xrefs if xref not in set(keep_xrefs)]

    # Dejamos OFF por defecto todo lo no mencionado, y explicitamos qué capas van ON/OFF.
    doc.set_layer(-1, on=keep_xrefs, off=off_xrefs, basestate="OFF")


def print_layers(rows: List[Tuple[int, str, bool]]) -> None:
    print("Capas detectadas en el PDF:")
    for xref, name, on in rows:
        state = "ON" if on else "OFF"
        print(f"  - xref={xref:<6} estado={state:<3} nombre={name}")


def main() -> int:
    args = parse_args()

    input_pdf = Path(args.input_pdf)
    output_pdf = Path(args.output_pdf)

    if not input_pdf.exists():
        print(f"[ERROR] No existe el archivo de entrada: {input_pdf}", file=sys.stderr)
        return 1

    if input_pdf.resolve() == output_pdf.resolve():
        print(
            "[ERROR] El PDF de salida debe ser distinto del PDF de entrada.",
            file=sys.stderr,
        )
        return 1

    try:
        with pymupdf.open(str(input_pdf)) as doc:
            authenticate_if_needed(doc, args.password)
            ocgs = get_ocgs(doc)
            rows = summarize_layers(ocgs)
            print_layers(rows)

            if args.list_only:
                print("\nModo --list-only activado. No se ha generado ningún PDF.")
                return 0

            keep_xrefs, missing = find_target_xrefs(ocgs, args.keep)

            if missing:
                raise LayerError(
                    "No se encontraron estas capas exactas en el PDF: "
                    + ", ".join(missing)
                )

            if not keep_xrefs:
                raise LayerError(
                    "No se ha encontrado ninguna capa objetivo para mantener visible."
                )

            set_only_selected_layers_visible(doc, ocgs, keep_xrefs)

            output_pdf.parent.mkdir(parents=True, exist_ok=True)
            doc.save(str(output_pdf), garbage=3, deflate=True)

        print("\n[OK] PDF generado correctamente.")
        print(f"Entrada: {input_pdf}")
        print(f"Salida : {output_pdf}")
        print("Capas visibles por defecto:")
        for name in args.keep:
            print(f"  - {name}")
        print("Todas las demás capas han quedado ocultas por defecto.")
        return 0

    except LayerError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover
        print(f"[ERROR] Fallo inesperado: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
