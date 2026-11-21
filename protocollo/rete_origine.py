"""Scambio delle prove e raccolta indipendente dei voti di origine."""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Callable, Collection, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from http.client import HTTPException
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING
from urllib.request import Request, urlopen

from .analisi_ia import CommunityForensics224, QuorumIA, VotoIA
from .dispositivi import (
    ApprovazioneDispositivo, CertificatoSensore, ProvaIscrizione, RegistroDispositivi, RichiestaRegistrazione,
)
from .ledger import normalizza_id_transazione
from .origine import QuorumOrigine
from .provenienza import AttestazioneDispositivo, DichiarazioneSviluppo

if TYPE_CHECKING:
    from numpy.typing import ArrayLike

    from .jpeg import EsitoJPEG


_LIMITE_PACCHETTO = 64 * 1024 * 1024


def _json(dati: dict) -> bytes:
    return json.dumps(dati, default=lambda valore: base64.b64encode(valore).decode("ascii"),
                      separators=(",", ":")).encode("utf-8")


def _byte(valore: str) -> bytes:
    if not isinstance(valore, str):
        raise ValueError("Il campo binario deve essere in Base64.")
    return base64.b64decode(valore, validate=True)


def _voto(dati: dict) -> ApprovazioneDispositivo:
    return ApprovazioneDispositivo(_byte(dati["chiave_validatore"]), _byte(dati["firma"]))


@dataclass(frozen=True)
class PacchettoOrigine:
    raw: bytes | None
    foto: bytes
    attestazione: AttestazioneDispositivo
    iscrizione: ProvaIscrizione
    tx_id_xrpl: str
    dichiarazione: DichiarazioneSviluppo | None = None

    def serializza(self) -> bytes:
        dati = asdict(self)
        certificato = dati["iscrizione"]["richiesta"]["certificato"]
        if certificato["prnu_jpeg_sha256"] is None:
            del certificato["prnu_jpeg_sha256"]
        if self.dichiarazione is None:
            del dati["dichiarazione"]
        return _json({"versione": 3 if self.dichiarazione or self.raw is None else 2, **dati})

    @classmethod
    def da_json(cls, corpo: bytes) -> PacchettoOrigine:
        dati = json.loads(corpo)
        if dati["versione"] not in (2, 3):
            raise ValueError("Versione del pacchetto sconosciuta.")
        tx_id_xrpl = normalizza_id_transazione(dati["tx_id_xrpl"])
        att = dati["attestazione"]
        iscrizione = dati["iscrizione"]
        richiesta = iscrizione["richiesta"]
        certificato = richiesta["certificato"].copy()
        for nome in ("chiave_dispositivo", "chiave_autorita", "firma"):
            certificato[nome] = _byte(certificato[nome])
        prova = ProvaIscrizione(
            RichiestaRegistrazione(CertificatoSensore(**certificato), _byte(richiesta["sfida"]),
                                   _byte(richiesta["firma_dispositivo"])),
            _byte(iscrizione["impronta_comitato"]),
            tuple(_voto(voto) for voto in iscrizione["approvazioni"]),
        )
        attestazione = AttestazioneDispositivo(att["scatto_id"], _byte(att["chiave_dispositivo"]), _byte(att["firma"]))
        sviluppo = dati.get("dichiarazione") if dati["versione"] == 3 else None
        if sviluppo is not None:
            sviluppo = DichiarazioneSviluppo(**{k: _byte(sviluppo[k]) for k in ("raw_sha256", "politica_sha256", "firma")})
        raw = None if dati["versione"] == 3 and dati["raw"] is None else _byte(dati["raw"])
        return cls(raw, _byte(dati["foto"]), attestazione, prova, tx_id_xrpl, sviluppo)


