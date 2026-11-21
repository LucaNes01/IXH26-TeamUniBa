# Controllo dei due DNG dello Xiaomi 15T Pro

| File | Ora nei metadati | ISO | Tempo |
| --- | --- | ---: | ---: |
| IMG_20261121_093305.dng | 09:33:05 | 725 | circa 1/50 s |
| IMG_20261121_093307.dng | 09:33:07 | 725 | circa 1/50 s |

Entrambi i file dichiarano Xiaomi 15T Pro e hanno un mosaico **BGGR** non compresso, con un campione per fotosito memorizzato a 16 bit. Il livello di bianco dichiarato è 16.383. Il raster misura 4096 × 3072 e il ritaglio predefinito misura 4080 × 3056, con origine (8, 8) in coordinate colonna e riga. I due file hanno hash SHA-256 diversi. Nei metadati controllati manca un seriale che permetta di attribuirli a due telefoni distinti.

Per questo controllo i campioni sono stati letti direttamente dal blocco TIFF del DNG, senza demosaicizzazione o rotazione. Sul ritaglio predefinito è stato sottratto il livello del nero per ciascuna posizione del blocco Bayer, poi i valori sono stati normalizzati al bianco. I residui sono quelli del filtro gaussiano del progetto con sigma 1. La correlazione di Pearson è stata calcolata sulle posizioni valide in entrambi gli scatti, con valori normalizzati tra 0,05 e 0,95.

| Posizione BGGR | Pixel validi in entrambi | Correlazione dei residui |
| --- | ---: | ---: |
| B, alto a sinistra | 40,8% | 0,0471 |
| G, alto a destra | 65,4% | 0,0428 |
| G, basso a sinistra | 65,3% | 0,0445 |
| R, basso a destra | 55,9% | 0,0492 |

La coppia conferma la disponibilità di campioni Bayer per il confronto. Le correlazioni sono descrittive e possono includere dettagli della scena. Per misurare il riconoscimento dei due esemplari servono riferimenti costruiti da scatti uniformi per ciascun telefono, un gruppo per calibrare la soglia e scatti ciechi separati. La lettura tramite il percorso rawpy dello script dell'esperimento resta da verificare.
