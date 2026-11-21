#!/usr/bin/env python3
"""Rigenera i vettori CROSS con OpenSSL e verifica i digest SHA-512 ufficiali."""
import argparse
import ctypes as ct
import hashlib
import json
from pathlib import Path
import shlex
import os
import subprocess
import sys
import tempfile

from build_cross import ROOT, VENDOR, VARIANTS, verify_sources


def verify(variant, prefix, export):
    verify_sources()
    ref = VENDOR / "Reference_Implementation"
    kat = VENDOR / "KAT_Generation"
    compiler = shlex.split(os.environ.get("CC", "cc"))
    includes = ["-I", str(ref / "include"), "-I", str(kat / "include")]
    linkage = ["-lcrypto"]
    if prefix:
        includes += ["-I", str(prefix / "include")]
        linkage = ["-L", str(prefix / "lib"), f"-Wl,-rpath,{prefix / 'lib'}", *linkage]
    flags = ["-std=c11", "-O2", "-DCATEGORY_1=1", "-DRSDP=1", *VARIANTS[variant]]
    expected = {line.split()[1].removeprefix("./"): line.split()[0]
                for line in (VENDOR / "sha_512_sum_KATs").read_text().splitlines()}
    with tempfile.TemporaryDirectory(prefix="cross-kat-") as directory:
        temp = Path(directory)
        binary = temp / "kat"
        subprocess.run(compiler + flags + includes + [
            *map(str, sorted((ref / "lib").glob("*.c"))),
            str(kat / "lib/rng.c"), str(kat / "lib/PQCgenKAT_sign.c"),
            *linkage, "-o", str(binary)], check=True)
        subprocess.run([str(binary)], cwd=temp, check=True)
        for file in sorted(temp.glob("PQCsignKAT*")):
            digest = hashlib.sha512(file.read_bytes()).hexdigest()
            if digest != expected.get(file.name):
                raise RuntimeError(f"KAT upstream non corrispondente: {file.name}")
            print(f"SHA-512 upstream verificato: {file.name}")
        if export:
            rsp = next(temp.glob("*.rsp"))
            record = rsp.read_text().split("\n\n")[1]
            fields = dict(line.split(" = ", 1) for line in record.splitlines())
            # La fixture deve usare la stessa sequenza di byte del generatore KAT.
            rnglib = temp / ("rng.dylib" if sys.platform == "darwin" else "rng.so")
            shared = "-dynamiclib" if sys.platform == "darwin" else "-shared"
            subprocess.run(compiler + ["-fPIC", shared, *includes, str(kat / "lib/rng.c"),
                                       *linkage, "-o", str(rnglib)], check=True)
            rng = ct.CDLL(str(rnglib))
            rng.randombytes_init.argtypes = [ct.c_char_p, ct.c_void_p, ct.c_int]
            rng.randombytes.argtypes = [ct.c_void_p, ct.c_ulonglong]
            rng.randombytes_init(bytes.fromhex(fields["seed"]), None, 256)
            draws = []
            for size in (32, 16, 32):
                out = ct.create_string_buffer(size)
                if rng.randombytes(out, size) != 0:
                    raise RuntimeError("KAT RNG fallito")
                draws.append(out.raw.hex())
            fixture = {"variant": f"CROSS-rsdp-128-{variant}", "source": rsp.name,
                       "source_sha512": expected[rsp.name], "count": 0,
                       "pk": fields["pk"], "sk": fields["sk"], "msg": fields["msg"],
                       "sm": fields["sm"], "key_entropy": draws[0],
                       "sign_entropy": draws[1] + draws[2]}
            target = ROOT / "tests/fixtures" / f"cross_v22_{variant}_count0.json"
            target.parent.mkdir(exist_ok=True)
            target.write_text(json.dumps(fixture, indent=2) + "\n")
            print(f"Vettore di test esportato: {target}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=[*VARIANTS, "all"], default="all")
    parser.add_argument("--openssl-prefix", type=Path)
    parser.add_argument("--export-fixtures", action="store_true")
    args = parser.parse_args()
    prefix = args.openssl_prefix
    if prefix is None and Path("/opt/homebrew/opt/openssl@3").is_dir():
        prefix = Path("/opt/homebrew/opt/openssl@3")
    for variant in VARIANTS if args.variant == "all" else [args.variant]:
        verify(variant, prefix, args.export_fixtures)
