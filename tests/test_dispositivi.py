import hashlib
import io
import json
import multiprocessing
import socket
import unittest
from contextlib import contextmanager
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.util import find_spec
from threading import Thread
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from crypto_kit import CROSSSigner
from protocollo import (
    ApprovazioneDispositivo, AttestazioneDispositivo, CertificatoSensore,
    QuorumOrigine, RegistroDispositivi, RichiestaRegistrazione, messaggio_cattura_dispositivo,
    messaggio_certificato_sensore, messaggio_registrazione_dispositivo, prepara_ancoraggio,
)


_CONTO_XRPL = "rMmTCjGFRWPz8S2zAUUoNVSQHxtRQD4eCx"
_TX_VALIDA = "A1" * 32
_TX_ALTRA_VALIDA = "B2" * 32
_TX_NON_VALIDATA = "C3" * 32
_TX_MEMO_ERRATO = "D4" * 32


@contextmanager
def _rpc_xrpl(iscrizione):
    class RPC(BaseHTTPRequestHandler):
        def do_POST(self):
            richiesta = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            tx_id = richiesta["params"][0]["transaction"]
            transazione = prepara_ancoraggio(iscrizione, _CONTO_XRPL)
            if tx_id == _TX_MEMO_ERRATO:
                transazione["Memos"][0]["Memo"]["MemoData"] = "00" * 32
            if tx_id in (_TX_VALIDA, _TX_ALTRA_VALIDA, _TX_NON_VALIDATA, _TX_MEMO_ERRATO):
                risultato = {"validated": tx_id != _TX_NON_VALIDATA, "hash": tx_id, "tx_json": transazione,
                             "meta": {"TransactionResult": "tesSUCCESS"}}
            else:
                risultato = {"error": "txnNotFound"}
            corpo = json.dumps({"result": risultato}).encode()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(corpo)

    with ThreadingHTTPServer(("127.0.0.1", 0), RPC) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}/"
        finally:
            server.shutdown()
            thread.join()


def _nodo_origine(canale, autorita, chiavi_iscrizione, chiavi_quorum, politica, geometria, riferimenti, coppia, rpc):
    import numpy as np

    from protocollo.bayer import MosaicoBayer
    from protocollo.rete_origine import server_validatore

    def decodifica(dati):
        return MosaicoBayer(np.load(io.BytesIO(dati), allow_pickle=False), geometria)

    registro = RegistroDispositivi({autorita}, chiavi_iscrizione, 2, orologio=lambda: 1000)
    quorum = QuorumOrigine(
        chiavi_quorum, 2, politica, geometria_attesa=geometria, decodifica=decodifica,
        soglia_prnu=0.5, elabora=lambda dati: hashlib.sha256(dati).digest(),
        conto_pubblicatore_xrpl=_CONTO_XRPL, url_rpc_xrpl=rpc,
    )
    pk, sk = coppia
    signer = CROSSSigner()
    with server_validatore(("127.0.0.1", 0), registro, quorum, chiave_validatore=pk,
                            firma=lambda messaggio: signer.sign(sk, messaggio), riferimenti=riferimenti) as server:
        canale.send(server.server_port)
        canale.close()
        server.serve_forever()


