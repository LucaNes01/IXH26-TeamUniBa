"""Rilevamento forense locale e voti firmati su un JPEG isolato."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Collection
from dataclasses import dataclass
from pathlib import Path

from crypto_kit import CROSSSigner

from .jpeg import decodifica_jpeg
from .origine import QuorumOrigine


COMMFOR_224_SHA256 = "a6cc439d5a6d2dfadd60c77d27a2838ad55b34e601ecd30f46ad97266d6ac4e0"
COMMFOR_224_VERSIONE = "OwensLab/commfor-model-224:26afc31e6b40c312c3fd42c05a758be62446215b:rgb256-crop224"
_SCALA = 10_000


class CommunityForensics224:
    """ViT-S/16 degli autori. Il checkpoint completo è caricato da file locale."""

    def __init__(self, percorso_pesi: str | Path):
        pesi = Path(percorso_pesi).read_bytes()
        if hashlib.sha256(pesi).hexdigest() != COMMFOR_224_SHA256:
            raise ValueError("Fingerprint SHA-256 dei pesi Community Forensics errata.")

        import timm
        import torch
        from safetensors.torch import load
        from torchvision import transforms

        self._torch = torch
        modello = timm.create_model("vit_small_patch16_224.augreg_in21k_ft_in1k", pretrained=False, num_classes=1)
        stato = {nome.removeprefix("vit."): valore for nome, valore in load(pesi).items()}
        modello.load_state_dict(stato, strict=True)
        self._modello = modello.eval()
        self._prepara = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
        ])

    def __call__(self, jpeg: bytes) -> float:
        immagine = self._prepara(decodifica_jpeg(jpeg, "RGB")).unsqueeze(0)
        with self._torch.inference_mode():
            return self._modello(immagine).sigmoid().item()


@dataclass(frozen=True)
class VotoIA:
    chiave_validatore: bytes
    esito: str
    punteggio: int
    firma: bytes


class QuorumIA:
    """Usa gli stessi validatori della foto per un verdetto statistico distinto."""

    def __init__(self, quorum: QuorumOrigine, *, soglia_ia: float):
        if isinstance(soglia_ia, bool) or not 0 < soglia_ia < 1:
            raise ValueError("Serve una soglia tra 0 e 1.")
        self._soglia_ia = round(soglia_ia * _SCALA)
        if not 0 < self._soglia_ia < _SCALA:
            raise ValueError("Soglia fuori dalla risoluzione del punteggio.")
        self._quorum = quorum
        self._cross = CROSSSigner()
        politica = {
            "checkpoint_sha256": COMMFOR_224_SHA256, "versione": COMMFOR_224_VERSIONE,
            "soglia_ia": self._soglia_ia, "soglia_voti": quorum.soglia,
            "validatori": sorted(pk.hex() for pk in quorum.chiavi_validatori),
        }
        self._impronta = hashlib.sha256(json.dumps(politica, sort_keys=True).encode("ascii")).digest()

    def _esito(self, punteggio: int) -> str:
        return "probabile_ia" if punteggio >= self._soglia_ia else "inconcludente"

    def _messaggio(self, jpeg_sha256: bytes, pk: bytes, esito: str, punteggio: int) -> bytes:
        return (b"TEAM-BARI-ANALISI-IA-1\x00" + self._impronta + jpeg_sha256 + pk
                + punteggio.to_bytes(2, "big") + esito.encode("ascii"))

    def vota(self, jpeg: bytes, chiave: bytes, rilevatore: CommunityForensics224,
              firma: Callable[[bytes], bytes]) -> VotoIA:
        if not self._quorum.verificatore_autorizzato(chiave):
            raise ValueError("Validatore non autorizzato per l'analisi IA.")
        punteggio = rilevatore(jpeg)
        if not math.isfinite(punteggio) or not 0 <= punteggio <= 1:
            raise ValueError("Punteggio del rilevatore non valido.")
        valore = round(punteggio * _SCALA)
        esito = self._esito(valore)
        messaggio = self._messaggio(hashlib.sha256(jpeg).digest(), chiave, esito, valore)
        return VotoIA(chiave, esito, valore, firma(messaggio))

    def verifica_voto(self, jpeg_sha256: bytes, voto: VotoIA) -> bool:
        if (not isinstance(jpeg_sha256, bytes) or len(jpeg_sha256) != 32 or not isinstance(voto, VotoIA)
                or not self._quorum.verificatore_autorizzato(voto.chiave_validatore)
                or type(voto.punteggio) is not int or not 0 <= voto.punteggio <= _SCALA
                or voto.esito != self._esito(voto.punteggio)):
            return False
        messaggio = self._messaggio(jpeg_sha256, voto.chiave_validatore, voto.esito, voto.punteggio)
        return self._cross.verify(voto.chiave_validatore, messaggio, voto.firma)

    def verifica(self, jpeg: bytes, voti: Collection[VotoIA]) -> str | None:
        """Restituisce l'esito con quorum omogeneo, o None con prove insufficienti."""
        if not isinstance(jpeg, bytes) or not jpeg or len(voti) < self._quorum.soglia:
            return None
        impronta = hashlib.sha256(jpeg).digest()
        chiavi = set()
        esiti = set()
        for voto in voti:
            if not self.verifica_voto(impronta, voto) or voto.chiave_validatore in chiavi:
                return None
            chiavi.add(voto.chiave_validatore)
            esiti.add(voto.esito)
        return next(iter(esiti)) if len(esiti) == 1 else None

    @property
    def soglia(self) -> int:
        return self._quorum.soglia
