"""Test di interoperabilità con i vettori ufficiali CROSS."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from crypto_kit import CROSSSigner, PQC_SPECS
from crypto_kit.cross_official import _library


class OfficialCROSSTests(unittest.TestCase):
    def test_official_known_answers_for_small_and_fast(self):
        for variant in ("small", "fast"):
            with self.subTest(variant=variant):
                data = json.loads((Path(__file__).parent / "fixtures" /
                                   f"cross_v22_{variant}_count0.json").read_text())
                signer = CROSSSigner(data["variant"])
                pk, sk, msg, sm = (bytes.fromhex(data[k]) for k in ("pk", "sk", "msg", "sm"))
                self.assertEqual(signer.spec, PQC_SPECS[data["variant"]])
                self.assertTrue(signer.verify(pk, msg, sm[len(msg):]))
                with patch("crypto_kit.cross_official.secrets.token_bytes",
                           return_value=bytes.fromhex(data["key_entropy"])):
                    self.assertEqual(signer.keygen(), (pk, sk))
                with patch("crypto_kit.cross_official.secrets.token_bytes",
                           return_value=bytes.fromhex(data["sign_entropy"])):
                    self.assertEqual(signer.sign(sk, msg), sm[len(msg):])

    def test_invalid_inputs_rejected_before_native_call_and_mutations_rejected(self):
        for variant in ("small", "fast"):
            signer = CROSSSigner(f"CROSS-rsdp-128-{variant}")
            pk, sk = signer.keygen()
            msg = b"\x00binary message\xff"
            sig = signer.sign(sk, msg)
            self.assertTrue(signer.verify(pk, msg, sig))
            for bad_pk, bad_msg, bad_sig in ((pk[:-1], msg, sig), (pk, msg, sig[:-1]),
                                            (None, msg, sig), (pk, None, sig),
                                            (pk, msg, None), (pk, msg + b"x", sig),
                                            (bytes(len(pk)), msg, sig)):
                self.assertFalse(signer.verify(bad_pk, bad_msg, bad_sig))
            for offset in (0, 32, 96, len(sig) // 2, len(sig) - 1):
                changed = sig[:offset] + bytes([sig[offset] ^ 1]) + sig[offset + 1:]
                self.assertFalse(signer.verify(pk, msg, changed))
            for bad_sk in (b"", sk[:-1], None):
                with self.assertRaises(ValueError):
                    signer.sign(bad_sk, msg)
            with self.assertRaises(ValueError):
                signer.sign(sk, "not bytes")

    def test_empty_message_randomized_signatures_and_parallel_calls(self):
        signer = CROSSSigner()
        pk, sk = signer.keygen()
        sig1, sig2 = signer.sign(sk, b""), signer.sign(sk, b"")
        self.assertNotEqual(sig1, sig2)
        self.assertTrue(signer.verify(pk, b"", sig1))
        self.assertTrue(signer.verify(pk, b"", sig2))

        def work(index):
            pk, sk = signer.keygen()
            msg = str(index).encode()
            return signer.verify(pk, msg, signer.sign(sk, msg))

        with ThreadPoolExecutor(max_workers=4) as pool:
            self.assertTrue(all(pool.map(work, range(12))))

    def test_no_silent_fallback_if_native_library_missing(self):
        with patch("crypto_kit.cross_official.ct.CDLL", side_effect=OSError("missing")):
            with self.assertRaisesRegex(RuntimeError, "build_cross.py"):
                _library.__wrapped__("small")


if __name__ == "__main__":
    unittest.main()
