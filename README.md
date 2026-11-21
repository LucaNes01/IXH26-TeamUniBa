# Photographic Provenance · IXH26 Team Bari

The project verifies two steps from physical capture to the published file.

1. **Capture.** The acquisition module signs the capture ID and the RAW file's SHA-256 digest. The registry recomputes the digest from the received bytes and verifies the signature with the registered device key.
2. **Processing.** `verifica_elaborazione()` reruns the verifier's deterministic pipeline on the RAW. Verification succeeds when the output matches the received file byte for byte.

## Reading the code

Start with the [public Python API](protocollo/__init__.py), then follow a photo from the sensor certificate to the validators' votes. The [integration tests](tests/test_dispositivi.py) provide concrete examples. Start with `test_la_registrazione_abilita_la_verifica_e_consuma_la_sfida` for keys, a registration challenge, and signed approvals.

### From sensor enrollment to a verified photo

| Step | Files | What to follow |
| --- | --- | --- |
| 1 | [Signature API](crypto_kit/__init__.py) and [CROSSSigner](crypto_kit/cross_official.py) | Start with `keygen`, `sign`, and `verify`. The authority, device, and validators use the same API with their own keys. |
| 2 | [dispositivi.py](protocollo/dispositivi.py) | The authority signs a `CertificatoSensore`. The registry issues a challenge, the device signs its response, and the validators approve the request. `registra` consumes the challenge and returns a `ProvaIscrizione`. `verifica_iscrizione` checks the proof using public configuration. |
| 3 | [ledger.py](protocollo/ledger.py) | `impronta_iscrizione` hashes the enrollment proof. `prepara_ancoraggio` puts the digest and the device ID into an XRPL transaction memo. An external wallet signs and submits the transaction. `verifica_ancoraggio` checks the account, memo, and result on a validated ledger. Later captures use the same enrollment proof. |
| 4 | [provenienza.py](protocollo/provenienza.py) and [acquisizione.py](protocollo/acquisizione.py) | Read what the device signs to produce an `AttestazioneDispositivo`. Then follow `acquisisci_cattura_aes` from the driver request through AES-CMAC verification to the CROSS signature. `verifica_elaborazione` compares the pipeline output with the submitted photo. |
| 5 | [bayer.py](protocollo/bayer.py) and [prnu.py](protocollo/prnu.py) | The Bayer module checks geometry and separates the four positions in a RAW mosaic. `stima_prnu_bayer` builds a reference during calibration, and `punteggi_prnu_bayer` scores a capture against it. `RegistroDispositivi.verifica_cattura_bayer` reports the signature, geometry, and fingerprint checks. |
| 6 | [origine.py](protocollo/origine.py) | `QuorumOrigine.valuta` produces a `RapportoOrigine`. Follow `messaggio_da_approvare` on the validator and `verifica` on the recipient. The enrollment and photo-approval committees are configured separately. |
| 7 | [rete_origine.py](protocollo/rete_origine.py) | Follow `PacchettoOrigine` from the sender to `server_validatore`. The node exposes reports at `/rapporto` and votes at `/approvazioni`. The sender calls `raccogli_approvazioni` and checks the resulting votes with `verifica_prova_distribuita`. |
| 8 | [Violations](protocollo/origine.py) and [revoche.py](protocollo/revoche.py) | If the pipeline output differs, `RapportoOrigine.attribuibile` requires valid checks for the RAW signature, Bayer geometry, and PRNU, along with a device-signed `DichiarazioneSviluppo` binding the RAW, photo, and policy. Nodes vote via `/violazioni`. After a quorum, `registra_violazione` records the RAW/photo pair once per device in SQLite. The registry treats the device as revoked at the configured threshold, which defaults to three. |

### Other input paths

- **Standalone JPEG.** `analizza_jpeg` starts with optional C2PA credential verification and can compare the image against a calibrated JPEG PRNU catalog. [JPEG analysis](protocollo/jpeg.py) · [C2PA verification](protocollo/credenziali.py) · [Catalog test](tests/test_dispositivi.py)
- **Statistical AI detection.** `CommunityForensics224` loads the model, `QuorumIA` defines what each node signs, and `raccogli_voti_ia` collects votes over HTTP. The test exercises a quorum with one node offline. [Model and votes](protocollo/analisi_ia.py) · [HTTP collection](protocollo/rete_origine.py) · [AI test](tests/test_analisi_ia.py)
- **RAW series at different exposures.** `stima_profilo_fotonico` and `verifica_profilo_fotonico` compare temporal variance with a calibration reference. [Photon noise](protocollo/rumore_fotonico.py) · [Curve test](tests/test_rumore_fotonico.py)

