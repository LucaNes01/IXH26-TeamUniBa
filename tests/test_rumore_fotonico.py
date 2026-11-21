import unittest
from importlib.util import find_spec


@unittest.skipUnless(find_spec("numpy"), "NumPy è una dipendenza opzionale")
class RumoreFotonicoTests(unittest.TestCase):
    def test_confronta_la_curva_di_varianza_con_la_calibrazione(self):
        import numpy as np

        from protocollo.rumore_fotonico import stima_profilo_fotonico, verifica_profilo_fotonico

        rng = np.random.default_rng(29)
        forma = (128, 128)
        livelli = (0.15, 0.30, 0.45, 0.60)

        def coppie(guadagno):
            for livello in livelli:
                scatti = rng.poisson(livello / guadagno, (2, *forma)) * guadagno
                scatti += rng.normal(0, 0.001, scatti.shape)
                yield scatti[0], scatti[1]

        riferimento = stima_profilo_fotonico(coppie(0.0001))
        compatibile = stima_profilo_fotonico(coppie(0.0001))
        incompatibile = stima_profilo_fotonico(coppie(0.0002))
        limiti = dict(tolleranza_guadagno=0.00001, tolleranza_intercetta=0.000006, r2_minimo=0.98)
        self.assertTrue(verifica_profilo_fotonico(compatibile, riferimento, **limiti))
        self.assertFalse(verifica_profilo_fotonico(incompatibile, riferimento, **limiti))

        ripetizioni = ((np.full(forma, livello), np.full(forma, livello)) for livello in livelli)
        senza_rumore = stima_profilo_fotonico(ripetizioni)
        self.assertFalse(verifica_profilo_fotonico(senza_rumore, riferimento, **limiti))
