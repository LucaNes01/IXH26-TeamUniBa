# Controllo preliminare di due iPhone 16

Il proprietario ha confermato che `IMG_3777.DNG` (A) e `IMG_6529.DNG` (B) provengono da due iPhone 16 fisicamente distinti. Entrambi i DNG dichiarano la fotocamera posteriore e contengono un mosaico Bayer BGGR. Il lettore dello script dell'esperimento, con rawpy 0.28.0, ha decodificato entrambi i mosaici visibili a 4032 × 3024. LibRaw riporta livello del nero 528 e livello del bianco 4095 per entrambi.

Per ciascuna posizione Bayer è stata calcolata la correlazione di Pearson fra i residui gaussiani dei due scatti (sigma 1), sulle coordinate in cui entrambi i valori normalizzati sono fra 0,05 e 0,95. Le coordinate sono quelle del sensore, senza rotazione o allineamento della scena.

| Piano BGGR | Pixel validi in entrambi | Percentuale del piano | Correlazione |
| --- | ---: | ---: | ---: |
| B alto a sinistra | 238.983 | 7,8% | −0,0019 |
| G alto a destra | 916.370 | 30,1% | 0,0140 |
| G basso a sinistra | 915.564 | 30,0% | 0,0130 |
| R basso a destra | 597.540 | 19,6% | 0,0317 |

La coppia fornisce un confronto fra corpi diversi privo di un confronto di controllo sullo stesso corpo. Le correlazioni descrivono i residui di questi due scatti. Per misurare la capacità di attribuzione del PRNU occorrono impronte da scatti uniformi per ciascun corpo, scatti separati per fissare la soglia e scene cieche mai usate prima. Per la calibrazione conviene aumentare l'illuminazione uniforme evitando la saturazione, dato che in questa coppia molti pixel sono sotto la soglia di intensità.

## Secondo invio · 19 scatti

I DNG da `IMG_3778.DNG` a `IMG_3797.DNG` (3780 assente) sono stati attribuiti provvisoriamente al telefono A in base alla numerazione degli allegati. Tutti sono stati decodificati a 4032 × 3024, BGGR, e i mosaici normalizzati risultano distinti. La percentuale mediana di pixel utilizzabili è 7,2% nel blu, 52,2% nei due verdi e 41,9% nel rosso.

Il digest dell'impronta costruita sui 19 scatti è `f36cb845b32a1c4e503021b49ce70b1178e4f03a59fc7a2356fdc479b999c4e9`. Per il controllo interno è stata costruita un'altra impronta usando solo i primi 16 scatti. Gli ultimi tre hanno dato questi risultati.

| DNG | B | G alto | G basso | R | Minimo |
| --- | ---: | ---: | ---: | ---: | ---: |
| IMG_3795.DNG | 0,186 | 0,150 | 0,150 | 0,242 | 0,150 |
| IMG_3796.DNG | 0,119 | 0,124 | 0,076 | 0,134 | 0,076 |
| IMG_3797.DNG | 0,101 | 0,045 | 0,051 | 0,142 | 0,045 |

Questa verifica usa scatti della stessa serie, con possibile contributo della scena condivisa. I due DNG iniziali erano assenti dalla cartella Download al momento di questo passaggio, quindi il confronto con l'impronta A resta da eseguire quando saranno disponibili. Servono anche gli scatti uniformi di B e scene separate per calibrare e misurare i tassi di errore.
