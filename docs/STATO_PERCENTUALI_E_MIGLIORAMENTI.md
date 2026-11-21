# Team Bari — Percentuali e piano completo dei miglioramenti

**Aggiornato al 17 novembre 2026. Documento di confronto per il team.**

**Nota del 20 novembre 2026.** Le percentuali citate qui si riferiscono alla
revisione del 17 novembre. Il [README](../README.md) descrive il codice corrente
di verifica della cattura e della derivazione del file finale.

Questo documento raccoglie le percentuali discusse, tutti i sette temi sollevati
da Niccolò e gli altri limiti emersi nel progetto. Per ogni area propone due
soluzioni, spiegando il meccanismo, le condizioni necessarie e un esempio.
Le alternative sono proposte: non indicano funzionalità già implementate.

## 1. Come leggere le percentuali

**Stima complessiva discussa: circa 50%, rispetto al precedente 40%.**

Sono valutazioni qualitative del completamento delle garanzie, non probabilità
di sicurezza, misure scientifiche o risultati di un audit. Il 50% complessivo è
un giudizio orientativo sul progetto; non deriva da pesi o criteri quantitativi
formalizzati. Non significa che metà delle operazioni sia sicura o che basti
metà del lavoro per una soluzione pronta per la gara.

La colonna “Prima” riprende la valutazione precedente alle modifiche di questa
chat; “Oggi” riprende quella discussa il 17 novembre. Gli zeri correggono il
credito attribuito al vecchio toolkit, poi eliminato: nel protocollo corrente
quelle funzionalità non sono presenti. Non descrivono nuove vulnerabilità
introdotte dalle pulizie.

| Garanzia | Prima | Oggi | Motivazione e principali sezioni di lavoro |
| --- | ---: | ---: | --- |
| Modello di fiducia e regole | 55% | **65%** | Ruoli distinti, parametri espliciti; restano governance, chiusura e ipotesi operative. M01, M10, M11. |
| Registrazione e autorizzazioni | 45% | **45%** | Prova di possesso della chiave; nessuna unicità personale o abilitazione applicativa. M02. |
| Autenticità delle richieste | 40% | **85%** | CROSS ufficiale e ricevute firmate; restano gestione delle chiavi e verifiche di integrazione. M03–M05. |
| Riservatezza verso il server | 15% | **15%** | Le private degli utenti restano ai client; manca il protocollo sui segreti applicativi. M14–M16. |
| Protezione dei dati archiviati e trasmessi | 20% | **0%** | Mancano un servizio di rete protetto e un archivio persistente protetto. M06, M08, M13. |
| Controllo distribuito del segreto | 20% | **0%** | Non implementato nel flusso corrente. M15. |
| Validità degli input e delle modifiche | 25% | **25%** | Controllo esplicito, ma la demo verifica soltanto il formato del commitment. M17. |
| Quorum sulla stessa operazione | 75% | **85%** | Firme legate a richiesta e configurazione; soglie parametrizzate e testate. M01, M09, M12. |
| Correttezza e completezza del risultato | 30% | **35%** | Ricevute migliori; mancano insieme completo degli input e calcolo finale verificabile. M07, M09, M11, M18. |
| Replay, sessioni e scadenze | 70% | **80%** | Quorum temporali e separazione delle sessioni; mancano ripristino e chiusura definitiva. M06, M10–M12. |
| Assenze e comportamenti malevoli | 40% | **50%** | Gestiti quorum incompleti e prove tardive; manca l'operatività su nodi distinti. M05, M09, M11, M20. |
| Ancoraggio blockchain effettivo | 20% | **0%** | Assente; non necessario alla soluzione temporale scelta. Da valutare solo rispetto alla traccia. M22. |
| Validazione avversariale | 45% | **70%** | 36 test superati, inclusi vettori ufficiali; mancano prove di rete, crash e revisione indipendente. M21. |

## 2. Cosa esiste effettivamente

- Configurazione immutabile della sessione e distinzione fra utenti e validatori.
- Registrazione pseudonima con sfida firmata e chiavi generate dai client.
- Contributi e attestazioni legati alla configurazione e alla specifica operazione.
- CROSS ufficiale di riferimento v2.2, richiamato da Python; sorgenti upstream fissati.
- Ricevute firmate dal coordinatore per le operazioni accettate.
- Ricevute temporali firmate dai validatori, distinte dalle approvazioni.
- Accettazione delle prove tempestive anche se consegnate dopo al coordinatore.
- Osservazione della scadenza mediante firme dei validatori e stato `IN_ATTESA_DI_PROVE`.
- Demo parametrica e **36 test superati**, rieseguiti per preparare questo documento.

Restano oggetti locali nello stesso processo, con stato in memoria. Non abbiamo
una rete decentralizzata già funzionante, persistenza, consenso BFT o calcolo
applicativo completo. Una firma autentica non dimostra la correttezza del dato
firmato, la precisione dell'orologio o la disponibilità futura dei dati.

