"""Verifica locale delle credenziali C2PA incorporate in un JPEG."""

import io
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class CredenzialeJPEG:
    stato: str
    origine: str | None = None
    firmatario: str | None = None


def verifica_credenziale_jpeg(jpeg: bytes, *, radici_pem: str) -> CredenzialeJPEG:
    from c2pa import C2paError, Context, Reader

    if not radici_pem.strip():
        raise ValueError("Servono radici C2PA fidate in formato PEM.")
    opzioni = {
        "trust": {"trust_anchors": radici_pem},
        "verify": {"verify_trust": True, "remote_manifest_fetch": False, "ocsp_fetch": False},
    }
    with Context.from_dict(opzioni) as contesto:
        try:
            with Reader("image/jpeg", io.BytesIO(jpeg), context=contesto) as lettore:
                rapporto = json.loads(lettore.json())
        except C2paError.ManifestNotFound:
            return CredenzialeJPEG("assente")
        except C2paError:
            return CredenzialeJPEG("non_verificata")

    verifica = rapporto.get("validation_results", {}).get("activeManifest", {})
    codici = {voce["code"] for voce in verifica.get("success", [])}
    richiesti = {"assertion.dataHash.match", "claimSignature.validated", "signingCredential.trusted"}
    if rapporto.get("validation_state") != "Trusted" or not richiesti <= codici:
        return CredenzialeJPEG("non_verificata")

    manifesto = rapporto["manifests"][rapporto["active_manifest"]]
    fonte_ia = "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"
    generata = any(
        azione.get("action") == "c2pa.created" and azione.get("digitalSourceType") == fonte_ia
        for asserzione in manifesto.get("assertions", [])
        if asserzione.get("label") in {"c2pa.actions", "c2pa.actions.v2"}
        for azione in asserzione["data"].get("actions", [])
    )
    firmatario = manifesto.get("signature_info", {}).get("common_name")
    return CredenzialeJPEG("verificata", "generata_ia" if generata else None, firmatario)
