"""Certificati dei sensori e registrazione delle chiavi di cattura."""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import time
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from threading import Lock
from typing import TYPE_CHECKING

from crypto_kit import CROSSSigner

from .provenienza import AttestazioneDispositivo, verifica_cattura
from .revoche import StatoRevoche

if TYPE_CHECKING:
    from numpy.typing import ArrayLike

    from .bayer import GeometriaBayer, MosaicoBayer


@dataclass(frozen=True)
class CertificatoSensore:
    sensore_id: str
    chiave_dispositivo: bytes
    chiave_autorita: bytes
    valido_da: int
    valido_fino: int
    firma: bytes
    tecnologia_sensore: str | None = None
    prnu_sha256: str | None = None
    prnu_jpeg_sha256: str | None = None
    @property
    def dispositivo_id(self) -> str:
        identita = json.dumps([self.chiave_autorita.hex(), self.sensore_id], ensure_ascii=True).encode("ascii")
        return hashlib.sha256(b"TEAM-BARI-ID-SENSORE-1\x00" + identita).hexdigest().upper()


def messaggio_certificato_sensore(sensore_id: str, chiave_dispositivo: bytes, chiave_autorita: bytes,
                                 valido_da: int, valido_fino: int, *, tecnologia_sensore: str | None = None,
                                 prnu_sha256: str | None = None, prnu_jpeg_sha256: str | None = None) -> bytes:
    dati = {"protocollo": "TEAM-BARI-CERTIFICATO-SENSORE-1", "sensore_id": sensore_id,
            "chiave_dispositivo": chiave_dispositivo.hex(), "chiave_autorita": chiave_autorita.hex(),
            "valido_da": valido_da, "valido_fino": valido_fino}
    if tecnologia_sensore is not None:
        dati["protocollo"] = "TEAM-BARI-CERTIFICATO-SENSORE-2"
        dati["tecnologia_sensore"] = tecnologia_sensore
    if prnu_sha256 is not None:
        dati["protocollo"] = "TEAM-BARI-CERTIFICATO-SENSORE-3"
        dati["prnu_sha256"] = prnu_sha256
    if prnu_jpeg_sha256 is not None:
        dati["protocollo"] = "TEAM-BARI-CERTIFICATO-SENSORE-4"
        dati["prnu_jpeg_sha256"] = prnu_jpeg_sha256
    return json.dumps(dati, sort_keys=True, separators=(",", ":")).encode("ascii")


def impronta_certificato(certificato: CertificatoSensore) -> str:
    c = certificato
    messaggio = messaggio_certificato_sensore(
        c.sensore_id, c.chiave_dispositivo, c.chiave_autorita, c.valido_da, c.valido_fino,
        tecnologia_sensore=c.tecnologia_sensore, prnu_sha256=c.prnu_sha256, prnu_jpeg_sha256=c.prnu_jpeg_sha256,
    )
    return hashlib.sha256(b"TEAM-BARI-ANCORAGGIO-1\x00" + messaggio + b"\x00" + c.firma).hexdigest().upper()


def messaggio_registrazione_dispositivo(certificato: CertificatoSensore, sfida: bytes) -> bytes:
    return b"TEAM-BARI-REGISTRA-DISPOSITIVO-2\x00" + bytes.fromhex(impronta_certificato(certificato)) + sfida


@dataclass(frozen=True)
class RichiestaRegistrazione:
    certificato: CertificatoSensore
    sfida: bytes
    firma_dispositivo: bytes

    @property
    def impronta(self) -> bytes:
        messaggio = messaggio_registrazione_dispositivo(self.certificato, self.sfida)
        return hashlib.sha256(messaggio + hashlib.sha256(self.firma_dispositivo).digest()).digest()


@dataclass(frozen=True)
class ApprovazioneDispositivo:
    chiave_validatore: bytes
    firma: bytes


@dataclass(frozen=True)
class ProvaIscrizione:
    richiesta: RichiestaRegistrazione
    impronta_comitato: bytes
    approvazioni: tuple[ApprovazioneDispositivo, ...]


