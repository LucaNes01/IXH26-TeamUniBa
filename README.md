# Provenienza fotografica · IXH26 Team Bari

Il progetto verifica due passaggi, dalla cattura fisica al file pubblicato.

1. **Cattura.** Il modulo di acquisizione firma l'identificativo dello scatto e
   l'impronta SHA-256 del RAW. Il registro ricalcola l'impronta dai byte ricevuti
   e verifica la firma usando la chiave del dispositivo registrato.
2. **Elaborazione.** `verifica_elaborazione()` ripete sul RAW la pipeline
   deterministica scelta dal verificatore. La verifica passa se il risultato
   coincide byte per byte con il file finale ricevuto.

## Guida alla lettura del codice

Il progetto è una libreria Python. Per orientarti, apri [l’API pubblica](protocollo/__init__.py), poi segui una foto dal certificato del sensore fino al voto dei validatori. Tieni aperto [il test di integrazione](tests/test_dispositivi.py) accanto ai moduli. La funzione di test `test_la_registrazione_abilita_la_verifica_e_consuma_la_sfida` mostra il primo passaggio con chiavi, richiesta e approvazioni concrete.

### Percorso principale · dal sensore alla foto verificata

| Ordine | File da aprire | Cosa seguire nel codice |
| --- | --- | --- |
| 1 | [API delle firme](crypto_kit/__init__.py) e [implementazione di CROSSSigner](crypto_kit/cross_official.py) | Parti da `keygen`, `sign` e `verify`. Autorità, dispositivo e validatori usano la stessa API con chiavi diverse. Puoi rimandare il codice C alla fine della lettura. |
| 2 | [dispositivi.py](protocollo/dispositivi.py) | Segui i dati in ordine: l’autorità firma il `CertificatoSensore`, il registro emette una sfida, il dispositivo firma la risposta e i validatori approvano la richiesta. `registra` consuma la sfida e restituisce la `ProvaIscrizione`. `verifica_iscrizione` mostra come controllarla con la configurazione pubblica. |
| 3 | [ledger.py](protocollo/ledger.py) | `impronta_iscrizione` calcola il digest della prova. `prepara_ancoraggio` lo inserisce con l’ID del dispositivo nel memo di una transazione XRPL. Un wallet esterno firma e invia. `verifica_ancoraggio` usa l’ID della transazione per controllare conto, memo ed esito sul ledger validato. La stessa iscrizione fa da riferimento per gli scatti successivi. |
| 4 | [provenienza.py](protocollo/provenienza.py) e [acquisizione.py](protocollo/acquisizione.py) | Leggi prima cosa firma il dispositivo per produrre una `AttestazioneDispositivo`. Poi segui `acquisisci_cattura_aes` per vedere come l’adattatore chiede al driver un nuovo fotogramma e verifica il tag AES-CMAC prima della firma CROSS. Torna a `verifica_elaborazione` per il confronto tra i byte prodotti dalla pipeline e la foto ricevuta. |
| 5 | [bayer.py](protocollo/bayer.py) e [prnu.py](protocollo/prnu.py) | Il primo modulo verifica la geometria del mosaico RAW e ne separa le quattro posizioni colore. Nel secondo, segui `stima_prnu_bayer` durante la calibrazione e `punteggi_prnu_bayer` durante il confronto con uno scatto. `RegistroDispositivi.verifica_cattura_bayer` riunisce gli esiti di firma, geometria e impronta del sensore. |
| 6 | [origine.py](protocollo/origine.py) | Parti da `QuorumOrigine.valuta`, che produce un `RapportoOrigine` per la foto. Segui poi `messaggio_da_approvare` sul validatore e `verifica` sul destinatario dei voti. Qui si vede la differenza tra il comitato che iscrive il sensore e quello che approva la provenienza di uno scatto. |
| 7 | [rete_origine.py](protocollo/rete_origine.py) | Segui `PacchettoOrigine` dal mittente a `server_validatore`. Il nodo espone il rapporto su `/rapporto` e il voto su `/approvazioni`. Sul mittente, `raccogli_approvazioni` interroga i nodi e `verifica_prova_distribuita` controlla i voti raccolti. |
| 8 | [Contestazioni](protocollo/origine.py) e [revoche.py](protocollo/revoche.py) | Se la pipeline produce una foto incompatibile, guarda `RapportoOrigine.attribuibile`. Occorrono anche firma del RAW, Bayer e PRNU validi e una `DichiarazioneSviluppo` firmata dal dispositivo che leghi RAW, foto e politica. I nodi votano su `/violazioni`. Al quorum, `registra_violazione` aggiorna SQLite. La transazione locale conta una sola volta la stessa coppia RAW/foto per dispositivo. Alla soglia configurata (predefinita 3) il registro considera il dispositivo revocato. |

