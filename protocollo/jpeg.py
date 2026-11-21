"""Analisi forense di JPEG isolati contro riferimenti PRNU certificati."""

from __future__ import annotations

import hashlib
import io
from collections.abc import Iterable
from dataclasses import dataclass
from http.client import HTTPException
from typing import TYPE_CHECKING

from .credenziali import CredenzialeJPEG, verifica_credenziale_jpeg
from .dispositivi import ProvaIscrizione, RegistroDispositivi
from .ledger import XRPL_TESTNET_RPC, verifica_ancoraggio

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import ArrayLike, NDArray


@dataclass(frozen=True)
class RiferimentoJPEG:
    iscrizione: ProvaIscrizione
    tx_id_xrpl: str
    impronta: ArrayLike
    soglia: float

    def __post_init__(self):
        if isinstance(self.soglia, bool) or not 0 < self.soglia <= 1:
            raise ValueError("La soglia JPEG deve essere nell'intervallo (0, 1].")


@dataclass(frozen=True)
class ConfrontoJPEG:
    sensore_id: str
    chiave_dispositivo: str
    correlazione: float
    compatibile: bool


@dataclass(frozen=True)
class EsitoJPEG:
    esito: str
    confronti: tuple[ConfrontoJPEG, ...]
    credenziale: CredenzialeJPEG | None = None


def decodifica_jpeg(jpeg: bytes, modalita: str):
    from PIL import Image

    if not isinstance(jpeg, bytes) or not jpeg:
        raise ValueError("Serve il file JPEG.")
    try:
        with Image.open(io.BytesIO(jpeg), formats=("JPEG",)) as immagine:
            if immagine.width * immagine.height > 64_000_000:
                raise ValueError("JPEG troppo grande per il confronto.")
            # Mantiene le coordinate raster originali, senza applicare l'orientamento EXIF.
            return immagine.convert(modalita)
    except (OSError, Image.DecompressionBombError) as errore:
        raise ValueError("JPEG non leggibile.") from errore


def _decodifica(jpeg: bytes) -> NDArray[np.float64]:
    import numpy as np

    return np.asarray(decodifica_jpeg(jpeg, "L"), dtype=np.float64) / 255


def stima_prnu_jpeg(scatti: Iterable[bytes]) -> NDArray[np.float64]:
    """Stima il riferimento dai JPEG originali, uniformi e allineati del dispositivo."""
    from .prnu import stima_prnu

    return stima_prnu(_decodifica(jpeg) for jpeg in scatti)


def impronta_prnu_jpeg(impronta: ArrayLike) -> str:
    from .prnu import impronta_prnu

    return hashlib.sha256(b"TEAM-BARI-PRNU-JPEG-L-1\x00" + bytes.fromhex(impronta_prnu(impronta))).hexdigest()


def analizza_jpeg(jpeg: bytes, registro: RegistroDispositivi, catalogo: Iterable[RiferimentoJPEG], *,
                  conto_pubblicatore_xrpl: str, url_rpc_xrpl: str = XRPL_TESTNET_RPC,
                  radici_c2pa_pem: str | None = None) -> EsitoJPEG:
    """Controlla l'origine dichiarata e confronta i riferimenti del catalogo."""
    credenziale = None
    if radici_c2pa_pem is not None:
        credenziale = verifica_credenziale_jpeg(jpeg, radici_pem=radici_c2pa_pem)
        if credenziale.origine == "generata_ia":
            return EsitoJPEG("generata_ia", (), credenziale)

    import numpy as np

    from .prnu import punteggio_prnu

    pixel = _decodifica(jpeg)
    confronti = []
    for candidato in catalogo:
        prova = candidato.iscrizione
        if not registro.verifica_iscrizione(prova):
            continue
        certificato = prova.richiesta.certificato
        if certificato.prnu_jpeg_sha256 is None:
            continue
        try:
            riferimento = np.array(candidato.impronta, dtype=np.float64, copy=True)
            if (pixel.shape != riferimento.shape
                    or impronta_prnu_jpeg(riferimento) != certificato.prnu_jpeg_sha256):
                continue
            punteggio = punteggio_prnu(pixel, riferimento)
            if not verifica_ancoraggio(prova, candidato.tx_id_xrpl, conto_pubblicatore_xrpl, url_rpc=url_rpc_xrpl):
                continue
        except (AttributeError, HTTPException, KeyError, OSError, RuntimeError, TypeError, ValueError):
            continue
        confronti.append(ConfrontoJPEG(certificato.sensore_id, certificato.chiave_dispositivo.hex(),
                                       punteggio, punteggio >= candidato.soglia))
    compatibili = {confronto.chiave_dispositivo for confronto in confronti if confronto.compatibile}
    if not confronti:
        return EsitoJPEG("non_valutabile", (), credenziale)
    if len(compatibili) > 1:
        return EsitoJPEG("ambiguo", tuple(confronti), credenziale)
    esito = "compatibile" if compatibili else "nessuna_corrispondenza"
    return EsitoJPEG(esito, tuple(confronti), credenziale)
