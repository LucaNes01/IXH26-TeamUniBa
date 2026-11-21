#!/usr/bin/env python3
"""Build unmodified upstream CROSS reference code and the Python ABI bridge."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "third_party/cross"
OUTPUT = ROOT / "crypto_kit/.native"
VARIANTS = {"small": ["-DSIG_SIZE=1"], "fast": ["-DSPEED=1", "-DNO_TREES=1"]}


def verify_sources():
    manifest = json.loads((VENDOR / "UPSTREAM.json").read_text())
    for name, expected in manifest["files"].items():
        if hashlib.sha256((VENDOR / name).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"Sorgente upstream modificato: {name}")


def build(variant):
    if sys.platform not in ("darwin", "linux"):
        raise RuntimeError("Build supportata su macOS e Linux.")
    verify_sources()
    OUTPUT.mkdir(exist_ok=True)
    ref = VENDOR / "Reference_Implementation"
    extension = "dylib" if sys.platform == "darwin" else "so"
    output = OUTPUT / f"libcross_{variant}.{extension}"
    flags = ["-dynamiclib"] if sys.platform == "darwin" else ["-shared"]
    command = shlex.split(os.environ.get("CC", "cc")) + [
        "-std=c11", "-O2", "-fPIC", *flags, "-DCATEGORY_1=1", "-DRSDP=1",
        # Con input malformati CROSS deve restituire un errore senza interrompere il processo.
        "-DSKIP_ASSERT=1",
        *VARIANTS[variant], "-I", str(ref / "include"),
        *map(str, sorted((ref / "lib").glob("*.c"))),
        str(ROOT / "crypto_kit/native/cross_bridge.c"), "-o", str(output),
    ]
    subprocess.run(command, check=True)
    print(f"CROSS v2.2 RSDP-128-{variant}: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=[*VARIANTS, "all"], default="all")
    args = parser.parse_args()
    for variant in VARIANTS if args.variant == "all" else [args.variant]:
        build(variant)