### Percorsi che usano dati diversi

- **Hai soltanto un JPEG.** Segui `analizza_jpeg` dalla verifica facoltativa delle credenziali C2PA al confronto con il catalogo PRNU. Il test con un JPEG isolato mostra come configurare il catalogo del nodo. [Analisi JPEG](protocollo/jpeg.py) · [Verifica C2PA](protocollo/credenziali.py) · [Test del catalogo](tests/test_dispositivi.py)
- **Hai soltanto un JPEG e vuoi valutare l’ipotesi di generazione IA.** Leggi prima `CommunityForensics224` per il caricamento del modello, poi `QuorumIA` per capire cosa firmano i nodi. Segui infine `raccogli_voti_ia` nel modulo di rete. Il test esercita il quorum anche con un nodo offline. [Modello e voti](protocollo/analisi_ia.py) · [Raccolta via HTTP](protocollo/rete_origine.py) · [Test IA](tests/test_analisi_ia.py)
- **Hai una serie di RAW a esposizioni diverse.** Segui `stima_profilo_fotonico` e `verifica_profilo_fotonico` per il confronto della varianza temporale con la calibrazione. Questo esperimento richiede più acquisizioni e ha un test dedicato. [Rumore fotonico](protocollo/rumore_fotonico.py) · [Test della curva](tests/test_rumore_fotonico.py)

### Backend nativo, test e documenti di progetto

- **Dalla firma Python al C.** Le dimensioni di chiavi e firme sono in [specs.py](crypto_kit/specs.py). Il [wrapper Python](crypto_kit/cross_official.py) carica la libreria compilata attraverso il [bridge C](crypto_kit/native/cross_bridge.c). Lo [script di build](scripts/build_cross.py) verifica i sorgenti e compila le varianti `small` e `fast`. Per entrare nei sorgenti di terze parti, parti dalle [note di integrazione CROSS](third_party/cross/INTEGRATION.md) e dal [manifest della versione inclusa](third_party/cross/UPSTREAM.json).
- **Dai risultati attesi ai test delle firme.** Il [test CROSS](tests/test_cross_official.py) confronta chiavi e firme con i [vettori di riferimento](tests/fixtures/). Lo [script di verifica KAT](scripts/verify_cross_kat.py) esegue il generatore ufficiale e controlla i checksum completi.
- **Dai singoli controlli alla prova distribuita.** Leggi nell’ordine i [test di cattura e sviluppo](tests/test_provenienza.py), i [test delle risposte RPC di XRPL](tests/test_ledger.py) e i [test del registro e dei nodi](tests/test_dispositivi.py). In quest’ultimo file trovi anche validatori avviati in processi distinti e un nodo XRPL simulato.
- **Per ricostruire le decisioni del team.** Consulta le [note iniziali](IXH26%20niccol%C3%B2.txt), il [percorso progettuale](docs/IDEA_ATTUALE_E_PERCORSO.md) e la [valutazione dei miglioramenti](docs/STATO_PERCENTUALI_E_MIGLIORAMENTI.md). Questi documenti comprendono proposte e fotografie di fasi precedenti del lavoro.

## Esecuzione

```sh
python3 scripts/build_cross.py
python3 -B -m unittest discover -s tests -v
```

Il build richiede Python 3 e un compilatore C11 su macOS o Linux. Usa la
libreria di riferimento CROSS v2.2 inclusa in `third_party/cross/`.
Per i moduli di analisi delle immagini usa le [dipendenze PRNU e JPEG](requirements-prnu.txt).
L’adattatore AES-CMAC richiede anche `cryptography`. Per eseguire il modello IA
servono le [dipendenze IA](requirements-ia.txt) e i pesi indicati nella sezione dedicata.

## Iscrizione del dispositivo