### Native backend, tests, and project notes

- **From Python to C.** Key and signature sizes are in [specs.py](crypto_kit/specs.py). The [Python wrapper](crypto_kit/cross_official.py) loads the library through the [C bridge](crypto_kit/native/cross_bridge.c). The [build script](scripts/build_cross.py) checks the sources and builds the `small` and `fast` variants. [CROSS integration notes](third_party/cross/INTEGRATION.md) · [Upstream manifest](third_party/cross/UPSTREAM.json)
- **Known-answer tests.** The [CROSS test](tests/test_cross_official.py) compares keys and signatures with [reference vectors](tests/fixtures/). The [KAT verification script](scripts/verify_cross_kat.py) runs the official generator and checks full checksums.
- **From individual checks to a distributed proof.** Read the [capture and development tests](tests/test_provenienza.py), [XRPL response tests](tests/test_ledger.py), and [registry and validator tests](tests/test_dispositivi.py). The last file includes validators running in separate processes and a simulated XRPL node.

## Running the project

```sh
python3 scripts/build_cross.py
python3 -B -m unittest discover -s tests -v
```

The build requires Python 3 and a C11 compiler on macOS or Linux. It uses the CROSS v2.2 reference library bundled in `third_party/cross/`. Image analysis uses the [PRNU and JPEG dependencies](requirements-prnu.txt). The AES-CMAC adapter also requires `cryptography`. The optional AI detector uses the [AI dependencies](requirements-ia.txt) and the checkpoint linked below.

## Device enrollment

The verifier configures the public keys of trusted authorities. Each device presents a `CertificatoSensore` that one of those authorities signed with CROSS. The certificate binds the sensor identifier to a capture key and validity period. The authority verifies the link to the physical module before signing the bytes returned by `messaggio_certificato_sensore(...)`. The project uses its own certificate format. The signature also covers the optional `tecnologia_sensore` field, which can identify different sensor technologies.

`verifica_certificato()` checks the authority, signature, and validity period. The device signs a one-time challenge together with its certificate digest. Each validator reconstructs the message, verifies the request, and signs an approval bound to the device's response and the committee configuration. The in-memory registry accepts a request once it has enough valid signatures from distinct members. RAW verification requires a certificate that is valid at verification time.

In the intended hardware flow, the capture module generates its key pair on first activation, retains the private key, and sends its public key to the certification service. Once enrolled, `certificato_pubblico()` and `prova_pubblica()` expose the certificate and complete enrollment proof. Hardware integration and network distribution of enrollment requests among independent validators are pending.

```python
from protocollo import (
    ApprovazioneDispositivo, AttestazioneDispositivo, RegistroDispositivi,
    RichiestaRegistrazione, messaggio_registrazione_dispositivo,
    verifica_elaborazione,
)

registro = RegistroDispositivi(chiavi_autorita_fidate, chiavi_validatori, soglia)
sfida = registro.emetti_sfida(certificato_sensore)
chiave_dispositivo = certificato_sensore.chiave_dispositivo
messaggio = messaggio_registrazione_dispositivo(certificato_sensore, sfida)
firma_registrazione = modulo_di_cattura.firma(messaggio)
richiesta = RichiestaRegistrazione(certificato_sensore, sfida, firma_registrazione)

# Run this step on each validator.
if verificatore_del_validatore.verifica_richiesta(richiesta):
    messaggio = verificatore_del_validatore.messaggio_approvazione(richiesta)
    voto = ApprovazioneDispositivo(chiave_validatore, validatore.firma(messaggio))

# Collect the validators’ signed approvals in the registry.
prova = registro.registra(richiesta, approvazioni_raccolte)

attestazione = AttestazioneDispositivo(scatto_id, chiave_dispositivo, firma)
cattura_verificata = registro.verifica_cattura(raw, attestazione)
provenienza_verificata = cattura_verificata and verifica_elaborazione(
    raw, foto_finale, pipeline_consentita,
)
```