## 3. Parametri generali e priorità

| Simbolo | Significato |
| --- | --- |
| N | Numero dei validatori autorizzati, ricavato dalle chiavi della configurazione. |
| Q | Soglia di approvazione del contenuto. |
| T | Soglia delle ricevute temporali. |
| F | Numero massimo di validatori disonesti ipotizzato nel modello di fiducia. |
| ε | Tolleranza massima assunta per gli orologi onesti. |

Non imponiamo un numero fisso di validatori. Occorre `1 <= Q <= N` e
`1 <= T <= N`; Q e T possono essere diversi. Per la sola garanzia temporale
serve `T > F`; per raccogliere le ricevute anche se F nodi non collaborano serve
`T <= N - F`, assumendo gli altri disponibili. Queste condizioni non bastano
a implementare consenso o a garantire la correttezza applicativa.

**P1** significa fondazione da affrontare subito; **P2** significa completamento
del protocollo e dell'operatività; **P3** significa lavoro dipendente dalla traccia
o dai requisiti di privacy. La priorità non misura la difficoltà né attribuisce
percentuali aggiuntive.

## 4. Copertura dei sette punti di Niccolò

| Punto originale | Situazione attuale | Dove viene approfondito |
| --- | --- | --- |
| Ridurre la fiducia nel coordinatore | Ricevute implementate; comunicazione e sincronizzazione indipendenti assenti. | M07, M09, M11, M20. |
| Scadenza e orologio | Scelta una soluzione con ricevute dei validatori; niente XRPL. Mancano nodi reali e gestione operativa degli orologi. | M10, M11. |
| Log append-only | Non implementato. Una sola catena locale non basta contro riscrittura e omissioni. | M06, M07. |
| Separazione dei domini | Già presente; va preservata nelle estensioni. | M04. |
| Revoca o rotazione dei validatori | Non implementata durante la sessione. | M05, M01. |
| Metadati di rete: IP e tempi | Non implementati trasporto o protezioni specifiche dei metadati. | M08, M19. |
| Reveal e mancata collaborazione | Fase di reveal non ancora definita nel protocollo corrente. | M14–M16, M18. |

## M01 — Modello di fiducia, configurazione e scelta delle soglie

**Stato e priorità: parziale, P1.** Oggi il coordinatore propone la configurazione
iniziale. Una soglia nell'intervallo corretto può comunque essere inadeguata.

**Soluzione A — Configurazione approvata esplicitamente prima della sessione.**
I partecipanti verificano elenco dei validatori, impronta, Q, T, scadenza e regola;
il comitato firma l'approvazione del manifest iniziale secondo una procedura
concordata fuori dalla sessione. Funziona perché il coordinatore non può presentare
una configurazione diversa senza che l'impronta cambi. Rimane necessario un punto
iniziale di fiducia sulle chiavi e sull'indipendenza dei validatori.

**Soluzione B — Politica di configurazione verificata dai nodi.**
Definiamo criteri espliciti rispetto a F e ai guasti tollerati, più una procedura
per approvare soltanto le configurazioni delle sessioni successive. Funziona
perché i nodi rifiutano soglie o sostituzioni fuori politica. Se possono esistere
proposte concorrenti, serve anche un ordine condiviso: le firme da sole non lo creano.

**Esempio.** In una sessione S, N, Q e T sono fissati. Il coordinatore vuole
ridurre Q perché alcuni nodi sono assenti: entrambe le soluzioni impediscono il
cambio in S. In A si negozia una nuova sessione; in B la nuova configurazione
deve inoltre superare i controlli della politica e l'autorizzazione prevista.

## M02 — Registrazione, diritti e account multipli

**Stato e priorità: registrazione presente, diritti applicativi da definire, P3.**
Una chiave identifica un account, non una persona.

**Soluzione A — Credenziale di abilitazione emessa da un soggetto autorizzato.**
Un ente controlla il requisito applicativo e firma un titolo valido per quella
sessione. Il protocollo registra l'utilizzo del titolo. Funziona se l'emittente
impedisce abilitazioni multiple indebite; la responsabilità dell'ammissione resta sua.

**Soluzione B — Credenziale con prova di possesso non collegabile e nullifier.**
L'utente dimostra di avere un titolo valido senza pubblicarlo direttamente e
produce un identificatore di spesa unico per quella sessione. Funziona contro
il riuso del medesimo titolo e può ridurre la collegabilità. Non impedisce a
un'emissione difettosa di attribuire due titoli alla stessa persona; richiede
un sistema di credenziali e prove già studiato, non una ZKP inventata.

**Esempio.** Alice apre molti account ma possiede un solo titolo elettorale.
In A il secondo uso dello stesso titolo viene rifiutato; in B viene rifiutato
il secondo nullifier uguale, senza dover pubblicare l'identità di Alice.

## M03 — Affidabilità dell'integrazione CROSS ufficiale

