import hashlib
import io
import socket
import unittest
from contextlib import ExitStack
from dataclasses import replace
from importlib.util import find_spec
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread

from crypto_kit import CROSSSigner
from protocollo import QuorumOrigine, RegistroDispositivi
from protocollo.analisi_ia import CommunityForensics224, QuorumIA
from protocollo.jpeg import decodifica_jpeg
from protocollo.rete_origine import raccogli_voti_ia, server_validatore


class AnalisiIATests(unittest.TestCase):
    def test_rifiuta_un_checkpoint_diverso_prima_di_caricarlo(self):
        with TemporaryDirectory() as cartella:
            percorso = Path(cartella) / "model.safetensors"
            percorso.write_bytes(b"checkpoint non autorizzato")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                CommunityForensics224(percorso)

    @unittest.skipUnless(find_spec("PIL"), "Pillow è una dipendenza opzionale")
    def test_due_nodi_attestano_lo_stesso_jpeg_anche_se_il_terzo_e_offline(self):
        from PIL import Image

        from protocollo.bayer import GeometriaBayer

        def jpeg(luce):
            with io.BytesIO() as file:
                Image.new("L", (32, 32), luce).save(file, format="JPEG")
                return file.getvalue()

        def rilevatore_di_test(dati):
            pixel = decodifica_jpeg(dati, "L").getpixel((0, 0))
            return pixel / 255

        signer = CROSSSigner()
        coppie = tuple(signer.keygen() for _ in range(3))
        chiavi = tuple(pk for pk, _ in coppie)
        registro = RegistroDispositivi((), chiavi, 2)
        quorum_foto = QuorumOrigine(
            chiavi, 2, hashlib.sha256(b"test").digest(),
            geometria_attesa=GeometriaBayer("RGGB", (32, 32), (0, 0)),
            decodifica=lambda raw: None, soglia_prnu=0.5, elabora=lambda raw: raw,
            conto_pubblicatore_xrpl="conto-di-test",
        )
        quorum_ia = QuorumIA(quorum_foto, soglia_ia=0.8)
        with ExitStack() as risorse:
            url = []
            for pk, sk in coppie[:2]:
                server = risorse.enter_context(server_validatore(
                    ("127.0.0.1", 0), registro, quorum_foto, chiave_validatore=pk,
                    firma=lambda messaggio, sk=sk: signer.sign(sk, messaggio), riferimenti=(),
                    quorum_ia=quorum_ia, rilevatore_ia=rilevatore_di_test,
                ))
                thread = Thread(target=server.serve_forever, daemon=True)
                thread.start()
                risorse.callback(server.shutdown)
                url.append(f"http://127.0.0.1:{server.server_port}/voti-ia")
            assente = risorse.enter_context(socket.socket())
            assente.bind(("127.0.0.1", 0))
            url.append(f"http://127.0.0.1:{assente.getsockname()[1]}/voti-ia")

            foto = jpeg(240)
            voti = raccogli_voti_ia(foto, quorum_ia, url)
            self.assertEqual(quorum_ia.verifica(foto, voti), "probabile_ia")
            self.assertIsNone(quorum_ia.verifica(foto + b"!", voti))
            self.assertIsNone(quorum_ia.verifica(foto, (voti[0], voti[0])))
            self.assertIsNone(quorum_ia.verifica(foto, (replace(voti[0], punteggio=9900), voti[1])))
            altro_quorum = QuorumIA(quorum_foto, soglia_ia=0.9)
            self.assertIsNone(altro_quorum.verifica(foto, voti))

            scuro = jpeg(70)
            voti_scuri = raccogli_voti_ia(scuro, quorum_ia, url)
            self.assertEqual(quorum_ia.verifica(scuro, voti_scuri), "inconcludente")
