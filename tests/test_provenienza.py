import hashlib
import unittest
from dataclasses import replace
from importlib.util import find_spec
from unittest.mock import Mock

from crypto_kit import CROSSSigner
from protocollo import (
    AttestazioneDispositivo, messaggio_cattura_dispositivo, verifica_cattura, verifica_elaborazione,
)


class ProvenienzaTests(unittest.TestCase):
    @unittest.skipUnless(find_spec("cryptography"), "Dipendenza AES-CMAC opzionale")
    def test_aes_cmac_autentica_il_raw_prima_della_firma_cross(self):
        from protocollo.acquisizione import attesta_cattura_aes, tag_cattura_aes

        signer = CROSSSigner()
        pk, sk = signer.keygen()
        chiave_sensore = bytes(range(32))
        raw = b"cattura"
        tag = tag_cattura_aes(raw, "scatto-1", pk, chiave_sensore)
        firma = Mock(side_effect=lambda messaggio: signer.sign(sk, messaggio))

        for dati, scatto, chiave, etichetta in (
            (raw + b"x", "scatto-1", chiave_sensore, tag),
            (raw, "scatto-2", chiave_sensore, tag),
            (raw, "scatto-1", bytes(reversed(chiave_sensore)), tag),
            (raw, "scatto-1", chiave_sensore, tag[:-1]),
        ):
            with self.assertRaisesRegex(ValueError, "Tag AES-CMAC"):
                attesta_cattura_aes(dati, scatto, pk, etichetta, chiave_aes=chiave, firma_cross=firma)
        firma.assert_not_called()

        attestazione = attesta_cattura_aes(
            raw, "scatto-1", pk, tag, chiave_aes=chiave_sensore, firma_cross=firma,
        )
        firma.assert_called_once()
        self.assertTrue(verifica_cattura(raw, attestazione, {pk}))

    @unittest.skipUnless(find_spec("cryptography"), "Dipendenza AES-CMAC opzionale")
    def test_acquisizione_chiede_un_nuovo_fotogramma_autenticato(self):
        from protocollo.acquisizione import acquisisci_cattura_aes, tag_cattura_aes

        signer = CROSSSigner()
        pk, sk = signer.keygen()
        chiave_aes = bytes(range(32))
        pixel = bytes(range(64))
        pacchetti = []

        def sensore(scatto_id):
            pacchetto = pixel, tag_cattura_aes(pixel, scatto_id, pk, chiave_aes)
            pacchetti.append(pacchetto)
            return pacchetto

        firma = Mock(side_effect=lambda messaggio: signer.sign(sk, messaggio))
        opzioni = dict(chiave_pubblica=pk, chiave_aes=chiave_aes, firma_cross=firma)
        raw, attestazione = acquisisci_cattura_aes(sensore, **opzioni)
        self.assertEqual(raw, pixel)
        self.assertTrue(verifica_cattura(raw, attestazione, {pk}))

        with self.assertRaisesRegex(ValueError, "Tag AES-CMAC"):
            acquisisci_cattura_aes(lambda _: pacchetti[0], **opzioni)
        firma.assert_called_once()

    def test_cattura_vincolata_al_raw_allo_scatto_e_alla_chiave_autorizzata(self):
        signer = CROSSSigner()
        pk, sk = signer.keygen()
        raw = b"cattura"
        msg = messaggio_cattura_dispositivo("scatto-1", hashlib.sha256(raw).digest(), pk)
        attestazione = AttestazioneDispositivo("scatto-1", pk, signer.sign(sk, msg))

        self.assertTrue(verifica_cattura(raw, attestazione, {pk}))
        self.assertFalse(verifica_cattura(raw + b"x", attestazione, {pk}))
        self.assertFalse(verifica_cattura(raw, replace(attestazione, scatto_id="scatto-2"), {pk}))
        self.assertFalse(verifica_cattura(raw, attestazione, set()))
        self.assertFalse(verifica_cattura(raw, replace(attestazione, firma=b"falsa"), {pk}))

    def test_elaborazione_verifica_i_byte_prodotti_dalla_pipeline(self):
        def pipeline(raw):
            return b"risultato:" + raw

        raw = b"cattura"
        finale = pipeline(raw)
        self.assertTrue(verifica_elaborazione(raw, finale, pipeline))
        self.assertFalse(verifica_elaborazione(raw, finale + b"x", pipeline))
        self.assertFalse(verifica_elaborazione(raw + b"x", finale, pipeline))