**Stato e priorità: backend ufficiale integrato, consolidamento P1/P2.**
Non serve riscrivere CROSS. Serve mantenere riproducibile e verificabile il
collegamento al codice degli autori, già fissato nel repository.

**Soluzione A — Conservare il riferimento upstream con verifiche automatiche.**
Controlliamo manifest, versione, parametri, dimensioni e vettori ufficiali a ogni
modifica del binding o del compilatore. Funziona perché intercetta cambi di formato
e divergenze dai risultati attesi. I vettori non equivalgono a un audit di sicurezza.

**Soluzione B — Usare una distribuzione mantenuta con wrapper supportato.**
Se disponibile per versione, piattaforma e parametri richiesti, adottiamo una
libreria mantenuta che includa CROSS, fissandone versione e provenienza e
verificandola con gli stessi vettori. Funziona riducendo il codice di integrazione
che dobbiamo mantenere; non rende automaticamente sicura qualsiasi distribuzione.

**Esempio.** Una nuova build produce una firma di formato diverso. A blocca
l'aggiornamento quando i vettori divergono; B impone una migrazione esplicita del
backend e della suite nella configurazione, senza accettare silenziosamente vecchie firme.

Fonte del backend corrente: [implementazione degli autori CROSS](https://github.com/CROSS-signature/CROSS-implementation).

## M04 — Separazione dei domini, serializzazione e versioni

**Stato e priorità: già implementata, requisito permanente P1.** È il quarto
punto di Niccolò. I messaggi includono protocollo, azione e impronta della configurazione.

**Soluzione A — Estendere il formato canonico attuale con schemi rigorosi.**
Ogni operazione ha campi ammessi, tipi, limiti e versione precisi. Il verificatore
ricostruisce i byte canonici prima di verificare la firma. Funziona impedendo
che la stessa firma autorizzi azioni diverse o rappresentazioni ambigue.

**Soluzione B — Adottare una codifica deterministica standard.**
Una libreria mantenuta gestisce la rappresentazione canonica, con etichette di
dominio e versione definite dal nostro protocollo. Funziona migliorando
l'interoperabilità tra linguaggi; serve comunque uno schema applicativo rigoroso.

**Esempio.** Una firma su `PUBBLICA` viene ripresentata come `ATTESTA`. A e B
producono byte diversi per le due azioni e la verifica fallisce. Una revoca
futura deve avere a sua volta un dominio distinto dalle approvazioni.

## M05 — Custodia, rotazione e revoca delle chiavi

**Stato e priorità: non implementata operativamente, P2.** Comprende il quinto
punto di Niccolò e le chiavi di utenti, coordinatore e validatori.

**Soluzione A — Custodia protetta e sostituzione tra sessioni.**
Conserviamo le private in un archivio cifrato o in un servizio di firma compatibile
con CROSS, con accessi limitati e recupero controllato. In emergenza interrompiamo
la sessione secondo una procedura esplicita e ne avviamo una nuova. Funziona
mantenendo immutabile la vecchia configurazione; occorre decidere cosa recuperare
e come trattare i risultati già definitivi. Non tutti i dispositivi hardware supportano CROSS.

**Soluzione B — Revoca certificata con epoche e regole di transizione.**
Un quorum di governance autorizza la sostituzione e ne fissa il punto di efficacia,
con ordine condiviso degli eventi. Funziona distinguendo le autorizzazioni prima
e dopo il cambio. Non basta cancellare una chiave dalla lista: bisogna specificare
soglie, firme pregresse e conseguenze di una compromissione retroattiva.

**Esempio.** V perde il controllo della propria privata. A blocca nuove operazioni
e ricostituisce il comitato in S2. B attiva una nuova epoca e verifica ogni firma
rispetto a quell'epoca. In entrambi i casi un semplice timestamp dichiarato da V
non prova che una sua firma preceda il furto.

## M06 — Persistenza, atomicità e ripristino

**Stato e priorità: assente, P1; primo intervento consigliato.** Serve sia al
coordinatore sia ai nodi temporali, che oggi perdono lo stato al riavvio.

**Soluzione A — SQLite con transazioni e vincoli.**
Una transazione salva richiesta, nonce consumato, esito, ricevuta ed evento.
La risposta positiva parte dopo il commit. Funziona perché non lascia accettazioni
parziali e permette il ripristino dello stesso stato. La durabilità dipende anche
dalle impostazioni di sincronizzazione e dal sistema di archiviazione: WAL da
solo non significa resistenza a ogni perdita di alimentazione.

**Soluzione B — Registro durevole degli eventi e snapshot verificati.**
Prima della conferma salviamo un evento completo; lo stato si ricostruisce
riproducendo gli eventi dopo uno snapshot. Funziona se formato, ordine e regole
di replay sono deterministici e il salvataggio durevole precede la risposta.
Richiede gestire record incompleti e versioni del formato.

**Esempio.** Il processo si interrompe mentre accetta C. A riparte con tutta
la transazione presente oppure assente. B riproduce l'evento completo, se
confermato durevolmente. Nessuno dei due deve trovare C accettato e il suo nonce libero.

Riferimenti: [commit atomico SQLite](https://www.sqlite.org/atomiccommit.html),
[durabilità e WAL](https://www.sqlite.org/wal.html).

## M07 — Registro verificabile e protezione dalle omissioni

**Stato e priorità: assente, P1 dopo M06.** È il terzo punto di Niccolò.

**Soluzione A — Catena di hash con checkpoint firmati e distribuiti.**
Ogni evento contiene progressivo e hash del precedente. I partecipanti conservano
checkpoint con lunghezza e hash di testa. Funziona perché una riscrittura non
coincide più con il checkpoint già conservato. Senza copie esterne il coordinatore
può rigenerare la catena o mostrarne un prefisso; la struttura locale non basta.

**Soluzione B — Log Merkle con prove di inclusione e consistenza.**
Il log produce radici firmate, prove che un evento sia incluso e prove che una
versione estenda quella precedente. I lettori confrontano le radici ricevute.
Funziona consentendo verifiche compatte anche su registri grandi; resta necessario
confrontare le viste e conservare o replicare i dati, non soltanto gli hash.

**Esempio.** Alice conserva una ricevuta per C e il checkpoint che lo include.
Il server pubblica poi un registro senza C. A rileva l'incompatibilità della
catena; B rileva la mancata consistenza rispetto alla radice precedente.
L'attacco diventa documentabile, ma il dato cancellato si recupera solo se ne esiste una copia.

Riferimento per prove di inclusione e consistenza: [Certificate Transparency, RFC 9162](https://www.rfc-editor.org/rfc/rfc9162.html).

## M08 — Trasporto di rete, API e protezione dei messaggi

**Stato e priorità: assente, P2.** Le chiamate Python non sono ancora un servizio.

**Soluzione A — API HTTPS con TLS e firme applicative.**
Usiamo una libreria/server mantenuti, validazione degli input e limiti espliciti.
TLS protegge il canale; CROSS mantiene l'autenticità verificabile dei messaggi
anche fuori dalla connessione. Le risposte di accettazione includono direttamente
la ricevuta, dopo il commit, invece di richiedere un secondo recupero.

**Soluzione B — Trasporto fra servizi su canali autenticati, con coda durevole.**
Nodi e coordinatore scambiano buste firmate tramite connessioni autenticate;
una coda conserva i messaggi finché il destinatario li conferma. Funziona contro
interruzioni temporanee e identifica i servizi autorizzati. La coda può duplicare
i messaggi: il destinatario deve essere idempotente, e il suo gestore può vederne
il contenuto se non aggiungiamo cifratura del payload.

**Esempio.** La connessione cade dopo il salvataggio di C. In A il retry restituisce
la ricevuta già salvata; in B la coda riconsegna C e il destinatario riconosce
la duplicazione. C non deve essere conteggiato due volte.

TLS protegge confidenzialità e integrità fra gli estremi del canale, non nasconde
i dati all'estremo server: [TLS 1.3](https://www.rfc-editor.org/rfc/rfc8446.html).

## M09 — Riduzione della fiducia nel coordinatore e sincronizzazione

**Stato e priorità: ricevute presenti, rete indipendente assente, P2.** Completa
il primo punto di Niccolò.

**Soluzione A — Invio diretto a più nodi e recupero per identificatore.**
L'utente conserva la richiesta e la invia ai validatori, che ne salvano il
contenuto insieme alla ricevuta. Un client può recuperare dati e firme anche
quando il coordinatore li omette. Funziona se le copie sono effettivamente
raggiungibili; una firma su un hash non è una copia del contenuto.

**Soluzione B — Repliche che confrontano periodicamente le proprie viste.**
I nodi scambiano checkpoint, richieste mancanti e attestazioni. Funziona
individuando omissioni e ricostruendo una vista più completa da più fonti.
Il confronto non stabilisce da solo un ordine definitivo: eventi incompatibili
richiedono regole esplicite o un protocollo di consenso adeguato.

**Esempio.** Il coordinatore nasconde un'approvazione. In A il client la recupera
dal validatore che l'ha emessa. In B un'altra replica ne rileva l'assenza durante
la sincronizzazione. Le firme permettono di verificarla senza fidarsi del trasportatore.

## M10 — Scadenze e correttezza degli orologi

**Stato e priorità: meccanismo implementato localmente, operatività P2.** È il
secondo punto di Niccolò. La scelta corrente esclude XRPL per la gestione del tempo.

**Soluzione A — Consolidare i quorum temporali già implementati.**
Ogni nodo usa un orologio sincronizzato e monitorato con fonti indipendenti;
può sospendere l'emissione se non riesce a rispettare ε. Conserviamo durevolmente
ricevute e memoria del tempo, e monitoriamo gli scostamenti. Funziona sotto le
ipotesi `T > F` e di errore entro ε per gli onesti. NTS può autenticare la
sincronizzazione NTP, ma non rende infallibile la fonte né elimina tutti gli effetti dei ritardi di rete.

**Soluzione B — Marca temporale esterna firmata.**
Come alternativa architetturale, un'autorità temporale riconosciuta marca l'hash
del dato o della ricevuta mediante un protocollo standard. Funziona come prova
di esistenza entro il tempo attestato, assumendo affidabile quell'autorità.
Marcare la sola richiesta non prova che i validatori l'abbiano ricevuta: per
quella proprietà bisogna marcare la loro ricevuta o mantenere il quorum temporale.

**Esempio.** Il termine è alle 15:00. A accetta T ricevute con timestamp più ε
strettamente precedente al termine, anche se il server le vede alle 15:01.
B permette a un verificatore di controllare il token dell'autorità temporale,
ma deve specificare se sta provando l'esistenza della richiesta o la sua ricezione.

Riferimenti: [NTS, RFC 8915](https://www.rfc-editor.org/rfc/rfc8915.html),
[marcatura temporale, RFC 3161](https://www.rfc-editor.org/rfc/rfc3161.html).

## M11 — Chiusura definitiva e prove ancora in transito

**Stato e priorità: aperto, P2 dopo persistenza e rete.** `IN_ATTESA_DI_PROVE`
è intenzionalmente non definitivo. Il semplice passaggio dell'ora non dimostra
che non arriverà una prova tempestiva.

**Soluzione A — Finestra di consegna e contestazione fissata in anticipo.**
Distinguiamo il termine di ricezione nei nodi dal termine di presentazione delle
prove al registro condiviso. Pubblichiamo un risultato provvisorio e permettiamo
contestazioni con ricevute verificabili. Funziona se assumiamo un limite ai ritardi
e almeno un canale disponibile per contestare. Cambia la regola corrente: anche
una prova tempestiva presentata oltre la finestra può essere esclusa. Va dichiarato prima.

**Soluzione B — Disseminazione affidabile e chiusura su un insieme condiviso.**
Prima della chiusura rendiamo disponibili ai nodi i certificati completi di
tempestività e i dati; il protocollo concorda poi l'insieme finale e ne firma
l'impronta. Funziona solo con regole di disponibilità, inclusione e consenso
esplicite. Un quorum che firma una lista senza verificarne la completezza non basta.
È una soluzione più impegnativa e richiede ridefinire cosa costituisce un'ammissione completa.

**Esempio.** La prova di Alice arriva al server alle 15:01. A la accetta se la
finestra pubblicata è ancora aperta. B la recupera dagli altri nodi prima di
concordare il risultato. Con ritardi arbitrari e dati non disponibili, non
possiamo promettere insieme chiusura entro un tempo fisso e recupero di ogni prova tardiva.

## M12 — Replay, idempotenza, concorrenza e rollback

**Stato e priorità: controlli in memoria presenti, completamento P1.**

**Soluzione A — Vincoli unici e operazioni atomiche nel database.**
Registriamo unicità di sessione/autore/nonce e di contributo/validatore, con
identificatori di richiesta stabili. Un retry identico restituisce il risultato
salvato; lo stesso nonce con contenuto diverso viene rifiutato. Funziona anche
con due richieste simultanee perché l'unicità è fatta rispettare dall'archivio.

**Soluzione B — Sequenze per autore e verifica dei checkpoint al ripristino.**
Oltre all'impronta della richiesta, ogni autore usa un contatore legato alla
sessione. I nodi persistono il massimo ammesso e, dopo un recupero da backup,
confrontano il proprio checkpoint con copie indipendenti. Funziona contro il
riuso di messaggi e rende rilevabile un rollback; un contatore salvato soltanto
nello stesso backup vecchio non protegge dal rollback. Occorre definire anche buchi e riordino.

**Esempio.** Due thread inviano lo stesso contributo, poi il servizio riparte da
un backup. A impedisce il doppio inserimento concorrente. B rileva che il backup
è precedente al checkpoint noto agli altri nodi e sospende l'ammissione finché recupera lo stato.

## M13 — Protezione dei dati archiviati e dei backup

**Stato e priorità: assente, P1/P2 secondo i dati conservati.** Integrità,
riservatezza e ripristino sono obiettivi distinti.

**Soluzione A — Cifratura dell'archivio e custodia separata della chiave.**
Usiamo un componente mantenuto per cifrare il database o il volume, con accessi
limitati e backup coerenti anch'essi protetti. Funziona contro il furto di dischi
o copie di backup senza la chiave. Non protegge necessariamente da un processo
server già compromesso e autorizzato a leggere i dati.

**Soluzione B — Cifrare soltanto i campi sensibili prima della scrittura.**
Un formato autenticato lega il ciphertext alla sessione e al tipo di record;
le chiavi stanno in un archivio separato. Funziona limitando ciò che una copia
del database rivela, ma lascia visibili campi e indici non cifrati. Se si usa
AES-GCM, la gestione delle chiavi e l'unicità del nonce per chiave sono obbligatorie.

**Esempio.** Viene copiata la directory dei backup. A rende illeggibile il backup
senza la chiave del volume/archivio. B lascia leggibili gli identificatori pubblici
ma protegge i payload sensibili. Nessuna delle due sostituisce ricevute e log verificabile.

Riferimento per la cifratura autenticata: [NIST SP 800-38D](https://csrc.nist.gov/pubs/sp/800/38/d/final).

## M14 — Riservatezza dei contenuti verso il coordinatore

**Stato e priorità: protocollo applicativo assente, P3.** Un hash opaco di 32
byte non dimostra da solo che un valore sia nascosto bene. Valori prevedibili
richiedono casualità appropriata in uno schema di commitment analizzato.

**Soluzione A — Cifratura sul client per i destinatari autorizzati.**
Il client cifra il contenuto con uno schema mantenuto; il coordinatore conserva
e inoltra soltanto ciphertext. Funziona perché il server non possiede la chiave
di apertura. Va deciso chi può leggere, come distribuire le chiavi e quali
metadati restano pubblici. Una chiave condivisa anche con il server non lo esclude.

**Soluzione B — Commitment con casualità segreta e prove della proprietà richiesta.**
L'utente pubblica un commitment di uno schema studiato e, se necessario, una
prova senza rivelare il valore. Funziona separando il vincolo sul dato dalla sua
apertura, a condizione che lo schema garantisca hiding e binding nel modello scelto.
Non è automaticamente un modo per calcolare qualsiasi risultato sui dati nascosti.

**Esempio.** Alice invia un'offerta economica. A la rende leggibile soltanto alla
commissione autorizzata. B permette di verificare che l'offerta rispetti un limite
senza pubblicarla, usando una prova specifica collegata al commitment.

## M15 — Controllo distribuito dei segreti

**Stato e priorità: assente, P3 se la traccia lo richiede.** Non va reintrodotto
il vecchio Shamir didattico come se bastasse a completare il protocollo.

**Soluzione A — Condivisione verificabile del segreto e quote cifrate.**
Un detentore divide il segreto con soglia K e permette di verificare la coerenza
delle quote mediante un protocollo studiato. Le quote sono consegnate cifrate e
autenticate. Funziona impedendo la ricostruzione da meno di K quote nel modello
previsto; K detentori collusi possono ricostruire. Il detentore iniziale conosce il segreto.

**Soluzione B — Generazione distribuita e operazioni crittografiche a soglia.**
Per una chiave di decifratura o firma, un protocollo DKG e uno schema a soglia
compatibile evitano di creare la privata completa su un singolo nodo. Funziona
distribuendo il potere di usare quella chiave. Non sostituisce automaticamente
la gestione di un qualsiasi segreto applicativo; richiede primitive e librerie
specifiche. La soglia sulle firme CROSS indipendenti attuale non è una firma CROSS a soglia.

**Esempio.** Il risultato deve restare nascosto fino alla chiusura. A distribuisce
quote dell'apertura e ricostruisce soltanto al verificarsi della regola concordata.
B cifra sotto una chiave collettiva e richiede K contributi di decifratura, senza
ricostruire la privata collettiva su un singolo server.

## M16 — Reveal e partecipante che smette di collaborare

**Stato e priorità: non definito, P3.** È il settimo punto di Niccolò. Prima
va stabilito se la traccia richieda davvero uno svelamento.

**Soluzione A — Apertura recuperabile mediante quote verificabili.**
Prima di ammettere il commitment, i nodi verificano che esistano abbastanza
quote corrette dei dati necessari all'apertura. Una condizione di recupero
esplicita autorizza la ricostruzione dopo il mancato reveal. Funziona se quote
e commitment sono collegati correttamente e ci sono abbastanza detentori disponibili.
Un quorum colluso potrebbe anticipare l'apertura: la soglia è anche un confine di privacy.

**Soluzione B — Regola deterministica per il mancato reveal.**
La configurazione stabilisce esclusione, valore sostitutivo o penalità secondo
il caso d'uso, così il protocollo termina anche senza quel partecipante.
Funziona come regola di avanzamento, ma non recupera il dato. Non è adatta se
l'esclusione permette di manipolare il risultato, per esempio scegliendo se
contribuire a un'estrazione casuale dopo aver visto gli altri contributi.

**Esempio.** Alice non apre la sua offerta. A recupera l'apertura attraverso K
quote valide, quando il protocollo lo autorizza. B tratta l'offerta come ritirata
secondo la regola pubblicata. La traccia deve stabilire quale dei due comportamenti sia corretto.

## M17 — Validità degli input, delle prove e delle modifiche

**Stato e priorità: solo formato nella demo, P3 ma indispensabile sulla traccia.**
Il controllo applicativo attuale non dimostra cosa contenga il commitment.

**Soluzione A — Validazione deterministica quando i dati possono essere letti.**
Definiamo una funzione di transizione con input, stato precedente e vincoli
espliciti; ogni validatore la esegue autonomamente. Funziona perché la stessa
operazione può essere riprodotta e confrontata. Richiede un ordine condiviso
quando due modifiche competono sullo stesso stato.

**Soluzione B — Prova specifica quando il dato deve restare nascosto.**
Usiamo un sistema di prova mantenuto per dimostrare esattamente la relazione
fra commitment, stato precedente e modifica ammessa. Funziona se il circuito
o la relazione codifica tutti i vincoli della traccia e lega le variabili pubbliche
corrette. Una prova di intervallo non dimostra da sola casualità o correttezza di una formula.

**Esempio.** Una risorsa può aumentare al massimo di D. A ricalcola l'aumento e
controlla lo stato iniziale. B verifica una prova che lega la modifica nascosta
al vecchio e al nuovo commitment. Se l'aumento deve essere anche casuale, occorre
un meccanismo verificabile aggiuntivo per la casualità.

## M18 — Correttezza e completezza del risultato finale

**Stato e priorità: assente, P3 per il calcolo; dipende da M09 e M11.**
Un insieme di firme valide non dimostra che il server abbia usato tutti gli input.

**Soluzione A — Ricalcolo indipendente su un insieme di input concordato.**
Pubblichiamo lista finale, dati ammessi, regola e risultato; i nodi ripetono il
calcolo e firmano lo stesso digest. Funziona se gli input possono essere divulgati
e l'insieme è stato chiuso correttamente. Non risolve da solo la censura in fase di raccolta.

**Soluzione B — Calcolo riservato con risultato verificabile.**
Una prova del calcolo, oppure un protocollo MPC appropriato con le garanzie
necessarie, lega risultato e lista dei commitment ammessi. Funziona se dimostra
la relazione applicativa esatta e include l'impronta dell'insieme finale. MPC
non implica automaticamente verifica pubblica né disponibilità del risultato.

**Esempio.** Il risultato è la somma dei contributi ammessi. A permette a chiunque
di rifare la somma sui dati pubblici. B può provare la somma senza pubblicare i
singoli valori. Entrambe devono riferirsi alla stessa lista finale: omettere C
e sommare correttamente il resto non è un risultato completo.

## M19 — Protezione dei metadati: IP, orari e collegabilità

**Stato e priorità: assente, P3.** È il sesto punto di Niccolò. Pseudonimato
e anonimato di rete sono proprietà diverse.

**Soluzione A — Relayer separato dal coordinatore e minimizzazione dei log.**
Un intermediario inoltra le richieste firmate senza aggiungere identificatori
superflui; il coordinatore vede il relayer come sorgente. Funziona contro la
visibilità diretta dell'IP presso il coordinatore. Il relayer vede il mittente;
collusione, log condivisi e correlazioni temporali possono annullare il vantaggio.

**Soluzione B — Trasporto anonimo o mescolamento con invii a lotti.**
Valutiamo una rete o un protocollo di anonimizzazione mantenuto e adeguato al
modello di osservatore, con batching e dimensioni meno riconoscibili dove utile.
Funziona riducendo collegamenti diretti e alcune correlazioni, con costi di
latenza e disponibilità. Ritardi casuali da soli non nascondono l'IP; non
promettiamo protezione da un osservatore globale senza un'analisi specifica.

**Esempio.** Alice invia un contributo da casa. A impedisce al coordinatore di
leggere direttamente il suo IP, ma il relayer lo conosce. B tenta di rendere
meno distinguibile il suo invio tra quelli di altri utenti; il margine prima
della scadenza deve includere la latenza introdotta.

## M20 — Disponibilità, assenze, censura e abuso delle risorse

**Stato e priorità: solo gestione logica dei quorum, P2.** La verifica delle
firme e la conservazione di ricevute hanno costi; un account non equivale a una persona.

**Soluzione A — Budget e limiti espliciti agli ingressi.**
Imponiamo dimensioni massime, controlli economici prima delle verifiche costose,
limiti alle sfide pendenti e code con risorse limitate. Funziona contenendo il
costo di richieste abusive; le quote per chiave possono essere aggirate creando
account, mentre i limiti per IP possono penalizzare utenti che condividono una rete.

**Soluzione B — Percorsi ridondanti e recupero da più nodi.**
Client e validatori possono inviare o recuperare messaggi da più repliche;
ritentano con identificatori stabili e misurano la salute dei nodi. Funziona
contro guasti o censura di un singolo canale, se esiste un percorso alternativo.
Se mancano T ricevute o Q approvazioni non abbassiamo automaticamente le soglie.

**Esempio.** Il coordinatore è sovraccarico e un validatore non risponde. A evita
che richieste enormi consumino tutte le risorse. B permette di usare altri nodi;
il protocollo procede solo se il numero disponibile resta sufficiente per T e Q.

## M21 — Test avversariali, prestazioni e riproducibilità operativa

**Stato e priorità: 36 test locali presenti, completamento P1/P2.** Il numero
dei test non misura da solo la copertura o la sicurezza.

**Soluzione A — Test di proprietà e guasti controllati.**
Generiamo configurazioni N/Q/T diverse, messaggi malformati e sequenze di eventi;
interrompiamo i processi durante commit, risposta, replica e recupero. Funziona
verificando invarianti come unicità del voto, durabilità della ricevuta e assenza
di riaperture dopo rollback. Servono anche test dei confini Python/C per input non validi.

**Soluzione B — Esecuzione con processi separati e revisione indipendente.**
Una procedura riproducibile avvia client, coordinatore e nodi, introduce ritardi,
disconnessioni e orologi difettosi e misura tempi, memoria e traffico. Un revisore
prova attacchi sul flusso completo. Funziona mostrando problemi che una demo in
un processo non espone; l'esito positivo di una campagna non dimostra assenza di tutti i bug.

**Esempio.** Il server salva C ma cade prima di rispondere. A controlla che il
retry ritrovi una sola accettazione. B verifica lo stesso scenario su processi
distinti e misura se le ricevute temporali arrivano con un margine sufficiente.
Misuriamo anche l'aumento di firme e byte al crescere di N, Q e T, prima di promettere scalabilità.

## M22 — Eventuale ancoraggio pubblico richiesto dalla traccia

**Stato e priorità: assente, P3 e condizionale.** È incluso perché compariva
nella valutazione delle garanzie. Non reintroduce XRPL per il tempo e non
autorizza integrazioni, transazioni o spese. Se la traccia non richiede una
blockchain, una percentuale zero qui può essere una scelta di scope corretta.

**Soluzione A — Ancorare soltanto checkpoint e risultato.**
Se richiesto, pubblichiamo impronta della configurazione, radice del registro
finale e digest del risultato su un registro pubblico adatto alla traccia.
Funziona fornendo un riferimento esterno per confrontare le versioni. Non rende
disponibili i dati, non dimostra che siano completi e non verifica il calcolo.

**Soluzione B — Far verificare al livello applicativo della blockchain una parte delle regole.**
Un contratto o componente equivalente, se la piattaforma lo permette, controlla
ammissione, unicità o una prova del risultato. Funziona spostando quei controlli
su una macchina di stato condivisa, ma richiede valutare costi, privacy, finalità
e supporto alle primitive. CROSS non può essere considerato verificabile nativamente
senza verificarne la disponibilità sulla piattaforma; la catena non diventa post-quantum per associazione.

**Esempio.** Dopo il risultato il coordinatore pubblica una lista diversa. A
permette di confrontarla con il digest già ancorato. B può impedire una seconda
finalizzazione incompatibile secondo le regole del contratto. Una lista iniziale
incompleta resta un problema anche se il suo hash è registrato immutabilmente.

## 5. Ordine di lavoro consigliato

| Fase | Aree | Risultato concreto da verificare |
| --- | --- | --- |
| 1 — Stato durevole | M06, M12; prime prove M21 | Un riavvio non perde nonce, attestazioni, ricevute o memoria temporale; retry e concorrenza non duplicano operazioni. |
| 2 — Storia verificabile | M07, custodia di base M05 | Checkpoint conservati da altri rendono rilevabili modifiche e rollback del registro. |
| 3 — Nodi reali | M08–M10, M20 | Client e validatori comunicano fra processi distinti e conservano dati indipendenti dal coordinatore. |
| 4 — Chiusura e risultato completo | M01, M11, struttura M18 | Esiste una regola documentata e testata per chiudere la sessione senza ignorare le prove ammesse. |
| 5 — Specializzazione sulla traccia | M02, M14–M18; M19/M22 se richiesti | Diritti, contenuti segreti, proprietà da provare e calcolo finale risolvono il problema effettivo della gara. |
| Continuo | M03–M05, M13, M21 | Dipendenze fissate, chiavi protette, verifiche riproducibili e limiti documentati. |

Le soluzioni A e B non sono tutte da costruire insieme. Per ogni area va scelta
la combinazione minima che soddisfa il requisito applicativo e il modello di
fiducia. In particolare, evitare un componente non richiesto può essere una
decisione migliore che aumentare artificialmente una percentuale.

## 6. Come aggiornare questo documento

Per modificare una percentuale annotare il requisito completato, i file cambiati,
la prova eseguita e il limite rimasto. Non aumentarla soltanto perché è stata
aggiunta una libreria, un algoritmo o una nuova schermata.

Il [README](../README.md) descrive l'API e l'implementazione corrente. Il
[percorso delle decisioni](IDEA_ATTUALE_E_PERCORSO.md) conserva la storia del
progetto. Il documento di Niccolò è un contributo alla revisione, non un elenco
di istruzioni eseguite automaticamente: tutte le proposte qui restano subordinate
alle scelte del team e alla traccia.
