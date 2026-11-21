"""Controllo strutturale del mosaico RAW e separazione delle posizioni Bayer."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray


SCHEMI_BAYER = ("RGGB", "GRBG", "GBRG", "BGGR")


@dataclass(frozen=True)
class GeometriaBayer:
    schema: str
    dimensioni: tuple[int, int]
    origine: tuple[int, int]


@dataclass(frozen=True)
class MosaicoBayer:
    pixel: ArrayLike
    geometria: GeometriaBayer


def verifica_struttura_bayer(mosaico: MosaicoBayer, attesa: GeometriaBayer) -> bool:
    """Confronta la geometria letta dal decoder con quella della calibrazione."""
    if (not isinstance(attesa, GeometriaBayer) or not isinstance(mosaico, MosaicoBayer)
            or mosaico.geometria != attesa or attesa.schema not in SCHEMI_BAYER
            or not isinstance(attesa.origine, tuple) or len(attesa.origine) != 2
            or any(type(coordinata) is not int or coordinata < 0 for coordinata in attesa.origine)):
        return False
    try:
        pixel = np.asarray(mosaico.pixel)
    except (TypeError, ValueError):
        return False
    return (pixel.ndim == 2 and min(pixel.shape) >= 6 and pixel.shape == attesa.dimensioni
            and pixel.dtype.kind in "fiu" and bool(np.isfinite(pixel).all())
            and bool(np.all((pixel >= 0) & (pixel <= 1))))


def piani_bayer(mosaico: ArrayLike) -> tuple[NDArray[np.float64], ...]:
    dati = np.asarray(mosaico, dtype=np.float64)
    if dati.ndim != 2 or min(dati.shape) < 6:
        raise ValueError("Serve un mosaico Bayer bidimensionale di almeno 6 × 6.")
    return (dati[::2, ::2], dati[::2, 1::2], dati[1::2, ::2], dati[1::2, 1::2])