Il verificatore configura le chiavi pubbliche delle autorità fidate. Ogni
modulo presenta un `CertificatoSensore` firmato con CROSS da una di queste
autorità. Il certificato lega l'identificativo del sensore alla chiave di
cattura e al periodo di validità. L'autorità firma i byte restituiti da
`messaggio_certificato_sensore(...)` dopo aver verificato il legame con il
modulo fisico. Il codice usa un formato del progetto, distinto da X.509.

Il campo facoltativo `tecnologia_sensore` è coperto dalla firma dell'autorità.
Il protocollo accetta sensori di tecnologie diverse. Per la firma del RAW
serve un modulo di acquisizione fidato.

`verifica_certificato()` controlla autorità, firma e validità temporale.
Il dispositivo firma la sfida monouso insieme all'impronta del proprio
certificato. Ogni validatore ricostruisce il messaggio, verifica la richiesta
e firma un'approvazione legata alla risposta del dispositivo e alla
configurazione del comitato. Il registro accetta la richiesta quando
raggiunge la soglia di firme valide di membri distinti. Il registro è in
memoria e la verifica del RAW richiede un certificato ancora valido al
momento del controllo.

Nel flusso previsto, alla prima attivazione il modulo di cattura genera la
coppia di chiavi. La chiave privata rimane nel modulo. La chiave pubblica può
essere inviata al servizio che certifica il sensore. Dopo la registrazione,
`certificato_pubblico()` e `prova_pubblica()` espongono rispettivamente il
certificato e l'intera prova di iscrizione. Il collegamento all'hardware e la
distribuzione delle richieste di iscrizione fra validatori indipendenti sono
da integrare.

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

# Questo passaggio avviene presso ciascun validatore.
if verificatore_del_validatore.verifica_richiesta(richiesta):
    messaggio = verificatore_del_validatore.messaggio_approvazione(richiesta)
    voto = ApprovazioneDispositivo(chiave_validatore, validatore.firma(messaggio))

# Il registro riceve le approvazioni firmate dei validatori.
prova = registro.registra(richiesta, approvazioni_raccolte)

attestazione = AttestazioneDispositivo(scatto_id, chiave_dispositivo, firma)
cattura_verificata = registro.verifica_cattura(raw, attestazione)
provenienza_verificata = cattura_verificata and verifica_elaborazione(
    raw, foto_finale, pipeline_consentita,
)
```

`raw` e `foto_finale` sono i byte dei file ricevuti. Il modulo di acquisizione
firma i byte restituiti da `messaggio_cattura_dispositivo(scatto_id,
impronta_raw, chiave_dispositivo)`.

### Autenticazione AES-CMAC durante la cattura

L'adattatore opzionale `protocollo.acquisizione` richiede il pacchetto
`cryptography`. Il sensore e il modulo di acquisizione condividono una chiave
AES-256 dedicata, distinta per dispositivo. Per ogni richiesta, il modulo
genera un nuovo ID di scatto. Il sensore calcola AES-CMAC direttamente sui
byte dei pixel appena letti, legandoli all'ID e alla chiave pubblica del
dispositivo. Restituisce il fotogramma e il tag nella stessa risposta.

```python
from protocollo.acquisizione import acquisisci_cattura_aes

