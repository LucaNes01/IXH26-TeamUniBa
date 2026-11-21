"""Approvazioni indipendenti per la provenienza di una foto specifica."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Collection
from dataclasses import dataclass
from http.client import HTTPException
from typing import TYPE_CHECKING

from crypto_kit import CROSSSigner

from .dispositivi import ApprovazioneDispositivo, ProvaIscrizione, RegistroDispositivi
from .ledger import XRPL_TESTNET_RPC, impronta_iscrizione, normalizza_id_transazione, verifica_ancoraggio
from .provenienza import AttestazioneDispositivo, DichiarazioneSviluppo, messaggio_cattura_dispositivo, verifica_cattura

if TYPE_CHECKING:
    from .bayer import GeometriaBayer, MosaicoBayer


@dataclass(frozen=True)
class RapportoOrigine:
    firma_raw: bool | None = None
    bayer: bool | None = None
    prnu: bool | None = None
    derivazione: str = "inconcludente"
    firma_coppia: bool = False

    @property
    def approvabile(self):
        return self.firma_raw and self.bayer and self.prnu and self.derivazione == "confermata"

    @property
    def attribuibile(self):
        return self.firma_coppia and self.firma_raw and self.bayer and self.prnu and self.derivazione == "incompatibile"


class QuorumOrigine:
    """Comitato configurato separatamente dal registro dei dispositivi."""

    def __init__(self, validatori: Collection[bytes], soglia: int, politica_sha256: bytes, *,
                 geometria_attesa: GeometriaBayer, decodifica: Callable[[bytes], MosaicoBayer],
                 soglia_prnu: float, elabora: Callable[[bytes], bytes], conto_pubblicatore_xrpl: str,
                 url_rpc_xrpl: str = XRPL_TESTNET_RPC):
        self._cross = CROSSSigner()
        chiavi = tuple(validatori)
        if not all(isinstance(pk, bytes) and len(pk) == self._cross.spec.pk_bytes for pk in chiavi):
            raise ValueError("Servono chiavi pubbliche CROSS valide.")
        self._validatori = frozenset(chiavi)
        if len(chiavi) != len(self._validatori) or type(soglia) is not int or not 1 <= soglia <= len(chiavi):
            raise ValueError("Servono validatori distinti e una soglia valida.")
        if not isinstance(politica_sha256, bytes) or len(politica_sha256) != 32:
            raise ValueError("Serve l'impronta SHA-256 della politica di verifica.")
        if isinstance(soglia_prnu, bool) or not 0 < soglia_prnu <= 1:
            raise ValueError("La soglia PRNU deve essere nell'intervallo (0, 1].")
        if not isinstance(conto_pubblicatore_xrpl, str) or not conto_pubblicatore_xrpl.strip():
            raise ValueError("Serve il conto XRPL autorizzato a pubblicare le iscrizioni.")
        self._soglia = soglia
        self._geometria = geometria_attesa
        self._decodifica = decodifica
        self._soglia_prnu = float(soglia_prnu)
        self._politica = politica_sha256
        self._elabora = elabora
        self._conto_xrpl = conto_pubblicatore_xrpl
        self._rpc_xrpl = url_rpc_xrpl
        politica = {"validatori": sorted(pk.hex() for pk in chiavi), "soglia": soglia,
                    "politica": politica_sha256.hex(), "soglia_prnu": self._soglia_prnu,
                    "bayer": geometria_attesa.schema, "dimensioni": geometria_attesa.dimensioni,
                    "origine": geometria_attesa.origine, "conto_xrpl": conto_pubblicatore_xrpl}
        self._impronta = hashlib.sha256(json.dumps(politica, sort_keys=True).encode("ascii")).digest()

    def _messaggio(self, raw: bytes, foto: bytes, attestazione: AttestazioneDispositivo,
                   iscrizione: ProvaIscrizione, tx_id_xrpl: str) -> bytes:
        cattura = messaggio_cattura_dispositivo(
            attestazione.scatto_id, hashlib.sha256(raw).digest(), attestazione.chiave_dispositivo,
        )
        return (b"TEAM-BARI-APPROVA-ORIGINE-3\x00" + self._impronta + hashlib.sha256(cattura).digest()
                + hashlib.sha256(attestazione.firma).digest() + hashlib.sha256(foto).digest()
                + bytes.fromhex(impronta_iscrizione(iscrizione)) + bytes.fromhex(normalizza_id_transazione(tx_id_xrpl)))

    def _ancoraggio_valido(self, iscrizione: ProvaIscrizione, tx_id_xrpl: str) -> bool:
        try:
            return verifica_ancoraggio(iscrizione, tx_id_xrpl, self._conto_xrpl, url_rpc=self._rpc_xrpl)
        except (AttributeError, HTTPException, KeyError, OSError, RuntimeError, TypeError, ValueError):
            return False

    def valuta(self, registro, raw: bytes | None, foto, attestazione, riferimenti, *, iscrizione,
               tx_id_xrpl, dichiarazione: DichiarazioneSviluppo | None = None) -> RapportoOrigine:
        try:
            vista = registro.verificatore_per_iscrizione(iscrizione)
        except ValueError:
            return RapportoOrigine()
        if not foto or not self._ancoraggio_valido(iscrizione, tx_id_xrpl):
            return RapportoOrigine()
        chiave = iscrizione.richiesta.certificato.chiave_dispositivo
        coppia = (dichiarazione is not None and attestazione.chiave_dispositivo == chiave
                  and dichiarazione.politica_sha256 == self._politica
                  and (raw is None or hashlib.sha256(raw).digest() == dichiarazione.raw_sha256)
                  and self._cross.verify(chiave, dichiarazione.messaggio(foto, attestazione), dichiarazione.firma))
        if raw is None:
            return RapportoOrigine(firma_coppia=coppia)
        esito = vista.verifica_cattura_bayer(
            raw, attestazione, riferimenti, geometria_attesa=self._geometria,
            decodifica=self._decodifica, soglia=self._soglia_prnu,
        )
        derivazione = "inconcludente"
        if esito.firma_valida:
            try:
                attesa = self._elabora(raw)
            except (OSError, TypeError, ValueError, RuntimeError):
                attesa = None
            if isinstance(attesa, bytes) and attesa:
                derivazione = "confermata" if attesa == foto else "incompatibile"
        return RapportoOrigine(esito.firma_valida, esito.struttura_bayer, esito.prnu, derivazione, coppia)

    def messaggio_da_approvare(self, registro, raw, foto, attestazione, riferimenti, *, iscrizione, tx_id_xrpl):
        rapporto = self.valuta(registro, raw, foto, attestazione, riferimenti,
                               iscrizione=iscrizione, tx_id_xrpl=tx_id_xrpl)
        if rapporto.approvabile:
            return self._messaggio(raw, foto, attestazione, iscrizione, tx_id_xrpl)
        return None

    def _messaggio_violazione(self, raw, foto, attestazione, iscrizione, tx_id_xrpl, dichiarazione):
        return (b"TEAM-BARI-VIOLAZIONE-SVILUPPO-1\x00"
                + self._messaggio(raw, foto, attestazione, iscrizione, tx_id_xrpl)
                + hashlib.sha256(dichiarazione.firma).digest())

    def messaggio_violazione(self, registro, raw, foto, attestazione, riferimenti, *,
                             iscrizione, tx_id_xrpl, dichiarazione):
        rapporto = self.valuta(registro, raw, foto, attestazione, riferimenti, iscrizione=iscrizione,
                               tx_id_xrpl=tx_id_xrpl, dichiarazione=dichiarazione)
        if rapporto.attribuibile:
            return self._messaggio_violazione(raw, foto, attestazione, iscrizione, tx_id_xrpl, dichiarazione)
        return None

    def registra_violazione(self, registro, raw, foto, attestazione, voti, *, iscrizione, tx_id_xrpl, dichiarazione):
        """Accetta un quorum di contestazioni dopo aver verificato le due firme del dispositivo."""
        if dichiarazione is None or not isinstance(raw, bytes) or not raw or not foto:
            return False
        chiave = iscrizione.richiesta.certificato.chiave_dispositivo
        if (dichiarazione.politica_sha256 != self._politica or dichiarazione.raw_sha256 != hashlib.sha256(raw).digest()
                or chiave != attestazione.chiave_dispositivo or not registro.verifica_iscrizione(iscrizione)
                or not verifica_cattura(raw, attestazione, {chiave})
                or not self._cross.verify(chiave, dichiarazione.messaggio(foto, attestazione), dichiarazione.firma)):
            return False
        messaggio = self._messaggio_violazione(raw, foto, attestazione, iscrizione, tx_id_xrpl, dichiarazione)
        if (not self._soglia <= len(voti) <= len(self._validatori)
                or not all(isinstance(v, ApprovazioneDispositivo) and self._verifica_voto(v, messaggio, chiave)
                           for v in voti)
                or len({v.chiave_validatore for v in voti}) != len(voti)
                or not self._ancoraggio_valido(iscrizione, tx_id_xrpl)):
            return False
        registro._revoche.registra(iscrizione.richiesta.certificato.dispositivo_id,
                                   dichiarazione.raw_sha256, hashlib.sha256(foto).digest())
        return True

    def verifica(self, registro: RegistroDispositivi, raw: bytes, foto: bytes,
                 attestazione: AttestazioneDispositivo, voti: Collection[ApprovazioneDispositivo], *,
                 iscrizione: ProvaIscrizione, tx_id_xrpl: str) -> bool:
        """Verifica voti distinti per questa cattura, questa foto e questa politica."""
        if not self._soglia <= len(voti) <= len(self._validatori):
            return False
        try:
            accetta = self.filtro_voti(registro, raw, foto, attestazione, iscrizione=iscrizione, tx_id_xrpl=tx_id_xrpl)
        except ValueError:
            return False
        visti = set()
        for voto in voti:
            if not isinstance(voto, ApprovazioneDispositivo):
                return False
            pk = voto.chiave_validatore
            if not accetta(voto) or pk in visti:
                return False
            visti.add(pk)
        return self._ancoraggio_valido(iscrizione, tx_id_xrpl)

    def _verifica_voto(self, voto: ApprovazioneDispositivo, messaggio: bytes, chiave_dispositivo: bytes) -> bool:
        pk = voto.chiave_validatore
        return (isinstance(pk, bytes) and pk in self._validatori and pk != chiave_dispositivo
                and self._cross.verify(pk, messaggio, voto.firma))

    def filtro_voti(self, registro: RegistroDispositivi, raw: bytes, foto: bytes,
                    attestazione: AttestazioneDispositivo, *, iscrizione: ProvaIscrizione, tx_id_xrpl: str):
        """Filtra le firme individuali. Il verdetto completo richiede verifica XRPL."""
        vista = registro.verificatore_per_iscrizione(iscrizione)
        if not isinstance(foto, bytes) or not foto or not vista.verifica_cattura(raw, attestazione):
            raise ValueError("Cattura o foto non valida.")
        messaggio = self._messaggio(raw, foto, attestazione, iscrizione, tx_id_xrpl)
        return lambda voto: self._verifica_voto(voto, messaggio, attestazione.chiave_dispositivo)

    @property
    def soglia(self) -> int:
        return self._soglia

    @property
    def chiavi_validatori(self) -> frozenset[bytes]:
        return self._validatori

    def verificatore_autorizzato(self, chiave: bytes) -> bool:
        return isinstance(chiave, bytes) and chiave in self._validatori
