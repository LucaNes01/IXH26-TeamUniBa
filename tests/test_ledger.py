import io
import json
import unittest
from copy import deepcopy
from dataclasses import replace
from unittest.mock import patch

from protocollo import (
    ApprovazioneDispositivo, CertificatoSensore, ProvaIscrizione, RichiestaRegistrazione,
    impronta_iscrizione, prepara_ancoraggio, verifica_ancoraggio,
)


class AncoraggioXRPLTests(unittest.TestCase):
    conto = "rMmTCjGFRWPz8S2zAUUoNVSQHxtRQD4eCx"
    tx_id = "A1" * 32
    certificato = CertificatoSensore("sensore-1", b"chiave-sensore", b"chiave-autorita", 900, 1100, b"firma")

    def setUp(self):
        self.prova = ProvaIscrizione(
            RichiestaRegistrazione(self.certificato, b"a" * 32, b"risposta"), b"b" * 32,
            (ApprovazioneDispositivo(b"v1", b"firma-1"), ApprovazioneDispositivo(b"v2", b"firma-2")),
        )
        self.tx = prepara_ancoraggio(self.prova, self.conto)
        self.risultato = {"status": "success", "validated": True, "hash": self.tx_id,
                          "tx_json": self.tx, "meta": {"TransactionResult": "tesSUCCESS"}}

    def test_ancoraggio_della_prova_di_iscrizione_verificato_via_rpc(self):
        memo = self.tx["Memos"][0]["Memo"]
        self.assertEqual(bytes.fromhex(memo["MemoType"]), b"team-bari/iscrizione-sensore/2")
        self.assertEqual(json.loads(bytes.fromhex(memo["MemoData"])), {
            "dispositivo_id": self.certificato.dispositivo_id,
            "iscrizione_sha256": impronta_iscrizione(self.prova),
        })
        risposta = io.BytesIO(json.dumps({"result": self.risultato}).encode())
        with patch("protocollo.ledger.urlopen", return_value=risposta) as invia:
            self.assertTrue(verifica_ancoraggio(self.prova, self.tx_id.lower(), self.conto))
        richiesta = invia.call_args.args[0]
        self.assertEqual(json.loads(richiesta.data), {"method": "tx", "params": [
            {"transaction": self.tx_id, "binary": False, "api_version": 2},
        ]})
        invertita = replace(self.prova, approvazioni=self.prova.approvazioni[::-1])
        senza_voto = replace(self.prova, approvazioni=self.prova.approvazioni[:1])
        alterata = replace(self.prova, richiesta=replace(self.prova.richiesta, firma_dispositivo=b"altra"))
        self.assertEqual(impronta_iscrizione(invertita), impronta_iscrizione(self.prova))
        self.assertNotEqual(impronta_iscrizione(senza_voto), impronta_iscrizione(self.prova))
        self.assertNotEqual(impronta_iscrizione(alterata), impronta_iscrizione(self.prova))

    def test_legge_il_memo_delle_iscrizioni_gia_pubblicate(self):
        precedente = deepcopy(self.risultato)
        precedente["tx_json"]["Memos"] = [{"Memo": {
            "MemoType": b"team-bari/iscrizione-sensore/1".hex().upper(),
            "MemoData": impronta_iscrizione(self.prova),
        }}]
        risposta = io.BytesIO(json.dumps({"result": precedente}).encode())
        with patch("protocollo.ledger.urlopen", return_value=risposta):
            self.assertTrue(verifica_ancoraggio(self.prova, self.tx_id, self.conto))

    def test_rifiuta_ancoraggi_non_definitivi_estranei_o_non_corrispondenti(self):
        errato_conto = deepcopy(self.risultato)
        errato_conto["tx_json"]["Account"] = "r3kmLJN5D28dHuH8vZNUZpMC43pEHpaecV"
        errata_impronta = deepcopy(self.risultato)
        errata_impronta["tx_json"]["Memos"][0]["Memo"]["MemoData"] = "00" * 32
        risultati = ({**self.risultato, "validated": False},
                     {**self.risultato, "meta": {"TransactionResult": "tecFAILED_PROCESSING"}},
                     {**self.risultato, "hash": "B2" * 32},
                     errato_conto, errata_impronta, {"error": "txnNotFound"})
        for risultato in risultati:
            risposta = io.BytesIO(json.dumps({"result": risultato}).encode())
            with self.subTest(risultato=risultato), patch("protocollo.ledger.urlopen", return_value=risposta):
                self.assertFalse(verifica_ancoraggio(self.prova, self.tx_id, self.conto))