`raw` and `foto_finale` contain the received file bytes. The capture module signs the bytes returned by `messaggio_cattura_dispositivo(scatto_id, impronta_raw, chiave_dispositivo)`.

### AES-CMAC authentication at capture

The optional `protocollo.acquisizione` adapter uses `cryptography`. The sensor and capture module share a dedicated AES-256 key unique to the device. The module generates a fresh capture ID for each request. The sensor computes an AES-CMAC over the pixel bytes it has just read, binding them to the capture ID and device public key. It returns the frame and tag together.

```python
from protocollo.acquisizione import acquisisci_cattura_aes

# The driver requests a new authenticated frame for this capture ID.
raw, attestazione = acquisisci_cattura_aes(
    driver.leggi_fotogramma_autenticato, chiave_pubblica=chiave_dispositivo,
    chiave_aes=chiave_aes_modulo, firma_cross=modulo_di_cattura.firma,
)
```

The module verifies the tag before hashing the frame for the CROSS signature. The registry and validators verify the attestation with the public key. The sensor and capture module retain the AES key. The software adapter has been tested. A physical device requires a sensor driver that produces the tag during readout and a trusted module that stores the keys and enforces tag verification before signing. Preserve the original authenticated frame bytes when repackaging or processing the frame.

## PRNU comparison

Install the optional dependencies with `python3 -m pip install -r requirements-prnu.txt`. The authority uses `protocollo.prnu.stima_prnu` to estimate a reference from multiple evenly illuminated captures of the same sensor under controlled conditions. It includes the digest returned by `protocollo.prnu.impronta_prnu` as `prnu_sha256` in both `messaggio_certificato_sensore` and `CertificatoSensore`. The enrollment quorum approves the request tied to that certificate. The enrollment proof digest can then be anchored on XRPL.

```python
cattura_compatibile = registro.verifica_cattura_prnu(
    raw, attestazione, riferimento, decodifica=decodifica_raw, soglia=soglia_calibrata,
)
```

The verifier checks the RAW's CROSS signature and the reference digest, then compares the noise in the decoded pixels with the certified reference. The verifier selects a decoder for the camera format. It must return a monochrome array of linear pixels in `[0, 1]` matching the reference geometry and alignment. The prototype uses a Gaussian residual and normalized correlation. Calibrate the threshold using real captures from the target sensor and other sensors. The score measures statistical compatibility with the sensor at capture.

### Bayer RAW

When the RAW preserves the original mosaic, the authority can call `stima_prnu_bayer` on reference captures and sign the digest from `impronta_prnu_bayer`. The digest binds the color pattern to four fingerprints ordered by position in the `2 × 2` block. The order for `RGGB` is `R, G₁, G₂, B`.

```python
from protocollo.prnu import impronta_prnu_bayer, stima_prnu_bayer

schema_bayer = "RGGB"
riferimenti = stima_prnu_bayer(mosaici_di_calibrazione)
prnu_sha256 = impronta_prnu_bayer(riferimenti, schema_bayer)
# The authority sets prnu_sha256 in the signed certificate before enrollment.
cattura_compatibile = registro.verifica_cattura_prnu(
    raw, attestazione, riferimenti, decodifica=decodifica_mosaico_raw,
    soglia=soglia_calibrata, schema_bayer=schema_bayer,
)
```

Configure the decoder for the camera. It must return the linear mosaic in `[0, 1]` before demosaicing, with the same active area, orientation, and grid origin used during calibration. All four scores must reach the threshold. `punteggi_prnu_bayer` returns individual scores for calibration. Certificates issued with a single fingerprint can still use that reference.

Use `registro.verifica_cattura_bayer` for separate signature, Bayer structure, and PRNU results. The decoder returns a `MosaicoBayer` containing the pixels and geometry read from the RAW. The verifier provides the calibration `GeometriaBayer`, including the pattern, dimensions in rows and columns, and origin on the sensor. A result of `None` means the check did not run.

### Standalone JPEG analysis