# Il driver chiede al sensore un nuovo fotogramma autenticato per questo ID.
raw, attestazione = acquisisci_cattura_aes(
    driver.leggi_fotogramma_autenticato, chiave_pubblica=chiave_dispositivo,
    chiave_aes=chiave_aes_modulo, firma_cross=modulo_di_cattura.firma,
)
```

Il modulo verifica il tag prima di calcolare l'hash per la firma CROSS. Il
registro e i validatori verificano l'attestazione con la chiave pubblica.
La chiave AES resta nel sensore e nel modulo di acquisizione.
L'adattatore è testato in software. Su un dispositivo reale richiede un
driver per il sensore che produce il tag durante la lettura e un modulo
fidato che custodisca le chiavi e imponga il controllo prima di firmare.
Il fotogramma autenticato va conservato nei byte originali se in seguito
viene inserito in un altro contenitore o elaborato per ottenere la foto finale.

## Confronto PRNU

Installare le dipendenze opzionali con `python3 -m pip install -r requirements-prnu.txt`.
L'autorità stima il riferimento con `protocollo.prnu.stima_prnu` a partire da
più acquisizioni uniformi dello stesso sensore in condizioni controllate.
Firma il digest restituito da `protocollo.prnu.impronta_prnu`, passandolo come
`prnu_sha256` sia a `messaggio_certificato_sensore` sia a `CertificatoSensore`.
Il quorum approva la richiesta di iscrizione legata a quel certificato e
l'ancoraggio può pubblicare su XRPL l'impronta della prova di iscrizione.

```python
cattura_compatibile = registro.verifica_cattura_prnu(
    raw, attestazione, riferimento, decodifica=decodifica_raw, soglia=soglia_calibrata,
)
```

Il verificatore controlla la firma CROSS del RAW e il digest del riferimento.
Poi confronta il rumore dei pixel decodificati con il riferimento certificato.
Il decoder, scelto dal verificatore per il formato della fotocamera, deve
restituire una matrice monocromatica di pixel lineari in `[0, 1]`, allineata
al riferimento e con la stessa geometria. Il prototipo usa un residuo
gaussiano e una correlazione normalizzata. La soglia va calibrata su scatti
reali del sensore e di altri sensori. Il punteggio indica compatibilità
statistica con il sensore e riguarda la fase di cattura.

### RAW con mosaico Bayer

Se il RAW conserva il mosaico originale, l'autorità può usare `stima_prnu_bayer`
sugli scatti di riferimento e firmare il digest di `impronta_prnu_bayer`. Il digest
lega lo schema colore alle quattro impronte ordinate per posizione nel blocco
`2 × 2`. Per `RGGB` l'ordine è `R, G₁, G₂, B`.

```python
from protocollo.prnu import impronta_prnu_bayer, stima_prnu_bayer

schema_bayer = "RGGB"
riferimenti = stima_prnu_bayer(mosaici_di_calibrazione)
prnu_sha256 = impronta_prnu_bayer(riferimenti, schema_bayer)
# L'autorità inserisce prnu_sha256 nel certificato firmato prima dell'iscrizione.
cattura_compatibile = registro.verifica_cattura_prnu(
    raw, attestazione, riferimenti, decodifica=decodifica_mosaico_raw,
    soglia=soglia_calibrata, schema_bayer=schema_bayer,
)
```

Il decoder va configurato per la fotocamera e deve restituire il mosaico
lineare in `[0, 1]` prima del demosaicing, con la stessa area, orientamento
e origine della griglia usati in calibrazione. Tutti e quattro i punteggi
devono raggiungere la soglia. `punteggi_prnu_bayer` restituisce i valori
individuali per la calibrazione. La modalità a impronta singola resta
disponibile per i certificati già emessi con quel riferimento.

Per ottenere gli esiti distinti della firma, della struttura Bayer e del
PRNU, usare `registro.verifica_cattura_bayer`. Il decoder restituisce un
`MosaicoBayer` con pixel e geometria letta dal RAW. Il verificatore fornisce
la `GeometriaBayer` di calibrazione con schema, dimensioni in righe e
colonne e origine sul sensore. Un esito `None` indica un controllo
non eseguito.

### Analisi di un JPEG senza RAW

Il nodo può verificare una credenziale C2PA incorporata prima di consultare
il catalogo PRNU. Per attivare il controllo, installare `c2pa-python==0.39.0`
e passare a `analizza_jpeg` il contenuto di un file PEM con le radici
fidate scelte dal nodo, tramite `radici_c2pa_pem`. Il verificatore controlla
firma, catena del firmatario e corrispondenza con il JPEG ricevuto.

Se il manifesto verificato dichiara che il JPEG è stato creato con IA
generativa, l'esito è `generata_ia`. Negli altri casi l'analisi prosegue
con il catalogo PRNU. Il risultato riporta anche lo stato della
credenziale (`verificata`, `assente` o `non_verificata`) quando il controllo
è attivo. Un manifesto verificato senza una dichiarazione di generazione
IA lascia aperta la questione dell'origine fisica. La verifica usa i
manifesti incorporati e i dati di revoca inclusi nella credenziale.

Il nodo può ricevere anche un JPEG isolato. In questo caso confronta il
residuo dell'immagine con i riferimenti JPEG calibrati per i sensori del
proprio catalogo. Il mittente presenta solo il JPEG. Il catalogo è
configurato dal nodo e contiene le prove d'iscrizione, gli ID XRPL, le
impronte e le soglie.

L'autorità stima il riferimento con `stima_prnu_jpeg` a partire da JPEG
originali uniformi, acquisiti nella stessa modalità e con la stessa geometria.
Inserisce `impronta_prnu_jpeg(riferimento)` come `prnu_jpeg_sha256` sia nel
messaggio firmato sia nel certificato prima di iscrivere il dispositivo.
Il riferimento JPEG è distinto dal riferimento RAW Bayer.

```python
from protocollo.jpeg import RiferimentoJPEG, analizza_jpeg

