"""Interfaccia Python alle firme CROSS."""

from .cross_official import CROSSSigner
from .specs import PQC_SPECS

__all__ = ["CROSSSigner", "PQC_SPECS"]