The node can check an embedded C2PA credential before consulting its PRNU catalog. Install `c2pa-python==0.39.0` and pass a PEM bundle containing the node's trusted roots to `analizza_jpeg` through `radici_c2pa_pem`. The verifier checks the signature, the signer's certificate chain, and the binding to the received JPEG. It uses the embedded manifest and any revocation data included in the credential.

If the verified manifest declares that generative AI created the JPEG, the result is `generata_ia`. Otherwise the node continues with the PRNU catalog. When C2PA is enabled, the response includes the credential state `verificata`, `assente`, or `non_verificata`. A verified credential without a declaration of AI generation leaves the physical origin open.

For PRNU comparison, the sender supplies the JPEG. The node configures a catalog of enrollment proofs, XRPL transaction IDs, reference fingerprints, and thresholds. The authority builds a reference with `stima_prnu_jpeg` using original, evenly illuminated JPEGs acquired with the same mode and geometry. Before enrollment, it uses `impronta_prnu_jpeg(riferimento)` as `prnu_jpeg_sha256` in both the signed message and the certificate. JPEG and Bayer RAW use separate references.

```python
from protocollo.jpeg import RiferimentoJPEG, analizza_jpeg

catalogo = [RiferimentoJPEG(prova_iscrizione, tx_id, riferimento_jpeg, soglia_jpeg)]

def valuta_jpeg(dati):
    return analizza_jpeg(dati, registro_pubblico, catalogo,
                        conto_pubblicatore_xrpl=conto_pubblicatore)

esito = valuta_jpeg(jpeg)
```

Pass `analisi_jpeg=valuta_jpeg` to `server_validatore` to enable `POST /analisi-jpeg` with the JPEG bytes as the request body. The result includes scores for usable references. It can report `compatibile` with one catalog sensor, `ambiguo` across multiple sensors, `nessuna_corrispondenza` among compared sensors, or `non_valutabile` when there are no usable references. Calibrate thresholds on real JPEGs. The comparison requires aligned rasters of the same size. Compression and resizing can lower the score. The comparison provides forensic evidence, while the derivation proof still requires the signed RAW.

### Quorum for statistical AI detection on a standalone JPEG