def server_validatore(indirizzo: tuple[str, int], registro: RegistroDispositivi, quorum: QuorumOrigine, *,
                       chiave_validatore: bytes, firma: Callable[[bytes], bytes],
                       riferimenti: Sequence[ArrayLike],
                       analisi_jpeg: Callable[[bytes], EsitoJPEG] | None = None,
                       quorum_ia: QuorumIA | None = None,
                       rilevatore_ia: CommunityForensics224 | None = None) -> ThreadingHTTPServer:
    """Espone un validatore. Politica, riferimenti e firmatario sono locali al nodo."""
    if not quorum.verificatore_autorizzato(chiave_validatore):
        raise ValueError("Il validatore non appartiene al comitato della foto.")
    if (quorum_ia is None) != (rilevatore_ia is None):
        raise ValueError("Per votare sull'IA servono il quorum e il rilevatore.")
    percorsi = {"/approvazioni", "/rapporto", "/violazioni"}
    if analisi_jpeg is not None:
        percorsi.add("/analisi-jpeg")
    if quorum_ia is not None:
        percorsi.add("/voti-ia")

    class ValidatoreHTTP(BaseHTTPRequestHandler):
        timeout = 10

        def do_POST(self):
            if self.path not in percorsi:
                self.send_error(404)
                return
            try:
                lunghezza = int(self.headers.get("Content-Length", "0"))
                if not 0 < lunghezza <= _LIMITE_PACCHETTO:
                    self.send_error(413)
                    return
                corpo = self.rfile.read(lunghezza)
                if self.path == "/analisi-jpeg" and analisi_jpeg is not None:
                    rapporto = asdict(analisi_jpeg(corpo))
                    if rapporto.get("credenziale") is None:
                        rapporto.pop("credenziale", None)
                    self._rispondi_json(rapporto)
                    return
                if self.path == "/voti-ia" and quorum_ia is not None and rilevatore_ia is not None:
                    voto = quorum_ia.vota(corpo, chiave_validatore, rilevatore_ia, firma)
                    self._rispondi_json(asdict(voto))
                    return
                pacchetto = PacchettoOrigine.da_json(corpo)
                if pacchetto.attestazione.chiave_dispositivo == chiave_validatore:
                    self.send_error(422)
                    return
                opzioni = dict(iscrizione=pacchetto.iscrizione, tx_id_xrpl=pacchetto.tx_id_xrpl)
                if self.path == "/rapporto":
                    rapporto = quorum.valuta(registro, pacchetto.raw, pacchetto.foto, pacchetto.attestazione,
                                             riferimenti, dichiarazione=pacchetto.dichiarazione, **opzioni)
                    self._rispondi_json(asdict(rapporto))
                    return
                vota = quorum.messaggio_da_approvare
                if self.path == "/violazioni":
                    vota = quorum.messaggio_violazione
                    opzioni["dichiarazione"] = pacchetto.dichiarazione
                messaggio = vota(
                    registro, pacchetto.raw, pacchetto.foto, pacchetto.attestazione, riferimenti,
                    **opzioni,
                )
            except (AttributeError, KeyError, TypeError, ValueError, OSError):
                self.send_error(400)
                return
            if messaggio is None:
                self.send_error(422)
                return
            self._rispondi_json(asdict(ApprovazioneDispositivo(chiave_validatore, firma(messaggio))))

        def _rispondi_json(self, dati: dict):
            corpo = _json(dati)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

    return ThreadingHTTPServer(indirizzo, ValidatoreHTTP)


def _richiedi_json(url: str, corpo: bytes, timeout: float, tipo: str):
    richiesta = Request(url, data=corpo, headers={"Content-Type": tipo}, method="POST")
    with urlopen(richiesta, timeout=timeout) as risposta:
        return json.loads(risposta.read(64 * 1024))


def _chiedi_voto(url: str, corpo: bytes, timeout: float) -> ApprovazioneDispositivo | None:
    try:
        return _voto(_richiedi_json(url, corpo, timeout, "application/json"))
    except (HTTPException, OSError, ValueError, KeyError, TypeError):
        return None


def raccogli_approvazioni(pacchetto: PacchettoOrigine, registro: RegistroDispositivi, quorum: QuorumOrigine,
                          url_validatori: Collection[str], *, timeout: float = 5) -> tuple[ApprovazioneDispositivo, ...]:
    """Raccoglie i primi voti validi e distinti, scartando nodi indisponibili o risposte invalide."""
    accetta = quorum.filtro_voti(registro, pacchetto.raw, pacchetto.foto, pacchetto.attestazione,
                                iscrizione=pacchetto.iscrizione, tx_id_xrpl=pacchetto.tx_id_xrpl)
    corpo = pacchetto.serializza()
    if len(corpo) > _LIMITE_PACCHETTO:
        raise ValueError("Pacchetto di origine troppo grande.")
    voti = {}
    richieste = ThreadPoolExecutor()
    try:
        future = [richieste.submit(_chiedi_voto, url, corpo, timeout) for url in dict.fromkeys(url_validatori)]
        for risposta in as_completed(future):
            voto = risposta.result()
            if voto is not None and voto.chiave_validatore not in voti and accetta(voto):
                voti[voto.chiave_validatore] = voto
                if len(voti) >= quorum.soglia:
                    break
    finally:
        richieste.shutdown(wait=False, cancel_futures=True)
    return tuple(voti.values())


