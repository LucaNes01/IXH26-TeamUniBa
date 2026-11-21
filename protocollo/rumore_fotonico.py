"""Misura della risposta fotonica su coppie di RAW lineari di calibrazione."""

from collections.abc import Iterable
from dataclasses import dataclass
from math import isfinite

import numpy as np
from numpy.typing import ArrayLike


@dataclass(frozen=True)
class ProfiloFotonico:
    guadagno: float
    intercetta: float
    r2: float


def stima_profilo_fotonico(coppie: Iterable[tuple[ArrayLike, ArrayLike]]) -> ProfiloFotonico:
    """Stima la relazione tra segnale medio e varianza temporale.

    Ogni coppia usa due acquisizioni indipendenti con la stessa luce ed esposizione.
    Tra coppie si varia l'esposizione mantenendo fissi guadagno, area e modalità.
    """
    misure = []
    forma = None
    for prima, seconda in coppie:
        a = np.asarray(prima, dtype=np.float64)
        b = np.asarray(seconda, dtype=np.float64)
        if forma is None:
            forma = a.shape
        if (a.ndim != 2 or min(a.shape) < 3 or a.shape != forma or b.shape != forma
                or any(not np.isfinite(pixel).all() or np.any((pixel < 0) | (pixel > 1)) for pixel in (a, b))):
            raise ValueError("Servono RAW lineari normalizzati e con la stessa geometria.")
        media = (a.mean() + b.mean()) / 2
        varianza = np.var(a - b, ddof=1) / 2
        misure.append((media, varianza))

    if len(misure) < 3:
        raise ValueError("Servono almeno tre coppie a livelli di esposizione diversi.")
    segnale, varianza = np.asarray(misure).T
    if np.unique(segnale).size < 3:
        raise ValueError("Servono almeno tre livelli di segnale distinti.")
    x = segnale - segnale.mean()
    y = varianza - varianza.mean()
    guadagno = float(np.dot(x, y) / np.dot(x, x))
    intercetta = float(varianza.mean() - guadagno * segnale.mean())
    totale = np.dot(y, y)
    residuo = y - guadagno * x
    r2 = float(1 - np.dot(residuo, residuo) / totale) if totale > 0 else 0.0
    return ProfiloFotonico(guadagno, intercetta, r2)


def verifica_profilo_fotonico(profilo: ProfiloFotonico, riferimento: ProfiloFotonico, *,
                              tolleranza_guadagno: float, tolleranza_intercetta: float, r2_minimo: float) -> bool:
    """Confronta la misura con un riferimento e limiti fissati in calibrazione."""
    if (not all(isfinite(x) and x >= 0 for x in (tolleranza_guadagno, tolleranza_intercetta))
            or not 0 < r2_minimo <= 1):
        raise ValueError("Tolleranze o soglia di linearità del profilo fotonico non valide.")
    return (profilo.guadagno > 0 and riferimento.guadagno > 0 and profilo.r2 >= r2_minimo
            and abs(profilo.guadagno - riferimento.guadagno) <= tolleranza_guadagno
            and abs(profilo.intercetta - riferimento.intercetta) <= tolleranza_intercetta)
