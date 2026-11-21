"""Serialized sizes; CROSS sizes are also read from the compiled upstream API."""
from dataclasses import dataclass


@dataclass(frozen=True)
class PQCSpec:
    pk_bytes: int
    sk_bytes: int
    ct_or_sig_bytes: int


PQC_SPECS = {
    "CROSS-rsdp-128-small": PQCSpec(77, 32, 12432),
    "CROSS-rsdp-128-fast": PQCSpec(77, 32, 18432),
}
