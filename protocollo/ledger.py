"""Ancoraggio delle prove di iscrizione su XRP Ledger."""

import hashlib
import json
import re
from urllib.request import Request, urlopen

from .dispositivi import ProvaIscrizione


XRPL_TESTNET_RPC = "https://s.altnet.rippletest.net:51234/"
_TIPO_MEMO_V2 = b"team-bari/iscrizione-sensore/2".hex().upper()
_TIPO_MEMO_V1 = b"team-bari/iscrizione-sensore/1".hex().upper()


def impronta_iscrizione(prova: ProvaIscrizione) -> str:
    dati = {"richiesta": prova.richiesta.impronta.hex(), "comitato": prova.impronta_comitato.hex(),
            "approvazioni": sorted((v.chiave_validatore.hex(), v.firma.hex()) for v in prova.approvazioni)}
    messaggio = json.dumps(dati, sort_keys=True, separators=(",", ":")).encode("ascii")
    return hashlib.sha256(b"TEAM-BARI-ANCORAGGIO-ISCRIZIONE-1\x00" + messaggio).hexdigest().upper()


def prepara_ancoraggio(prova: ProvaIscrizione, conto_pubblicatore: str) -> dict:
    """Prepara i campi della transazione da completare e firmare nel wallet."""
    dati = {"dispositivo_id": prova.richiesta.certificato.dispositivo_id,
            "iscrizione_sha256": impronta_iscrizione(prova)}
    memo = json.dumps(dati, separators=(",", ":")).encode("ascii").hex().upper()
    return {
        "TransactionType": "AccountSet",
        "Account": conto_pubblicatore,
        "Memos": [{"Memo": {"MemoType": _TIPO_MEMO_V2, "MemoData": memo}}],
    }


def normalizza_id_transazione(tx_id: str) -> str:
    if not isinstance(tx_id, str) or re.fullmatch(r"[0-9A-Fa-f]{64}", tx_id) is None:
        raise ValueError("L'identificativo XRPL deve essere un hash esadecimale di 64 caratteri.")
    return tx_id.upper()


def verifica_ancoraggio(prova: ProvaIscrizione, tx_id: str, conto_pubblicatore: str,
                       *, url_rpc: str = XRPL_TESTNET_RPC) -> bool:
    """Cerca la transazione nel ledger configurato dal verificatore."""
    tx_id = normalizza_id_transazione(tx_id)
    richiesta = {"method": "tx", "params": [{"transaction": tx_id, "binary": False, "api_version": 2}]}
    rpc = Request(url_rpc, data=json.dumps(richiesta).encode("utf-8"),
                  headers={"Content-Type": "application/json"})
    with urlopen(rpc, timeout=10) as risposta:
        risultato = json.load(risposta)["result"]

    if risultato.get("error") == "txnNotFound":
        return False
    if risultato.get("status") == "error" or risultato.get("error"):
        raise RuntimeError("Il nodo XRPL ha restituito un errore durante la ricerca della transazione.")

    tx = risultato.get("tx_json", {})
    meta = risultato.get("meta", {})
    if (risultato.get("validated") is not True or risultato.get("hash") != tx_id
            or meta.get("TransactionResult") != "tesSUCCESS"
            or tx.get("TransactionType") != "AccountSet" or tx.get("Account") != conto_pubblicatore):
        return False

    memo_atteso = prepara_ancoraggio(prova, conto_pubblicatore)["Memos"][0]
    memos = tx.get("Memos", [])
    if any(m.get("Memo", {}).get("MemoType") == _TIPO_MEMO_V2 for m in memos):
        return memo_atteso in memos
    return {"Memo": {"MemoType": _TIPO_MEMO_V1, "MemoData": impronta_iscrizione(prova)}} in memos
