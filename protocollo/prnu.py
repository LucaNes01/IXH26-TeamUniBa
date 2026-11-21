"""Stima e confronto PRNU per immagini lineari allineate, anche Bayer."""

import hashlib
from collections.abc import Callable, Iterable, Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.ndimage import gaussian_filter

from .bayer import SCHEMI_BAYER, piani_bayer


def _matrice(valori: ArrayLike) -> NDArray[np.float64]:
    dati = np.asarray(valori, dtype=np.float64)
    if dati.ndim != 2 or min(dati.shape) < 3 or not np.isfinite(dati).all():
        raise ValueError("Serve una matrice bidimensionale finita di almeno 3 × 3.")
    return dati


def _residuo(immagine: ArrayLike) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.bool_]]:
    pixel = _matrice(immagine)
    if np.any((pixel < 0) | (pixel > 1)):
        raise ValueError("I pixel lineari devono essere normalizzati nell'intervallo [0, 1].")
    utilizzabili = (pixel > 0.05) & (pixel < 0.95)
    residuo = pixel - gaussian_filter(pixel, sigma=1, mode="reflect")
    return pixel, residuo, utilizzabili


def _contributo_prnu(immagine: ArrayLike) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    pixel, residuo, utilizzabili = _residuo(immagine)
    return np.where(utilizzabili, pixel * residuo, 0), np.where(utilizzabili, pixel**2, 0)


def _stima_prnu(immagini: Iterable[tuple[ArrayLike, ...]]) -> tuple[NDArray[np.float64], ...]:
    iteratore = iter(immagini)
    try:
        accumuli = tuple(_contributo_prnu(piano) for piano in next(iteratore))
    except StopIteration:
        raise ValueError("Servono almeno due immagini di riferimento.") from None
    numero_immagini = 1
    for piani in iteratore:
        for piano, (numeratore, denominatore) in zip(piani, accumuli, strict=True):
            contributo, pesi = _contributo_prnu(piano)
            if contributo.shape != numeratore.shape:
                raise ValueError("Le immagini di riferimento devono avere la stessa geometria.")
            numeratore += contributo
            denominatore += pesi
        numero_immagini += 1
    if numero_immagini < 2:
        raise ValueError("Servono almeno due immagini di riferimento.")
    return tuple(_normalizza_prnu(numeratore, denominatore) for numeratore, denominatore in accumuli)


def _normalizza_prnu(numeratore: NDArray[np.float64], denominatore: NDArray[np.float64]) -> NDArray[np.float64]:
    validi = denominatore > 0
    impronta = np.divide(numeratore, denominatore, out=np.zeros_like(numeratore), where=validi)
    if not np.any(validi) or np.ptp(impronta[validi]) == 0:
        raise ValueError("Le immagini di riferimento non contengono un'impronta utilizzabile.")
    impronta[validi] -= impronta[validi].mean()
    return impronta


def stima_prnu(immagini: Iterable[ArrayLike]) -> NDArray[np.float64]:
    """Stima il rumore moltiplicativo del sensore da immagini uniformi."""
    return _stima_prnu((immagine,) for immagine in immagini)[0]


def impronta_prnu(impronta: ArrayLike) -> str:
    """Identifica in modo canonico il riferimento da associare al certificato."""
    dati = _matrice(impronta).astype("<f8", copy=False)
    righe, colonne = dati.shape
    testata = f"TEAM-BARI-PRNU-GAUSS1-1\x00{righe}x{colonne}\x00".encode("ascii")
    return hashlib.sha256(testata + dati.tobytes(order="C")).hexdigest()


def punteggio_prnu(immagine: ArrayLike, impronta: ArrayLike) -> float:
    """Calcola la correlazione normalizzata fra residuo e PRNU attesa."""
    pixel, residuo, utilizzabili = _residuo(immagine)
    riferimento = _matrice(impronta)
    if pixel.shape != riferimento.shape:
        raise ValueError("L'immagine e l'impronta devono avere la stessa geometria.")
    utilizzabili &= riferimento != 0
    if np.count_nonzero(utilizzabili) < 3:
        raise ValueError("Pixel utilizzabili insufficienti per il confronto PRNU.")
    osservato = residuo[utilizzabili]
    atteso = (pixel * riferimento)[utilizzabili]
    osservato -= osservato.mean()
    atteso -= atteso.mean()
    norma = np.linalg.norm(osservato) * np.linalg.norm(atteso)
    if norma == 0 or not np.isfinite(norma):
        raise ValueError("Segnale insufficiente per il confronto PRNU.")
    return float(np.clip(np.dot(osservato, atteso) / norma, -1, 1))


def stima_prnu_bayer(mosaici: Iterable[ArrayLike]) -> tuple[NDArray[np.float64], ...]:
    """Stima quattro riferimenti, nell'ordine delle posizioni del blocco Bayer 2 × 2."""
    return _stima_prnu(piani_bayer(mosaico) for mosaico in mosaici)


def impronta_prnu_bayer(riferimenti: Sequence[ArrayLike], schema_bayer: str) -> str:
    """Vincola lo schema colore e i quattro riferimenti nel loro ordine spaziale."""
    if schema_bayer not in SCHEMI_BAYER or len(riferimenti) != 4:
        raise ValueError("Servono uno schema Bayer valido e quattro riferimenti PRNU.")
    testata = f"TEAM-BARI-PRNU-BAYER-1\x00{schema_bayer}\x00".encode("ascii")
    digest = hashlib.sha256(testata)
    for riferimento in riferimenti:
        digest.update(bytes.fromhex(impronta_prnu(riferimento)))
    return digest.hexdigest()


def punteggi_prnu_bayer(mosaico: ArrayLike, riferimenti: Sequence[ArrayLike]) -> tuple[float, ...]:
    """Restituisce una correlazione per ciascuna posizione del blocco Bayer."""
    if len(riferimenti) != 4:
        raise ValueError("Servono quattro riferimenti PRNU Bayer.")
    return tuple(punteggio_prnu(piano, riferimento)
                 for piano, riferimento in zip(piani_bayer(mosaico), riferimenti, strict=True))


def verifica_prnu_bayer(leggi_mosaico: Callable[[], ArrayLike], riferimenti: Sequence[ArrayLike],
                        schema: str, digest_atteso: str, soglia: float) -> bool:
    """Confronta il mosaico con una copia dei riferimenti vincolati al digest."""
    copia = tuple(np.array(piano, dtype=np.float64, copy=True) for piano in riferimenti)
    return (impronta_prnu_bayer(copia, schema) == digest_atteso
            and min(punteggi_prnu_bayer(leggi_mosaico(), copia)) >= soglia)