class RegistroDispositiviTests(unittest.TestCase):
    def setUp(self):
        self.signer = CROSSSigner()
        self.pk_autorita, self.sk_autorita = self.signer.keygen()
        self.validatori = tuple(self.signer.keygen() for _ in range(3))
        self.ora = 1000
        self.registro = self.verificatore(2)

    def verificatore(self, soglia):
        chiavi = tuple(pk for pk, _ in self.validatori)
        return RegistroDispositivi({self.pk_autorita}, chiavi, soglia, orologio=lambda: self.ora)

    def certificato(self, pk, autorita=None, *, tecnologia=None, prnu_sha256=None, prnu_jpeg_sha256=None):
        pk_autorita, sk_autorita = autorita or (self.pk_autorita, self.sk_autorita)
        dati = "sensore-1", pk, pk_autorita, 900, 1100
        opzioni = dict(tecnologia_sensore=tecnologia, prnu_sha256=prnu_sha256, prnu_jpeg_sha256=prnu_jpeg_sha256)
        firma = self.signer.sign(sk_autorita, messaggio_certificato_sensore(*dati, **opzioni))
        return CertificatoSensore(*dati, firma, **opzioni)

    def richiesta(self, certificato, sk):
        sfida = self.registro.emetti_sfida(certificato)
        messaggio = messaggio_registrazione_dispositivo(certificato, sfida)
        return RichiestaRegistrazione(certificato, sfida, self.signer.sign(sk, messaggio))

    def approva(self, richiesta, validatore):
        verificatore = self.verificatore(2)
        self.assertTrue(verificatore.verifica_richiesta(richiesta))
        pk, sk = validatore
        firma = self.signer.sign(sk, verificatore.messaggio_approvazione(richiesta))
        return ApprovazioneDispositivo(pk, firma)

    @unittest.skipUnless(all(find_spec(nome) for nome in ("numpy", "scipy", "PIL")), "Dipendenze JPEG opzionali")
    def test_jpeg_isolato_usa_il_catalogo_certificato_senza_richiedere_il_raw(self):
        import numpy as np
        from PIL import Image

        from protocollo.bayer import GeometriaBayer
        from protocollo.jpeg import RiferimentoJPEG, analizza_jpeg, impronta_prnu_jpeg, stima_prnu_jpeg
        from protocollo.rete_origine import server_validatore

        rng = np.random.default_rng(42)
        forma = (64, 64)
        sensore, estraneo = rng.normal(0, 0.035, (2, *forma))

        def scatto(pattern, luce):
            pixel = np.rint(255 * (luce * (1 + pattern) + rng.normal(0, 0.002, forma))).astype("uint8")
            with io.BytesIO() as file:
                Image.fromarray(pixel).save(file, format="JPEG", quality=100)
                return file.getvalue()

        riferimento = stima_prnu_jpeg(scatto(sensore, luce) for luce in (0.4, 0.5, 0.6))
        pk, sk = self.signer.keygen()
        digest = impronta_prnu_jpeg(riferimento)
        certificato = self.certificato(pk, prnu_jpeg_sha256=digest)
        self.assertFalse(self.registro.verifica_certificato(replace(certificato, prnu_jpeg_sha256="0" * 64)))
        richiesta = self.richiesta(certificato, sk)
        prova = self.registro.registra(richiesta, tuple(self.approva(richiesta, v) for v in self.validatori[:2]))
        foto = scatto(sensore, 0.55)
        altra = scatto(estraneo, 0.55)
        candidato = RiferimentoJPEG(prova, _TX_VALIDA, riferimento, 0.5)
        registro_pubblico = self.verificatore(2)

        with _rpc_xrpl(prova) as rpc:
            opzioni = dict(conto_pubblicatore_xrpl=_CONTO_XRPL, url_rpc_xrpl=rpc)
            errato = replace(candidato, impronta=np.flipud(riferimento))
            self.assertEqual(analizza_jpeg(foto, registro_pubblico, (errato,), **opzioni).esito, "non_valutabile")
            errato = replace(candidato, tx_id_xrpl=_TX_MEMO_ERRATO)
            self.assertEqual(analizza_jpeg(foto, registro_pubblico, (errato,), **opzioni).esito, "non_valutabile")
            pk_nodo, sk_nodo = self.signer.keygen()
            quorum = QuorumOrigine(
                (pk_nodo,), 1, hashlib.sha256(b"test").digest(),
                geometria_attesa=GeometriaBayer("RGGB", forma, (0, 0)), decodifica=lambda raw: None,
                soglia_prnu=0.5, elabora=lambda raw: raw, **opzioni,
            )
            with server_validatore(
                ("127.0.0.1", 0), registro_pubblico, quorum, chiave_validatore=pk_nodo,
                firma=lambda msg: self.signer.sign(sk_nodo, msg), riferimenti=(),
                analisi_jpeg=lambda jpeg: analizza_jpeg(jpeg, registro_pubblico, (candidato,), **opzioni),
            ) as nodo:
                thread = Thread(target=nodo.serve_forever, daemon=True)
                thread.start()
                try:
                    url = f"http://127.0.0.1:{nodo.server_port}/analisi-jpeg"
                    for jpeg, esito in ((foto, "compatibile"), (altra, "nessuna_corrispondenza")):
                        with urlopen(Request(url, data=jpeg, method="POST"), timeout=5) as risposta:
                            dati = json.load(risposta)
                        self.assertEqual(dati["esito"], esito)
                        self.assertEqual(dati["confronti"][0]["chiave_dispositivo"], pk.hex())
                    with self.assertRaises(HTTPError) as errore:
                        urlopen(Request(url, data=b"non e' un JPEG", method="POST"), timeout=5)
                    self.assertEqual(errore.exception.code, 400)
                    errore.exception.close()
                finally:
                    nodo.shutdown()
                    thread.join()

    def test_la_registrazione_abilita_la_verifica_e_consuma_la_sfida(self):
        pk, sk = self.signer.keygen()
        certificato = self.certificato(pk)
        raw = b"cattura"
        messaggio = messaggio_cattura_dispositivo("scatto-1", hashlib.sha256(raw).digest(), pk)
        attestazione = AttestazioneDispositivo("scatto-1", pk, self.signer.sign(sk, messaggio))
        self.assertFalse(self.registro.verifica_cattura(raw, attestazione))

        richiesta = self.richiesta(certificato, sk)
        self.assertIsNone(self.registro.certificato_pubblico(pk))
        self.assertEqual(self.registro.emetti_sfida(certificato), richiesta.sfida)
        con_firma_di_cattura = replace(richiesta, firma_dispositivo=attestazione.firma)
        with self.assertRaisesRegex(ValueError, "Firma di registrazione"):
            self.registro.registra(con_firma_di_cattura, ())

        primo, secondo = [self.approva(richiesta, voto) for voto in self.validatori[:2]]
        estraneo = self.approva(richiesta, self.signer.keygen())
        for voti in ((primo,), (primo, primo), (primo, estraneo)):
            with self.subTest(voti=len(voti)), self.assertRaisesRegex(ValueError, "Quorum"):
                self.registro.registra(richiesta, voti)
            self.assertIsNone(self.registro.prova_pubblica(pk))

        prova = self.registro.registra(richiesta, (primo, secondo))
        self.assertTrue(self.verificatore(2).verifica_iscrizione(prova))
        self.assertFalse(self.verificatore(1).verifica_iscrizione(prova))
        self.assertEqual(self.registro.prova_pubblica(pk), prova)
        self.assertEqual(self.registro.certificato_pubblico(pk), certificato)
        self.assertTrue(self.registro.verifica_cattura(raw, attestazione))
        with self.assertRaisesRegex(ValueError, "già utilizzata"):
            self.registro.registra(richiesta, (primo, secondo))

        self.ora = 1100
        self.assertFalse(self.registro.verifica_cattura(raw, attestazione))

    def test_chiave_sconosciuta_e_firma_di_un_altro_dispositivo_sono_respinte(self):
        pk, _ = self.signer.keygen()
        pk_estranea, sk_estranea = self.signer.keygen()
        certificato = self.certificato(pk)
        estraneo = self.certificato(pk, (pk_estranea, sk_estranea))
        for non_valido in (estraneo, replace(certificato, sensore_id="altro"),
                           replace(certificato, chiave_dispositivo=pk_estranea),
                           replace(certificato, valido_fino=1200)):
            self.assertFalse(self.registro.verifica_certificato(non_valido))
            with self.assertRaisesRegex(ValueError, "Certificato del sensore non valido"):
                self.registro.emetti_sfida(non_valido)
        richiesta = self.richiesta(certificato, sk_estranea)
        self.assertFalse(self.registro.verifica_richiesta(richiesta))
        with self.assertRaisesRegex(ValueError, "Firma di registrazione"):
            self.registro.registra(richiesta, ())

    def test_le_approvazioni_non_si_trasferiscono_a_un_altra_risposta(self):
        pk, sk = self.signer.keygen()
        certificato = self.certificato(pk)
        richiesta = self.richiesta(certificato, sk)
        altra_risposta = self.richiesta(certificato, sk)
        voti = tuple(self.approva(richiesta, v) for v in self.validatori[:2])
        self.assertTrue(self.registro.verifica_richiesta(altra_risposta))
        with self.assertRaisesRegex(ValueError, "Quorum"):
            self.registro.registra(altra_risposta, voti)

    def test_validita_del_certificato_al_rilascio_e_al_consumo_della_sfida(self):
        pk, sk = self.signer.keygen()
        certificato = self.certificato(pk)
        self.ora = 899
        self.assertFalse(self.registro.verifica_certificato(certificato))
        self.ora = 900
        richiesta = self.richiesta(certificato, sk)
        voti = tuple(self.approva(richiesta, v) for v in self.validatori[:2])
        self.ora = 1100
        with self.assertRaisesRegex(ValueError, "scaduto"):
            self.registro.registra(richiesta, voti)

    def test_la_tecnologia_del_sensore_e_facoltativa_e_firmata(self):
        for tecnologia in (None, "CCD", "CMOS"):
            with self.subTest(tecnologia=tecnologia):
                pk, sk = self.signer.keygen()
                certificato = self.certificato(pk, tecnologia=tecnologia)
                alterato = replace(certificato, tecnologia_sensore="altro")
                self.assertFalse(self.registro.verifica_certificato(alterato))

                richiesta = self.richiesta(certificato, sk)
                voti = tuple(self.approva(richiesta, v) for v in self.validatori[:2])
                prova = self.registro.registra(richiesta, voti)
                self.assertTrue(self.verificatore(2).verifica_iscrizione(prova))

    @unittest.skipUnless(find_spec("numpy") and find_spec("scipy"), "Dipendenze PRNU opzionali")
    def test_prnu_collega_il_raw_firmato_al_riferimento_certificato(self):
        import numpy as np

        from protocollo.prnu import impronta_prnu, stima_prnu

        rng = np.random.default_rng(27)
        forma = (64, 64)
        sensore, altro_sensore = rng.normal(0, 0.012, (2, *forma))

        def cattura(pattern, livello):
            return livello * (1 + pattern) + rng.normal(0, 0.002, forma)

        def firma_cattura(pattern):
            file = io.BytesIO()
            np.save(file, cattura(pattern, 0.55), allow_pickle=False)
            raw = file.getvalue()
            messaggio = messaggio_cattura_dispositivo("scatto-prnu", hashlib.sha256(raw).digest(), pk)
            return raw, AttestazioneDispositivo("scatto-prnu", pk, self.signer.sign(sk, messaggio))

        def decodifica(raw):
            return np.load(io.BytesIO(raw), allow_pickle=False)

        livelli = (0.35, 0.50, 0.65)
        riferimento = stima_prnu(cattura(sensore, livello) for livello in livelli)
        altro_riferimento = stima_prnu(cattura(altro_sensore, livello) for livello in livelli)
        pk, sk = self.signer.keygen()
        certificato = self.certificato(pk, prnu_sha256=impronta_prnu(riferimento))
        alterato = replace(certificato, prnu_sha256=impronta_prnu(altro_riferimento))
        self.assertFalse(self.registro.verifica_certificato(alterato))
        richiesta = self.richiesta(certificato, sk)
        voti = tuple(self.approva(richiesta, v) for v in self.validatori[:2])
        self.registro.registra(richiesta, voti)

        opzioni = dict(decodifica=decodifica, soglia=0.5)
        raw, attestazione = firma_cattura(sensore)
        altro_raw, altra_attestazione = firma_cattura(altro_sensore)
        self.assertTrue(self.registro.verifica_cattura_prnu(raw, attestazione, riferimento, **opzioni))
        self.assertFalse(self.registro.verifica_cattura_prnu(raw + b"!", attestazione, riferimento, **opzioni))
        self.assertFalse(self.registro.verifica_cattura_prnu(raw, attestazione, altro_riferimento, **opzioni))
        self.assertTrue(self.registro.verifica_cattura(altro_raw, altra_attestazione))
        self.assertFalse(self.registro.verifica_cattura_prnu(altro_raw, altra_attestazione, riferimento, **opzioni))

    @unittest.skipUnless(find_spec("numpy") and find_spec("scipy"), "Dipendenze PRNU opzionali")
    def test_prnu_bayer_verifica_le_quattro_posizioni_del_mosaico(self):
        import numpy as np

        from protocollo.bayer import GeometriaBayer, MosaicoBayer
        from protocollo.dispositivi import EsitoCatturaBayer
        from protocollo.prnu import impronta_prnu_bayer, punteggi_prnu_bayer, stima_prnu_bayer

        rng = np.random.default_rng(28)
        forma = (65, 63)
        sensore, altro_sensore = rng.normal(0, 0.012, (2, *forma))
        luce = np.tile([[0.65, 0.5], [0.5, 0.35]], (33, 32))[:65, :63]

        def cattura(pattern, esposizione):
            return esposizione * luce * (1 + pattern) + rng.normal(0, 0.001, forma)

        riferimenti = stima_prnu_bayer(cattura(sensore, livello) for livello in (0.8, 1.0, 1.2))
        self.assertEqual(tuple(piano.shape for piano in riferimenti), ((33, 32), (33, 31), (32, 32), (32, 31)))
        pk, sk = self.signer.keygen()
        digest = impronta_prnu_bayer(riferimenti, "RGGB")
        richiesta = self.richiesta(self.certificato(pk, prnu_sha256=digest), sk)
        voti = tuple(self.approva(richiesta, v) for v in self.validatori[:2])
        self.registro.registra(richiesta, voti)

        def firma_cattura(pixel):
            file = io.BytesIO()
            np.save(file, pixel, allow_pickle=False)
            raw = file.getvalue()
            messaggio = messaggio_cattura_dispositivo("scatto-bayer", hashlib.sha256(raw).digest(), pk)
            return raw, AttestazioneDispositivo("scatto-bayer", pk, self.signer.sign(sk, messaggio))

        def decodifica(raw):
            return np.load(io.BytesIO(raw), allow_pickle=False)

        mosaico = cattura(sensore, 1.0)
        raw, attestazione = firma_cattura(mosaico)
        opzioni = dict(decodifica=decodifica, soglia=0.5, schema_bayer="RGGB")
        verifica = self.registro.verifica_cattura_prnu
        self.assertTrue(verifica(raw, attestazione, riferimenti, **opzioni))
        self.assertFalse(verifica(raw + b"!", attestazione, riferimenti, **opzioni))
        self.assertFalse(verifica(raw, attestazione, riferimenti[::-1], **opzioni))
        self.assertFalse(verifica(raw, attestazione, riferimenti, **(opzioni | {"schema_bayer": "BGGR"})))

        mosaico[1::2, ::2] = cattura(altro_sensore, 1.0)[1::2, ::2]
        punteggi = punteggi_prnu_bayer(mosaico, riferimenti)
        self.assertEqual(tuple(punteggio >= 0.5 for punteggio in punteggi), (True, True, False, True))
        raw_misto, attestazione_mista = firma_cattura(mosaico)
        self.assertTrue(self.registro.verifica_cattura(raw_misto, attestazione_mista))
        self.assertFalse(verifica(raw_misto, attestazione_mista, riferimenti, **opzioni))

        geometria = GeometriaBayer("RGGB", forma, (0, 0))

        def decodifica_mosaico(dati):
            return MosaicoBayer(decodifica(dati), geometria)

        opzioni = dict(decodifica=decodifica_mosaico, geometria_attesa=geometria)
        dettagliata = self.registro.verifica_cattura_bayer
        self.assertEqual(dettagliata(raw, attestazione, riferimenti, soglia=0.5, **opzioni),
                         EsitoCatturaBayer(True, True, True))
        self.assertEqual(dettagliata(raw_misto, attestazione_mista, riferimenti, soglia=0.5, **opzioni),
                         EsitoCatturaBayer(True, True, False))
        self.assertEqual(dettagliata(raw + b"!", attestazione, riferimenti, soglia=0.5, **opzioni),
                         EsitoCatturaBayer(False, None, None))
        for diversa in (replace(geometria, origine=(0, 1)), replace(geometria, schema="BGGR"),
                        replace(geometria, dimensioni=(65, 64))):
            with self.subTest(geometria=diversa):
                esito = dettagliata(raw, attestazione, riferimenti, soglia=0.5,
                                    **(opzioni | {"geometria_attesa": diversa}))
                self.assertEqual(esito, EsitoCatturaBayer(True, False, None))

        iscrizione = self.registro.prova_pubblica(attestazione.chiave_dispositivo)
        with _rpc_xrpl(iscrizione) as rpc:
            self._controlla_quorum_origine(raw, attestazione, riferimenti, opzioni, iscrizione, rpc)

    def _controlla_quorum_origine(self, raw, attestazione, riferimenti, opzioni, iscrizione, rpc):
        validatori = tuple(self.signer.keygen() for _ in range(3))
        chiavi = tuple(pk for pk, _ in validatori)
        politica = hashlib.sha256(b"pipeline di test: SHA-256").digest()

        def elabora(dati):
            return hashlib.sha256(dati).digest()

        configurazione = dict(conto_pubblicatore_xrpl=_CONTO_XRPL, url_rpc_xrpl=rpc, elabora=elabora, **opzioni)
        quorum = QuorumOrigine(chiavi, 2, politica, soglia_prnu=0.5, **configurazione)
        ancoraggio = dict(iscrizione=iscrizione, tx_id_xrpl=_TX_VALIDA)
        foto = elabora(raw)
        messaggio = quorum.messaggio_da_approvare(self.registro, raw, foto, attestazione, riferimenti, **ancoraggio)
        self.assertIsNotNone(messaggio)
        self.assertIsNone(quorum.messaggio_da_approvare(self.registro, raw, b"altra", attestazione,
                                                       riferimenti, **ancoraggio))
        self.assertIsNone(quorum.messaggio_da_approvare(self.registro, raw, foto, attestazione,
                                                       riferimenti[::-1], **ancoraggio))
        voti = tuple(ApprovazioneDispositivo(pk, self.signer.sign(sk, messaggio)) for pk, sk in validatori[:2])
        self.assertTrue(quorum.verifica(self.registro, raw, foto, attestazione, voti, **ancoraggio))
        with patch("protocollo.ledger.urlopen", side_effect=TimeoutError):
            self.assertFalse(quorum.verifica(self.registro, raw, foto, attestazione, voti, **ancoraggio))
            self.assertIsNone(quorum.messaggio_da_approvare(self.registro, raw, foto, attestazione,
                                                           riferimenti, **ancoraggio))
        self.assertFalse(quorum.verifica(self.registro, raw, foto, attestazione, voti[:1], **ancoraggio))
        self.assertFalse(quorum.verifica(self.registro, raw, foto, attestazione, (voti[0], voti[0]), **ancoraggio))
        self.assertFalse(quorum.verifica(self.registro, raw, b"altra", attestazione, voti, **ancoraggio))
        self.assertFalse(quorum.verifica(self.registro, raw + b"!", foto, attestazione, voti, **ancoraggio))
        altra_politica = QuorumOrigine(chiavi, 2, politica, soglia_prnu=0.6, **configurazione)
        self.assertFalse(altra_politica.verifica(self.registro, raw, foto, attestazione, voti, **ancoraggio))
        self.assertFalse(quorum.verifica(self.registro, raw, foto, attestazione, iscrizione.approvazioni, **ancoraggio))

        self._controlla_validatori_in_rete(raw, foto, attestazione, riferimenti, validatori,
                                         politica, opzioni["geometria_attesa"], quorum, iscrizione, rpc)

    def _controlla_validatori_in_rete(self, raw, foto, attestazione, riferimenti, validatori,
                                     politica, geometria, quorum, iscrizione, rpc):
        from protocollo.rete_origine import PacchettoOrigine, raccogli_approvazioni, verifica_prova_distribuita

        pacchetto = PacchettoOrigine(raw, foto, attestazione, iscrizione, _TX_VALIDA)
        self.assertEqual(PacchettoOrigine.da_json(pacchetto.serializza()), pacchetto)
        verifica = self.verificatore(2)
        self.assertIsNone(verifica.prova_pubblica(attestazione.chiave_dispositivo))
        chiavi_iscrizione = tuple(pk for pk, _ in self.validatori)
        chiavi_quorum = tuple(pk for pk, _ in validatori)
        processi = []
        contesto = multiprocessing.get_context("spawn")
        try:
            url = []
            for coppia in validatori[:2]:
                lettura, scrittura = contesto.Pipe(duplex=False)
                processo = contesto.Process(target=_nodo_origine, args=(
                    scrittura, self.pk_autorita, chiavi_iscrizione, chiavi_quorum, politica,
                    geometria, riferimenti, coppia, rpc,
                ))
                with lettura, scrittura:
                    processo.start()
                    processi.append(processo)
                    scrittura.close()
                    self.assertTrue(lettura.poll(10), "Il validatore non si è avviato")
                    url.append(f"http://127.0.0.1:{lettura.recv()}/approvazioni")

            with socket.socket() as assente:
                assente.bind(("127.0.0.1", 0))
                url.append(f"http://127.0.0.1:{assente.getsockname()[1]}/approvazioni")
                approvazioni = raccogli_approvazioni(pacchetto, verifica, quorum, url)
            self.assertEqual({voto.chiave_validatore for voto in approvazioni}, set(chiavi_quorum[:2]))
            self.assertTrue(verifica_prova_distribuita(pacchetto, verifica, quorum, approvazioni))
            self.assertFalse(verifica_prova_distribuita(pacchetto, verifica, quorum, approvazioni[:1]))
            alterato = replace(pacchetto, foto=foto + b"!")
            self.assertFalse(verifica_prova_distribuita(alterato, verifica, quorum, approvazioni))
            self.assertEqual(raccogli_approvazioni(alterato, verifica, quorum, url[:2]), ())
            altro_ancoraggio = replace(pacchetto, tx_id_xrpl=_TX_ALTRA_VALIDA)
            self.assertFalse(verifica_prova_distribuita(altro_ancoraggio, verifica, quorum, approvazioni))
            for tx_id in (_TX_NON_VALIDATA, _TX_MEMO_ERRATO, "EE" * 32):
                with self.subTest(tx_id=tx_id):
                    respinto = replace(pacchetto, tx_id_xrpl=tx_id)
                    self.assertEqual(raccogli_approvazioni(respinto, verifica, quorum, url[:2]), ())
        finally:
            for processo in processi:
                processo.terminate()
                processo.join(5)
                if processo.is_alive():
                    processo.kill()
                    processo.join()
                processo.close()