def verifica_prova_distribuita(pacchetto: PacchettoOrigine, registro: RegistroDispositivi, quorum: QuorumOrigine,
                                voti: Collection[ApprovazioneDispositivo]) -> bool:
    """Verifica le approvazioni e l'ancoraggio usando chiavi pubbliche e il nodo XRPL configurato."""
    return quorum.verifica(registro, pacchetto.raw, pacchetto.foto, pacchetto.attestazione, voti,
                          iscrizione=pacchetto.iscrizione, tx_id_xrpl=pacchetto.tx_id_xrpl)


def _chiedi_voto_ia(url: str, jpeg: bytes, timeout: float) -> VotoIA | None:
    try:
        dati = _richiedi_json(url, jpeg, timeout, "image/jpeg")
        return VotoIA(_byte(dati["chiave_validatore"]), dati["esito"], dati["punteggio"], _byte(dati["firma"]))
    except (HTTPException, OSError, ValueError, KeyError, TypeError):
        return None


def raccogli_voti_ia(jpeg: bytes, quorum: QuorumIA, url_validatori: Collection[str], *,
                      timeout: float = 5) -> tuple[VotoIA, ...]:
    """Raccoglie voti validi e concordi senza richiedere risposte da tutti i nodi."""
    if not isinstance(jpeg, bytes) or not 0 < len(jpeg) <= _LIMITE_PACCHETTO:
        raise ValueError("Servono i byte del JPEG, entro il limite del pacchetto.")
    impronta = hashlib.sha256(jpeg).digest()
    visti = set()
    per_esito = {}
    richieste = ThreadPoolExecutor()
    try:
        future = [richieste.submit(_chiedi_voto_ia, url, jpeg, timeout) for url in dict.fromkeys(url_validatori)]
        for risposta in as_completed(future):
            voto = risposta.result()
            if voto is None or voto.chiave_validatore in visti or not quorum.verifica_voto(impronta, voto):
                continue
            visti.add(voto.chiave_validatore)
            gruppo = per_esito.setdefault(voto.esito, [])
            gruppo.append(voto)
            if len(gruppo) >= quorum.soglia:
                return tuple(gruppo)
    finally:
        richieste.shutdown(wait=False, cancel_futures=True)
    return ()


def raccogli_violazioni(pacchetto: PacchettoOrigine, registro: RegistroDispositivi, quorum: QuorumOrigine,
                        url_validatori: Collection[str], *, timeout: float = 5) -> bool:
    if pacchetto.raw is None or pacchetto.dichiarazione is None:
        return False
    corpo = pacchetto.serializza()
    if len(corpo) > _LIMITE_PACCHETTO:
        raise ValueError("Pacchetto di origine troppo grande.")
    messaggio = quorum._messaggio_violazione(pacchetto.raw, pacchetto.foto, pacchetto.attestazione,
                                             pacchetto.iscrizione, pacchetto.tx_id_xrpl, pacchetto.dichiarazione)
    voti = {}
    with ThreadPoolExecutor() as richieste:
        future = [richieste.submit(_chiedi_voto, url, corpo, timeout) for url in dict.fromkeys(url_validatori)]
        for risposta in as_completed(future):
            voto = risposta.result()
            if voto and quorum._verifica_voto(voto, messaggio, pacchetto.attestazione.chiave_dispositivo):
                voti[voto.chiave_validatore] = voto
    return quorum.registra_violazione(registro, pacchetto.raw, pacchetto.foto, pacchetto.attestazione,
                                      tuple(voti.values()), iscrizione=pacchetto.iscrizione,
                                      tx_id_xrpl=pacchetto.tx_id_xrpl, dichiarazione=pacchetto.dichiarazione)
