"""Interfaccia ctypes per CROSS v2.2 con entropia fornita dal sistema operativo."""
import ctypes as ct
from functools import lru_cache
from pathlib import Path
import secrets
import sys

from .specs import PQCSpec

UPSTREAM_COMMIT = "7e9a4d93ab072b7c59f89589d0eb2d90751330fb"
SIGNATURE_SUITE = f"CROSS-REFERENCE-2.2-RSDP-128-SMALL@{UPSTREAM_COMMIT}"
_BUFFER = ct.POINTER(ct.c_ubyte)


def _input(value: bytes):
    return (ct.c_ubyte * len(value)).from_buffer_copy(value)


@lru_cache(maxsize=2)
def _library(variant):
    extension = "dylib" if sys.platform == "darwin" else "so"
    path = Path(__file__).parent / ".native" / f"libcross_{variant}.{extension}"
    try:
        lib = ct.CDLL(str(path))
    except OSError as exc:
        raise RuntimeError(
            "Backend CROSS ufficiale non disponibile. Esegui dalla radice: "
            "python3 scripts/build_cross.py"
        ) from exc
    for name in ("pk", "sk", "sig", "key_entropy", "sign_entropy"):
        function = getattr(lib, f"tb_cross_{name}_bytes")
        function.argtypes = []
        function.restype = ct.c_size_t
    lib.tb_cross_keypair.argtypes = [_BUFFER, _BUFFER, _BUFFER]
    lib.tb_cross_keypair.restype = ct.c_int
    lib.tb_cross_sign.argtypes = [_BUFFER, ct.POINTER(ct.c_ulonglong), _BUFFER,
                                  ct.c_ulonglong, _BUFFER, _BUFFER]
    lib.tb_cross_sign.restype = ct.c_int
    lib.crypto_sign_open.argtypes = [_BUFFER, ct.POINTER(ct.c_ulonglong), _BUFFER,
                                     ct.c_ulonglong, _BUFFER]
    lib.crypto_sign_open.restype = ct.c_int
    return lib


class CROSSSigner:
    """Official CROSS v2.2: RSDP, category 1, small or fast parameter set."""

    def __init__(self, variant="CROSS-rsdp-128-small"):
        variants = {"CROSS-rsdp-128-small": "small", "CROSS-rsdp-128-fast": "fast"}
        if variant not in variants:
            raise ValueError(f"Variante CROSS non supportata: {variant}")
        self._lib = _library(variants[variant])
        self.spec = PQCSpec(self._lib.tb_cross_pk_bytes(), self._lib.tb_cross_sk_bytes(),
                            self._lib.tb_cross_sig_bytes())

    def keygen(self):
        pk = (ct.c_ubyte * self.spec.pk_bytes)()
        sk = (ct.c_ubyte * self.spec.sk_bytes)()
        randomness = _input(secrets.token_bytes(self._lib.tb_cross_key_entropy_bytes()))
        if self._lib.tb_cross_keypair(pk, sk, randomness) != 0:
            raise RuntimeError("Generazione chiavi CROSS fallita.")
        return bytes(pk), bytes(sk)

    def sign(self, sk: bytes, message: bytes) -> bytes:
        if not isinstance(sk, bytes) or len(sk) != self.spec.sk_bytes:
            raise ValueError("Chiave privata CROSS non valida.")
        if not isinstance(message, bytes):
            raise ValueError("Il messaggio deve essere bytes.")
        sm = (ct.c_ubyte * (len(message) + self.spec.ct_or_sig_bytes))()
        length = ct.c_ulonglong()
        randomness = _input(secrets.token_bytes(self._lib.tb_cross_sign_entropy_bytes()))
        status = self._lib.tb_cross_sign(sm, ct.byref(length), _input(message), len(message),
                                         _input(sk), randomness)
        if status != 0 or length.value != len(sm):
            raise RuntimeError("Firma CROSS fallita.")
        # CROSS restituisce il messaggio seguito dalla firma.
        return bytes(sm[len(message):])

    def verify(self, pk: bytes, message: bytes, sig: bytes) -> bool:
        if (not isinstance(pk, bytes) or len(pk) != self.spec.pk_bytes
                or not isinstance(message, bytes) or not isinstance(sig, bytes)
                or len(sig) != self.spec.ct_or_sig_bytes):
            return False
        sm = message + sig
        output = (ct.c_ubyte * len(sm))()
        length = ct.c_ulonglong()
        status = self._lib.crypto_sign_open(output, ct.byref(length), _input(sm),
                                            len(sm), _input(pk))
        return status == 0 and length.value == len(message) and bytes(output[:length.value]) == message
