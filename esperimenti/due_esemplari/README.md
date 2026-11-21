# Due esemplari dello stesso modello

L'esperimento misura quanto il confronto PRNU Bayer del progetto distingue due corpi macchina A e B. Per ciascuno scatto si provano entrambe le impronte. Un riferimento è accettato se tutti i suoi quattro punteggi raggiungono la soglia. Possono passare entrambi o nessuno.

## Acquisizione

Annotare marca, modello, due identificativi fisici distinti, ISO, modalità RAW, geometria e origine dell'area visibile. Usare la stessa modalità e disabilitare lo sviluppo automatico. Lo script assume che queste condizioni e l'identità dei due corpi siano state verificate da chi raccoglie i dati.

1. **Impronte.** Per un primo esperimento, raccogliere 20 RAW uniformi per corpo a ISO fisso e a più esposizioni, evitando ombre profonde e saturazione. Riempire l'inquadratura con un diffusore illuminato uniformemente.
2. **Soglia.** Riprendere le stesse scene con A e B e destinare, per esempio, 10 scatti per corpo alla scelta della soglia. Distribuire le condizioni di luce tra i due corpi.
3. **Prova cieca.** Fotografare altre scene con entrambi i corpi, includendo luce debole e superfici ricche di dettagli. Per una prova pilota partire da 20 scatti per corpo. Riservare scene e raffiche intere a una sola fase. Assegnare nomi anonimi e far conservare la corrispondenza a chi ha acquisito le immagini.

## Input ed esecuzione

Nella cartella dati creare le sottocartelle indicate qui sotto. Inserire solo immagini nelle cinque cartelle che contengono scatti.

```text
dati/
  uniformi/A/   uniformi/B/
  soglia/A/     soglia/B/
  cieco/
  verita.json
```

Il file di verità associa ogni nome cieco alla fotocamera, per esempio `{"001.dng": "B", "002.dng": "A"}`. Il programma lo apre dopo aver fissato la soglia e calcolato i punteggi ciechi.

Dalla radice del repository, con le dipendenze PRNU installate, eseguire:

```sh
python3 -m pip install -r requirements-prnu.txt
python3 -m pip install rawpy
python3 -m esperimenti.due_esemplari.confronto dati --schema RGGB > rapporto.json
```

Scegliere lo schema effettivo all'origine del mosaico visibile. Il lettore usa LibRaw tramite rawpy, sottrae il livello del nero per canale e normalizza al livello del bianco prima del confronto. Usare RAW Bayer lineari leggibili da LibRaw. In alternativa si possono fornire mosaici NumPy `.npy` bidimensionali già normalizzati in [0, 1], tutti decodificati con la stessa origine e lo stesso schema. Per questo ingresso bastano le dipendenze PRNU.

## Lettura del risultato

La soglia minimizza la somma di false accettazioni e falsi rifiuti sugli scatti di calibrazione valutabili. A parità di errori prevale la soglia con meno false accettazioni. Il punteggio di un riferimento è il minimo delle quattro correlazioni, in ordine alto-sinistra, alto-destra, basso-sinistra, basso-destra nel blocco Bayer.

Il JSON contiene i quattro punteggi contro A e B e gli esemplari accettati per ogni scatto. Dividere ciascun conteggio di errore per il numero di scatti ciechi valutabili: ciascuno genera una prova con il corpo corretto e una con l'altro. Riportare separatamente i non valutabili per segnale insufficiente, oltre ai casi ambigui in cui entrambi passano. Per esempio, zero errori su venti confronti descrive quei venti confronti. Conservare dati originali, soglia e rapporto per la riproducibilità.