catalogo = [RiferimentoJPEG(prova_iscrizione, tx_id, riferimento_jpeg, soglia_jpeg)]

def valuta_jpeg(dati):
    return analizza_jpeg(dati, registro_pubblico, catalogo,
                        conto_pubblicatore_xrpl=conto_pubblicatore)

esito = valuta_jpeg(jpeg)
```

Passando `analisi_jpeg=valuta_jpeg` a `server_validatore`, si abilita
`POST /analisi-jpeg` con i byte del JPEG come corpo. L'esito include i
punteggi dei riferimenti valutabili. Può essere `compatibile` con un
sensore del catalogo, `ambiguo` tra più sensori, `nessuna_corrispondenza`
tra i riferimenti confrontati oppure `non_valutabile` in assenza di
riferimenti utilizzabili. Le soglie vanno misurate su JPEG reali.
Il confronto richiede raster allineati e della stessa dimensione. La
compressione o il ridimensionamento possono ridurre il punteggio.
L'esito è forense e la prova di derivazione continua a usare il RAW firmato.

### Quorum sull'origine IA di un JPEG isolato

Il nodo può eseguire localmente **Community Forensics ViT-S/16 224** (Park
e Owens, CVPR 2025). Installare `python3 -m pip install -r requirements-ia.txt`
e scaricare [i pesi MIT degli autori](https://huggingface.co/OwensLab/commfor-model-224/blob/26afc31e6b40c312c3fd42c05a758be62446215b/model.safetensors).
Il caricatore controlla il digest SHA-256 prima di leggere il checkpoint.
Il JPEG viene decodificato in RGB, ridimensionato, ritagliato al centro e
normalizzato come nella procedura di valutazione degli autori.

```python
from protocollo.analisi_ia import CommunityForensics224, QuorumIA
from protocollo.rete_origine import raccogli_voti_ia

quorum_ia = QuorumIA(quorum_foto, soglia_ia=soglia_calibrata)
rilevatore_ia = CommunityForensics224("model.safetensors")
# Passare quorum_ia=quorum_ia e rilevatore_ia=rilevatore_ia a server_validatore.
# Gli URL dei nodi per questa funzione terminano in /voti-ia.
voti = raccogli_voti_ia(jpeg, quorum_ia, url_validatori_ia)
esito = quorum_ia.verifica(jpeg, voti)
```

Ogni voto lega hash del JPEG, versione e digest del modello, soglia,
punteggio ed esito. `raccogli_voti_ia` cerca il numero richiesto di firme
distinte per lo stesso esito. La verifica pubblica restituisce
`probabile_ia`, `inconcludente` oppure `None` se manca un quorum valido.
Il punteggio del modello non è una probabilità calibrata per il nostro
catalogo. Impostare la soglia su JPEG reali e sintetici, includendo immagini
ricompresse e generatori diversi da quelli usati per la calibrazione.
Il quorum attesta l'esito statistico. Il controllo dell'origine fotografica
con RAW, firme e XRPL segue il percorso dedicato.

### Quorum per la provenienza della foto

`QuorumOrigine` riceve un comitato configurato separatamente da quello
d'iscrizione. Il verificatore fissa il decoder, la geometria attesa, la
soglia PRNU, una pipeline deterministica e il conto XRPL di pubblicazione
autorizzato, e distribuisce ai validatori l'hash della politica. Ogni
validatore verifica le firme della prova d'iscrizione e, tramite il proprio
nodo XRPL configurato, richiede una transazione validata e riuscita del conto
autorizzato con il digest di quella stessa prova. Poi controlla il RAW e la
foto finale. Il voto lega anche la prova d'iscrizione e l'ID della transazione.

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

La verifica del quorum copre un singolo RAW attestato. Il modulo
`rumore_fotonico` confronta separatamente la relazione tra luce media e
varianza temporale a partire da almeno tre coppie di RAW lineari a
esposizioni diverse, con luce uniforme, guadagno fisso e senza clipping.
Per includerlo nella decisione su una foto serve una serie di acquisizioni
attestate e legate a quella foto.

#### Validatori su processi o macchine distinti

Ogni nodo carica localmente la propria chiave di voto e la configurazione
pubblica del quorum, delle autorità e del comitato d'iscrizione. Carica anche
il decoder, la pipeline approvata e il riferimento PRNU. Chi carica la foto
invia il RAW, il file finale, l'attestazione di cattura, la prova pubblica
d'iscrizione e l'ID della sua transazione XRPL. Ogni nodo verifica
autonomamente la prova e il suo ancoraggio, poi rifà i controlli di Bayer,
PRNU e riproduzione della foto prima di firmare.

```python
from protocollo.rete_origine import (
    PacchettoOrigine, raccogli_approvazioni, server_validatore, verifica_prova_distribuita,
)