The node can run **Community Forensics ViT-S/16 224** (Park and Owens, CVPR 2025) locally. Run `python3 -m pip install -r requirements-ia.txt` and download the [authors' MIT-licensed weights](https://huggingface.co/OwensLab/commfor-model-224/blob/26afc31e6b40c312c3fd42c05a758be62446215b/model.safetensors). The loader checks the SHA-256 digest before loading the checkpoint. It follows the authors' evaluation procedure for RGB decoding, resizing, center cropping, and normalizing.

```python
from protocollo.analisi_ia import CommunityForensics224, QuorumIA
from protocollo.rete_origine import raccogli_voti_ia

quorum_ia = QuorumIA(quorum_foto, soglia_ia=soglia_calibrata)
rilevatore_ia = CommunityForensics224("model.safetensors")
# Pass quorum_ia=quorum_ia and rilevatore_ia=rilevatore_ia to server_validatore.
# Node URLs for this function end in /voti-ia.
voti = raccogli_voti_ia(jpeg, quorum_ia, url_validatori_ia)
esito = quorum_ia.verifica(jpeg, voti)
```

Each vote binds the JPEG digest, model version and digest, threshold, score, and outcome. `raccogli_voti_ia` looks for the required number of distinct signatures on the same outcome. Public verification returns `probabile_ia`, `inconcludente`, or `None` when a valid quorum is unavailable. The model score has not been calibrated as a probability for our catalog. Calibrate the threshold on real and synthetic JPEGs, including recompressed images and inputs from generators excluded from the calibration set when evaluating generalization. The quorum attests the statistical result. The RAW, signature, and XRPL checks follow the photo provenance path.

### Photo provenance quorum

`QuorumOrigine` uses a committee configured separately from the enrollment committee. The verifier fixes the decoder, expected geometry, PRNU threshold, deterministic pipeline, and authorized XRPL publishing account, then distributes the policy digest to the validators. Each validator checks the enrollment signatures and independently queries its configured XRPL node for a successful validated transaction from the authorized account containing the same proof digest. It then checks the RAW and final photo. Each vote binds the enrollment proof and transaction ID.

```python
from protocollo import ApprovazioneDispositivo, QuorumOrigine

quorum = QuorumOrigine(
    chiavi_validatori_foto, soglia_voti, hash_politica,
    geometria_attesa=geometria, decodifica=decodifica_mosaico,
    soglia_prnu=soglia_calibrata, elabora=pipeline_approvata,
    conto_pubblicatore_xrpl=conto_pubblicatore,
)
ancoraggio = dict(iscrizione=prova_iscrizione, tx_id_xrpl=tx_id)
messaggio = quorum.messaggio_da_approvare(registro, raw, foto_finale, attestazione, riferimenti, **ancoraggio)
if messaggio is not None:
    voto = ApprovazioneDispositivo(chiave_validatore, validatore.firma(messaggio))

origine_approvata = quorum.verifica(registro, raw, foto_finale, attestazione, voti_raccolti, **ancoraggio)
```

Quorum verification covers a single attested RAW. Separately, `rumore_fotonico` examines the relationship between mean signal and temporal variance using at least three pairs of linear RAW captures at different exposures. Use uniform illumination, fixed gain, and avoid clipping. Including this signal in the decision for a photo would require an attested capture series linked to that photo.

#### Validators on separate processes or machines

Each node loads its own voting key and the public configuration of the quorum, authorities, and enrollment committee. It also loads the decoder, approved pipeline, and PRNU reference. The uploader sends the RAW, final file, capture attestation, public enrollment proof, and XRPL transaction ID. Before signing, each node independently verifies the proof and anchor, checks the Bayer geometry and PRNU, and reruns the pipeline.

```python
from protocollo.rete_origine import (
    PacchettoOrigine, raccogli_approvazioni, server_validatore, verifica_prova_distribuita,
)

# Run on each node with its own private voting key.
with server_validatore(
    ("127.0.0.1", porta), registro_pubblico, quorum,
    chiave_validatore=chiave_pubblica_del_nodo, firma=firmatario_del_nodo,
    riferimenti=riferimenti,
) as nodo:
    nodo.serve_forever()

# Run in another process using the configuration and public keys.
pacchetto = PacchettoOrigine(raw, foto_finale, attestazione, prova_iscrizione, tx_id)
voti = raccogli_approvazioni(pacchetto, registro_pubblico, quorum, url_approvazioni)
origine_approvata = verifica_prova_distribuita(pacchetto, registro_pubblico, quorum, voti)
```

Validator URLs end in `/approvazioni`. The collector queries nodes in parallel and counts valid signatures from distinct members. Anyone with the package, votes, and public configuration can verify the result without contacting the validators. Full verification independently queries XRPL. When validators run on different machines, use a trusted network or an HTTPS proxy.

## XRP Ledger anchoring

The service prepares an `AccountSet` transaction whose memo contains the device ID and the enrollment proof's SHA-256 digest. The digest covers the certificate, challenge, signed response, committee configuration, and approvals. The caller stores the proof off-chain with the transaction ID. The wallet completes, signs, and submits the transaction from the publishing account and pays the network fee.

```python
from protocollo import prepara_ancoraggio, verifica_ancoraggio

transazione = prepara_ancoraggio(prova, conto_pubblicatore)
# The external verifier receives the proof and transaction ID.
iscrizione_verificata = verificatore_esterno.verifica_iscrizione(prova)
ancorato = verifica_ancoraggio(prova, tx_id, conto_pubblicatore)
provenienza_verificata = provenienza_verificata and iscrizione_verificata and ancorato
```

Verification queries XRPL Testnet by default and requires a successful transaction in a validated ledger. The verifier configures the authorities, committee, threshold, RPC node, and publishing account. It verifies the proof's signatures and checks the digest published on XRPL. The application handles network publication of the proof and wallet submission outside the Python registry.

Verifying physical capture requires integrating a module that signs during acquisition. Verifying derivation requires a deterministic pipeline with fixed operations, parameters, and versions. The comparison proves that the approved pipeline reproduces the received file. Establishing the actual execution history would require an attestation from that process. Work on verification that tolerates changes to the file is on hold.

[CROSS reference backend](https://github.com/CROSS-signature/CROSS-implementation).
