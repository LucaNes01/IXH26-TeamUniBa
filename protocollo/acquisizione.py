"""Autenticazione AES-CMAC tra sensore e modulo di acquisizione."""

import hashlib
from collections.abc import Callable
from uuid import uuid4

from crypto_kit import CROSSSigner

from .provenienza import AttestazioneDispositivo, messaggio_cattura_dispositivo


def _cmac(raw: bytes, scatto_id: str, chiave_pubblica: bytes, chiave_aes: bytes):
    from cryptography.hazmat.primitives.ciphers.algorithms import AES
    from cryptography.hazmat.primitives.cmac import CMAC

    if not isinstance(raw, bytes) or not raw or not isinstance(scatto_id, str) or not scatto_id.strip():
        raise ValueError("Servono i byte del RAW e un identificativo dello scatto.")
    if not isinstance(chiave_pubblica, bytes) or len(chiave_pubblica) != CROSSSigner().spec.pk_bytes:
        raise ValueError("Serve la chiave pubblica CROSS del dispositivo.")
    if not isinstance(chiave_aes, bytes) or len(chiave_aes) != 32:
        raise ValueError("Serve una chiave AES-256 di 32 byte dedicata all'acquisizione.")
    identificativo = scatto_id.encode("utf-8")
    mac = CMAC(AES(chiave_aes))
    mac.update(b"TEAM-BARI-CATTURA-AES-CMAC-2\x00")
    mac.update(chiave_pubblica)
    mac.update(len(identificativo).to_bytes(8, "big") + identificativo)
    mac.update(raw)
    return mac


def tag_cattura_aes(raw: bytes, scatto_id: str, chiave_pubblica: bytes, chiave_aes: bytes) -> bytes:
    """Autentica direttamente i byte appena letti dal sensore."""
    return _cmac(raw, scatto_id, chiave_pubblica, chiave_aes).finalize()


def attesta_cattura_aes(raw: bytes, scatto_id: str, chiave_pubblica: bytes, tag: bytes, *,
                       chiave_aes: bytes, firma_cross: Callable[[bytes], bytes]) -> AttestazioneDispositivo:
    """Verifica il tag nel modulo di acquisizione prima di invocare il firmatario."""
    from cryptography.exceptions import InvalidSignature

    mac = _cmac(raw, scatto_id, chiave_pubblica, chiave_aes)
    if not isinstance(tag, bytes) or len(tag) != 16:
        raise ValueError("Tag AES-CMAC di cattura non valido.")
    try:
        mac.verify(tag)
    except InvalidSignature:
        raise ValueError("Tag AES-CMAC di cattura non valido.") from None
    messaggio = messaggio_cattura_dispositivo(scatto_id, hashlib.sha256(raw).digest(), chiave_pubblica)
    return AttestazioneDispositivo(scatto_id, chiave_pubblica, firma_cross(messaggio))


def acquisisci_cattura_aes(leggi_sensore: Callable[[str], tuple[bytes, bytes]], *,
                           chiave_pubblica: bytes, chiave_aes: bytes,
                           firma_cross: Callable[[bytes], bytes]) -> tuple[bytes, AttestazioneDispositivo]:
    """Chiede una nuova lettura e verifica il tag restituito insieme al fotogramma."""
    scatto_id = uuid4().hex
    raw, tag = leggi_sensore(scatto_id)
    attestazione = attesta_cattura_aes(
        raw, scatto_id, chiave_pubblica, tag, chiave_aes=chiave_aes, firma_cross=firma_cross,
    )
    return raw, attestazione