@dataclass(frozen=True)
class EsitoCatturaBayer:
    firma_valida: bool
    struttura_bayer: bool | None
    prnu: bool | None


class RegistroDispositivi:
    """Abilita chiavi di cattura certificate da un'autorità fidata."""

    def __init__(self, chiavi_autorita: Collection[bytes], chiavi_validatori: Collection[bytes],
                 soglia: int, *, orologio: Callable[[], float] = time.time,
                 soglia_revoca: int = 3, archivio_revoche: str = ":memory:"):
        self._cross = CROSSSigner()
        chiavi = tuple(chiavi_autorita)
        if not all(self._chiave_valida(pk) for pk in chiavi):
            raise ValueError("Le autorità devono avere chiavi pubbliche CROSS valide.")
        self._autorita = frozenset(chiavi)
        validatori = tuple(chiavi_validatori)
        if not all(self._chiave_valida(pk) for pk in validatori):
            raise ValueError("I validatori devono avere chiavi pubbliche CROSS valide.")
        self._validatori = frozenset(validatori)
        if len(self._validatori) != len(validatori) or self._validatori & self._autorita:
            raise ValueError("Servono chiavi di voto distinte tra loro e da quelle delle autorità.")
        if type(soglia) is not int or not 1 <= soglia <= len(self._validatori):
            raise ValueError("Soglia del quorum non valida.")
        self._soglia = soglia
        politica = {"autorita": sorted(pk.hex() for pk in self._autorita),
                    "validatori": sorted(pk.hex() for pk in self._validatori), "soglia": soglia}
        self._impronta_comitato = hashlib.sha256(json.dumps(politica, sort_keys=True).encode("ascii")).digest()
        self._revoche = StatoRevoche(archivio_revoche, soglia_revoca)
        self._orologio = orologio
        self._iscrizioni: dict[bytes, ProvaIscrizione] = {}
        self._sfide: dict[bytes, tuple[CertificatoSensore, bytes]] = {}
        self._lock = Lock()

    def numero_violazioni(self, dispositivo_id: str) -> int:
        return self._revoche.totale(dispositivo_id)

    def revocato(self, dispositivo_id: str) -> bool:
        return self.numero_violazioni(dispositivo_id) >= self._revoche.soglia

    def _chiave_valida(self, chiave: bytes) -> bool:
        return isinstance(chiave, bytes) and len(chiave) == self._cross.spec.pk_bytes

    def verifica_certificato(self, certificato: CertificatoSensore) -> bool:
        if not isinstance(certificato, CertificatoSensore):
            return False
        c = certificato
        if (not isinstance(c.sensore_id, str) or not c.sensore_id.strip()
                or not self._chiave_valida(c.chiave_dispositivo)
                or not self._chiave_valida(c.chiave_autorita) or c.chiave_autorita not in self._autorita
                or c.chiave_dispositivo in self._autorita or c.chiave_dispositivo in self._validatori
                or type(c.valido_da) is not int or type(c.valido_fino) is not int
                or not 0 <= c.valido_da <= self._orologio() < c.valido_fino):
            return False
        if self.revocato(c.dispositivo_id):
            return False
        tecnologia = c.tecnologia_sensore
        if tecnologia is not None and (not isinstance(tecnologia, str) or not tecnologia.strip()):
            return False
        if any(not isinstance(prnu, str) or not re.fullmatch(r"[0-9a-f]{64}", prnu)
               for prnu in (c.prnu_sha256, c.prnu_jpeg_sha256) if prnu is not None):
            return False
        messaggio = messaggio_certificato_sensore(
            c.sensore_id, c.chiave_dispositivo, c.chiave_autorita, c.valido_da, c.valido_fino,
            tecnologia_sensore=tecnologia, prnu_sha256=c.prnu_sha256, prnu_jpeg_sha256=c.prnu_jpeg_sha256,
        )
        return self._cross.verify(c.chiave_autorita, messaggio, c.firma)

    def emetti_sfida(self, certificato: CertificatoSensore) -> bytes:
        with self._lock:
            if not self.verifica_certificato(certificato):
                raise ValueError("Certificato del sensore non valido.")
            pk = certificato.chiave_dispositivo
            precedente = self._iscrizioni.get(pk)
            if precedente is not None and precedente.richiesta.certificato.valido_fino > self._orologio():
                raise ValueError("Dispositivo già registrato.")
            in_attesa = self._sfide.get(pk)
            if in_attesa is None or in_attesa[0] != certificato:
                in_attesa = (certificato, secrets.token_bytes(32))
                self._sfide[pk] = in_attesa
            return in_attesa[1]

    def verifica_richiesta(self, richiesta: RichiestaRegistrazione) -> bool:
        """Controllo pubblico eseguibile da ogni validatore sul transcript ricevuto."""
        if (not isinstance(richiesta, RichiestaRegistrazione) or not isinstance(richiesta.sfida, bytes)
                or len(richiesta.sfida) != 32 or not self.verifica_certificato(richiesta.certificato)):
            return False
        messaggio = messaggio_registrazione_dispositivo(richiesta.certificato, richiesta.sfida)
        return self._cross.verify(richiesta.certificato.chiave_dispositivo, messaggio, richiesta.firma_dispositivo)

    def messaggio_approvazione(self, richiesta: RichiestaRegistrazione) -> bytes:
        return b"TEAM-BARI-APPROVA-DISPOSITIVO-1\x00" + self._impronta_comitato + richiesta.impronta

    def _verifica_approvazioni(self, prova: ProvaIscrizione) -> bool:
        if (prova.impronta_comitato != self._impronta_comitato
                or not isinstance(prova.approvazioni, tuple)
                or not self._soglia <= len(prova.approvazioni) <= len(self._validatori)):
            return False
        messaggio = self.messaggio_approvazione(prova.richiesta)
        visti = set()
        for voto in prova.approvazioni:
            if not isinstance(voto, ApprovazioneDispositivo):
                return False
            pk = voto.chiave_validatore
            if (not isinstance(pk, bytes) or pk not in self._validatori or pk in visti
                    or not self._cross.verify(pk, messaggio, voto.firma)):
                return False
            visti.add(pk)
        return True

    def verifica_iscrizione(self, prova: ProvaIscrizione) -> bool:
        return (isinstance(prova, ProvaIscrizione) and self.verifica_richiesta(prova.richiesta)
                and self._verifica_approvazioni(prova))

    def verificatore_per_iscrizione(self, prova: ProvaIscrizione) -> RegistroDispositivi:
        """Verifica una prova pubblica e crea una vista locale per la singola iscrizione."""
        if not self.verifica_iscrizione(prova):
            raise ValueError("Prova pubblica di iscrizione non valida.")
        from copy import copy

        copia = copy(self)
        copia._iscrizioni = {}
        copia._sfide = {}
        copia._lock = Lock()
        copia._iscrizioni[prova.richiesta.certificato.chiave_dispositivo] = prova
        return copia

    def registra(self, richiesta: RichiestaRegistrazione,
                 approvazioni: Collection[ApprovazioneDispositivo]) -> ProvaIscrizione:
        with self._lock:
            if not isinstance(richiesta, RichiestaRegistrazione) or not self.verifica_certificato(richiesta.certificato):
                raise ValueError("Certificato del sensore non valido o scaduto.")
            chiave_dispositivo = richiesta.certificato.chiave_dispositivo
            in_attesa = self._sfide.get(chiave_dispositivo)
            if in_attesa != (richiesta.certificato, richiesta.sfida):
                raise ValueError("Sfida sconosciuta o già utilizzata.")
            if not self.verifica_richiesta(richiesta):
                raise ValueError("Firma di registrazione non valida.")
            prova = ProvaIscrizione(richiesta, self._impronta_comitato, tuple(approvazioni))
            if not self._verifica_approvazioni(prova):
                raise ValueError("Quorum di approvazioni non valido o insufficiente.")
            self._iscrizioni[chiave_dispositivo] = prova
            del self._sfide[chiave_dispositivo]
            return prova

    def certificato_pubblico(self, chiave_dispositivo: bytes) -> CertificatoSensore | None:
        """Restituisce il certificato reso consultabile dalla registrazione."""
        prova = self.prova_pubblica(chiave_dispositivo)
        return prova.richiesta.certificato if prova is not None else None

    def prova_pubblica(self, chiave_dispositivo: bytes) -> ProvaIscrizione | None:
        if not self._chiave_valida(chiave_dispositivo):
            return None
        with self._lock:
            return self._iscrizioni.get(chiave_dispositivo)

    def _certificato_per_cattura(self, raw: bytes, attestazione: AttestazioneDispositivo) -> CertificatoSensore | None:
        if not isinstance(attestazione, AttestazioneDispositivo):
            return None
        certificato = self.certificato_pubblico(attestazione.chiave_dispositivo)
        adesso = self._orologio()
        if (certificato is not None and not self.revocato(certificato.dispositivo_id)
                and certificato.valido_da <= adesso < certificato.valido_fino
                and verifica_cattura(raw, attestazione, {certificato.chiave_dispositivo})):
            return certificato
        return None

    def verifica_cattura(self, raw: bytes, attestazione: AttestazioneDispositivo) -> bool:
        return self._certificato_per_cattura(raw, attestazione) is not None

    def verifica_cattura_prnu(self, raw: bytes, attestazione: AttestazioneDispositivo,
                              impronta: ArrayLike | Sequence[ArrayLike], *,
                              decodifica: Callable[[bytes], ArrayLike], soglia: float,
                              schema_bayer: str | None = None) -> bool:
        """Verifica il RAW firmato e confronta i suoi pixel con il riferimento certificato."""
        from numpy import array

        from .prnu import impronta_prnu, punteggio_prnu, verifica_prnu_bayer

        self._valida_soglia_prnu(soglia)
        certificato = self._certificato_per_cattura(raw, attestazione)
        if certificato is None or certificato.prnu_sha256 is None:
            return False
        try:
            if schema_bayer is not None:
                return verifica_prnu_bayer(
                    lambda: decodifica(raw), impronta, schema_bayer, certificato.prnu_sha256, soglia,
                )
            riferimento = array(impronta, dtype="float64", copy=True)
            return (impronta_prnu(riferimento) == certificato.prnu_sha256
                    and punteggio_prnu(decodifica(raw), riferimento) >= soglia)
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _valida_soglia_prnu(soglia: float) -> None:
        if isinstance(soglia, bool) or not 0 < soglia <= 1:
            raise ValueError("La soglia PRNU deve essere nell'intervallo (0, 1].")

    def verifica_cattura_bayer(self, raw: bytes, attestazione: AttestazioneDispositivo,
                               riferimenti: Sequence[ArrayLike], *, geometria_attesa: GeometriaBayer,
                               decodifica: Callable[[bytes], MosaicoBayer], soglia: float) -> EsitoCatturaBayer:
        """Verifica firma, struttura Bayer e PRNU e restituisce i singoli esiti."""
        from .bayer import verifica_struttura_bayer
        from .prnu import verifica_prnu_bayer

        self._valida_soglia_prnu(soglia)
        certificato = self._certificato_per_cattura(raw, attestazione)
        if certificato is None:
            return EsitoCatturaBayer(False, None, None)
        try:
            mosaico = decodifica(raw)
            struttura = verifica_struttura_bayer(mosaico, geometria_attesa)
        except (TypeError, ValueError):
            struttura = False
        if not struttura or certificato.prnu_sha256 is None:
            return EsitoCatturaBayer(True, struttura, None)
        try:
            prnu = verifica_prnu_bayer(
                lambda: mosaico.pixel, riferimenti, geometria_attesa.schema, certificato.prnu_sha256, soglia,
            )
        except (TypeError, ValueError):
            prnu = False
        return EsitoCatturaBayer(True, True, prnu)
