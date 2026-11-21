"""Confronto cieco delle impronte Bayer di due esemplari dello stesso modello."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from protocollo.bayer import SCHEMI_BAYER
from protocollo.prnu import punteggi_prnu_bayer, stima_prnu_bayer


def mosaico(file, schema):
    if file.suffix.lower() == ".npy":
        return np.load(file, allow_pickle=False)
    import rawpy

    with rawpy.imread(str(file)) as raw:
        colori = raw.raw_colors_visible[:2, :2].copy()
        disposizione = "".join(chr(raw.color_desc[i]) for i in colori.flat)
        if raw.raw_pattern is None or raw.raw_pattern.shape != (2, 2) or disposizione != schema:
            raise ValueError(f"Mosaico diverso da {schema}: {file}")
        pixels = raw.raw_image_visible.astype(np.float32)
        neri = raw.black_level_per_channel
        bianchi = raw.camera_white_level_per_channel
        for (r, c), indice in np.ndenumerate(colori):
            nero = neri[indice]
            bianco = bianchi[indice] if bianchi and bianchi[indice] else raw.white_level
            if bianco <= nero:
                raise ValueError(f"Livelli RAW incoerenti: {file}")
            piano = pixels[r::2, c::2]
            piano -= nero
            piano /= bianco - nero
        return np.clip(pixels, 0, 1)


def files(cartella):
    immagini = sorted(p for p in cartella.iterdir() if p.is_file() and not p.name.startswith("."))
    if not immagini:
        raise ValueError(f"Cartella vuota: {cartella}")
    return immagini


def esegui(radice, schema):
    visti = {}
    forma = None

    def leggi(file):
        nonlocal forma
        dati = np.ascontiguousarray(mosaico(file, schema), dtype="<f4")
        if dati.ndim != 2 or not np.isfinite(dati).all() or dati.min() < 0 or dati.max() > 1:
            raise ValueError(f"Serve un mosaico lineare normalizzato: {file}")
        if forma is None:
            forma = dati.shape
        if dati.shape != forma:
            raise ValueError(f"Geometria diversa: {file}")
        digest = hashlib.sha256(dati).digest()
        if digest in visti:
            raise ValueError(f"Acquisizione duplicata: {file} e {visti[digest]}")
        visti[digest] = file
        return dati

    camere = ("A", "B")
    riferimenti = {}
    for camera in camere:
        flat = files(radice / "uniformi" / camera)
        riferimenti[camera] = stima_prnu_bayer(leggi(file) for file in flat)

    def valuta(file):
        dati = leggi(file)
        try:
            return {c: punteggi_prnu_bayer(dati, rif) for c, rif in riferimenti.items()}
        except ValueError as errore:
            if str(errore) not in {"Segnale insufficiente per il confronto PRNU.",
                                   "Pixel utilizzabili insufficienti per il confronto PRNU."}:
                raise
            return None

    propri, estranei = [], []
    calibrazione = {}
    for camera in camere:
        inizio = len(propri)
        scatti = files(radice / "soglia" / camera)
        for file in scatti:
            punti = valuta(file)
            if punti:
                propri.append(min(punti[camera]))
                estranei.append(min(punti["B" if camera == "A" else "A"]))
        calibrazione[camera] = {"totali": len(scatti), "valutabili": len(propri) - inizio}
        if len(propri) == inizio:
            raise ValueError(f"Nessuno scatto valutabile per calibrare {camera}")

    # A parità di errori complessivi preferiamo meno false accettazioni.
    def costo(s):
        fa = sum(x >= s for x in estranei)
        return (fa + sum(x < s for x in propri), fa, s)

    candidati = sorted(set(propri + estranei))
    soglia = min([*candidati, np.nextafter(candidati[-1], np.inf)], key=costo)
    ciechi = {p.name: valuta(p) for p in files(radice / "cieco")}
    verita = json.loads((radice / "verita.json").read_text())
    if set(verita) != set(ciechi) or set(verita.values()) != set(camere):
        raise ValueError("La verità deve coprire tutti i file ciechi e contenere entrambi gli esemplari.")

    righe = []
    fa = fr = validi = 0
    for nome, punti in ciechi.items():
        origine = verita[nome]
        accettati = []
        if punti:
            validi += 1
            accettati = [c for c in camere if min(punti[c]) >= soglia]
            fr += origine not in accettati
            fa += any(c != origine for c in accettati)
        righe.append(dict(file=nome, origine=origine, punteggi=punti, accettati=accettati))
    return dict(schema=schema, soglia=soglia, calibrazione=calibrazione, valutabili=validi,
                non_valutabili=len(righe)-validi, falsi_rifiuti=fr, false_accettazioni=fa,
                denominatore_per_tasso=validi, scatti=righe)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cartella", type=Path)
    parser.add_argument("--schema", choices=SCHEMI_BAYER, required=True)
    args = parser.parse_args()
    print(json.dumps(esegui(args.cartella, args.schema), indent=2, allow_nan=False))
