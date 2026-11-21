"""Verifica dell'origine del RAW e della derivazione del file finale."""

import hashlib
import json
from collections.abc import Callable, Collection
from dataclasses import dataclass

from crypto_kit import CROSSSigner


@dataclass(frozen=True)
class AttestazioneDispositivo:
    scatto_id: str
    chiave_dispositivo: bytes
    firma: bytes


def messaggio_cattura_dispositivo(scatto_id: str, impronta_raw: bytes, chiave_dispositivo: bytes) -> bytes:
    dati = {"protocollo": "TEAM-BARI-CATTURA-DISPOSITIVO-1", "scatto_id": scatto_id,
            "impronta_raw": impronta_raw.hex(), "chiave_dispositivo": chiave_dispositivo.hex()}
    return json.dumps(dati, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def verifica_cattura(raw: bytes, attestazione: AttestazioneDispositivo,
                     chiavi_autorizzate: Collection[bytes]) -> bool:
    """Ricalcola l'impronta dai byte ricevuti e verifica la firma di cattura."""
    if not isinstance(raw, bytes) or not raw or not isinstance(attestazione, AttestazioneDispositivo):
        return False
    if not isinstance(attestazione.scatto_id, str) or not attestazione.scatto_id.strip():
        return False
    chiave = attestazione.chiave_dispositivo
    if not isinstance(chiave, bytes) or chiave not in chiavi_autorizzate:
        return False
    messaggio = messaggio_cattura_dispositivo(attestazione.scatto_id, hashlib.sha256(raw).digest(), chiave)
    return CROSSSigner().verify(chiave, messaggio, attestazione.firma)


def verifica_elaborazione(raw: bytes, foto_finale: bytes,
                           elabora: Callable[[bytes], bytes]) -> bool:
    """Riproduce la pipeline deterministica scelta dal verificatore."""
    if not isinstance(raw, bytes) or not raw or not isinstance(foto_finale, bytes) or not foto_finale:
        return False
    attesa = elabora(raw)
    return isinstance(attesa, bytes) and attesa == foto_finale


@dataclass(frozen=True)
class DichiarazioneSviluppo:
    raw_sha256: bytes
    politica_sha256: bytes
    firma: bytes

    def messaggio(self, foto: bytes, attestazione: AttestazioneDispositivo) -> bytes:
        if not isinstance(foto, bytes) or not foto or any(
            not isinstance(digest, bytes) or len(digest) != 32 for digest in (self.raw_sha256, self.politica_sha256)
        ):
            raise ValueError("Servono il file finale e due digest SHA-256.")
        cattura = messaggio_cattura_dispositivo(attestazione.scatto_id, self.raw_sha256,
                                                attestazione.chiave_dispositivo)
        return (b"TEAM-BARI-SVILUPPO-1\x00" + hashlib.sha256(cattura).digest()
                + self.politica_sha256 + hashlib.sha256(foto).digest())

    @classmethod
    def firma_coppia(cls, raw: bytes, foto: bytes, attestazione: AttestazioneDispositivo,
                     politica_sha256: bytes, firma: Callable[[bytes], bytes]):
        digest = hashlib.sha256(raw).digest()
        messaggio = cls(digest, politica_sha256, b"").messaggio(foto, attestazione)
        return cls(digest, politica_sha256, firma(messaggio))