# Su ciascun nodo, con la rispettiva chiave privata di voto.
with server_validatore(
    ("127.0.0.1", porta), registro_pubblico, quorum,
    chiave_validatore=chiave_pubblica_del_nodo, firma=firmatario_del_nodo,
    riferimenti=riferimenti,
) as nodo:
    nodo.serve_forever()

# In un altro processo, con configurazione e chiavi pubbliche.
pacchetto = PacchettoOrigine(raw, foto_finale, attestazione, prova_iscrizione, tx_id)
voti = raccogli_approvazioni(pacchetto, registro_pubblico, quorum, url_approvazioni)
origine_approvata = verifica_prova_distribuita(pacchetto, registro_pubblico, quorum, voti)
```

Gli URL terminano in `/approvazioni`. Il raccoglitore interroga i nodi in
parallelo e conta solo le firme valide di membri distinti. Chiunque abbia il
pacchetto, i voti e la configurazione pubblica può verificare l'esito
senza contattare i validatori. La verifica completa consulta XRPL in modo
indipendente. Per macchine distinte esporre i nodi su una rete fidata o
tramite un proxy HTTPS.

## Ancoraggio su XRP Ledger

Il servizio prepara una transazione `AccountSet` con l'impronta SHA-256
dell'intera prova di iscrizione. L'impronta copre il certificato, la challenge,
la risposta firmata, la configurazione del comitato e le approvazioni. Il chiamante conserva la prova fuori catena insieme all’identificativo della
transazione. Il wallet completa, firma e invia la transazione dal conto di
pubblicazione, pagando la commissione di rete.

```python
from protocollo import prepara_ancoraggio, verifica_ancoraggio

transazione = prepara_ancoraggio(prova, conto_pubblicatore)
# Il verificatore esterno riceve la prova e l'identificativo della transazione.
iscrizione_verificata = verificatore_esterno.verifica_iscrizione(prova)
ancorato = verifica_ancoraggio(prova, tx_id, conto_pubblicatore)
provenienza_verificata = provenienza_verificata and iscrizione_verificata and ancorato
```

La verifica interroga XRPL Testnet per impostazione predefinita e richiede
una transazione riuscita in un ledger validato. Il verificatore configura
le autorità, il comitato, la soglia, il nodo RPC e il conto di pubblicazione.
Verifica sia le firme della prova sia la corrispondenza con l'impronta
pubblicata su XRPL. La pubblicazione via rete della prova e l'invio dal wallet
sono passaggi esterni al registro Python.

Per verificare la cattura fisica serve integrare un modulo che firmi durante
l'acquisizione. Per l'elaborazione, il verificatore deve fornire una pipeline
deterministica con operazioni, parametri e versioni fissati. Il confronto prova
che la pipeline autorizzata riproduce il file ricevuto. La storia effettiva
dell'elaborazione richiederebbe un'attestazione del processo di esecuzione.
La verifica con una soglia di tolleranza per le modifiche è in pausa come
funzionalità distintiva del progetto.

[Backend CROSS di riferimento](https://github.com/CROSS-signature/CROSS-implementation).
