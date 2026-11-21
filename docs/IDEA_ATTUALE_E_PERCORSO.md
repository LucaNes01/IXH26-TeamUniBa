# Team Bari: idea attuale del progetto e percorso delle decisioni

**Documento di confronto per il team — 13 novembre 2026**

**Nota del 20 novembre 2026.** Questo documento conserva le decisioni delle
prime revisioni. Il codice corrente si concentra sulla verifica della cattura
e della derivazione del file finale. Vedi il [README](../README.md).

**Aggiornamento del 14 novembre 2026:** il backend CROSS didattico descritto
in questo documento è stato sostituito dalla libreria C ufficiale di riferimento
v2.2. Sono state aggiunte ricevute firmate dal coordinatore, che conserva la
propria chiave privata separata da quelle dei partecipanti. La suite attuale
comprende 36 test, con vettori CROSS ufficiali; la rigenerazione dei 100 KAT di
ciascuna variante small/fast coincide con gli SHA-512 upstream. Per lo stato
aggiornato, installazione e limiti vedere il [README principale](../README.md).
Il resto del documento conserva il percorso decisionale della prima revisione.
Il vecchio toolkit HQC/MPC/ZKP/XRPL e le sue regressioni sono stati rimossi dal
repository perché non utilizzati dal protocollo corrente. I riferimenti a quei
file nelle sezioni seguenti descrivono il lavoro precedente.
La scadenza usa ora ricevute temporali firmate dai validatori, distinte dalle
approvazioni, con soglia e tolleranza immutabili. L'orologio del coordinatore
non decide l'ammissione; le prove tempestive possono essere consegnate dopo.
Il precedente stato `SCADUTO` è sostituito da `IN_ATTESA_DI_PROVE` quando un quorum
osserva il termine: una chiusura definitiva richiede ancora prove di completezza.
Non è stata introdotta un'integrazione XRPL.

Questo documento descrive la direzione concordata e la prima implementazione.
La traccia dell'hackathon 2026 non è ancora disponibile: prepariamo una base
riutilizzabile, senza assumere che la sfida sarà necessariamente un'elezione o un gioco.

## 1. L'idea in poche parole

Vogliamo un protocollo in cui gli utenti possano registrare un'identità
crittografica pseudonima e pubblicare contributi sotto forma di commitment.
Un insieme di validatori autorizzati controlla i contributi e ne firma gli esiti.
Un contributo viene accettato quando raggiunge la soglia fissata per la sessione.

**Registrarsi permette di inviare richieste, ma non attribuisce automaticamente
potere di validazione, token o diritti di voto.**

Il server coordina il processo: apre la sessione, espone la configurazione,
raccoglie i contributi e verifica le attestazioni. Nella versione attuale il server
è centralizzato; l'obiettivo successivo è far eseguire le verifiche a nodi distinti.
Non descriviamo quindi il prototipo come una rete già decentralizzata o trustless.

## 2. Da dove siamo partiti

### L'esperienza del progetto 2025

Lo scorso anno il Team Bari ha ottenuto il terzo posto con ZK-F1-AI. Il progetto
utilizzava commitment dello stato delle auto, prove ZK sulle operazioni e un
meccanismo commit-reveal, con contratti su Ethereum.

La lezione da riprendere è il collegamento fra stato, operazioni consentite e
risultato: ogni componente crittografico deve risolvere un problema del protocollo.
Una collezione di algoritmi, da sola, non costituisce una soluzione completa.

Esaminando il codice conservato negli artefatti Hardhat abbiamo anche chiarito
il tema degli account multipli: c'erano controlli per indirizzo e per commitment,
ma non una verifica dell'unicità della persona. I token venivano inizialmente
assegnati al deployer e distribuiti nello script di test, non regalati automaticamente
a ogni nuovo wallet. Questo gestiva il setup della demo, senza risolvere in generale
il problema di una persona che controlla più account.

### Il toolkit preparato per il 2026

Il repository iniziale raccoglieva HQC, CROSS, commitment su sindrome, prove di
range, Shamir e strumenti di ancoraggio XRPL. La vecchia `versione_facile`
aggiungeva registrazioni dinamiche, file di identità e raccolta delle firme.

La revisione ha mostrato che quel flusso non realizzava ancora le garanzie
descritte. In particolare, il server conosceva il segreto e generava anche le
chiavi private degli utenti. Nella versione facile sono stati inoltre riprodotti:

- recupero del segreto da una sola quota usando il seme pubblico del polinomio;
- decifratura del KEM semplificato usando informazioni pubbliche;
- falsificazione di una firma semplificata;
- raggiungimento del quorum sommando firme su proposte diverse.

Questi riscontri riguardano quelle implementazioni: non sono attacchi agli
algoritmi ufficiali HQC o CROSS. Hanno motivato l'eliminazione dei vecchi sei
script della versione facile e la costruzione di un nuovo flusso di sessione.
Il resto del toolkit rimane materiale di studio, con limiti da valutare separatamente.

## 3. Cosa abbiamo ricavato dalle tracce precedenti

| Edizione | Problema centrale | Indicazione per noi |
| --- | --- | --- |
| 2024: elezione De Cifris | Il presidente può alterare il risultato o omettere scrutini locali. Il conteggio locale è assunto corretto. | Servono completezza dei contributi e correttezza dell'aggregazione. |
| 2025: F1-AI | Stato delle auto e formula devono restare segreti; allenamenti e gare devono rispettare le regole anche con giocatori o server disonesti. | Servono gestione dei segreti, transizioni ammesse e verifica del risultato. |

Nel 2025 i parametri devono essere sconosciuti anche al proprietario e le modifiche
devono essere casuali. Una prova del solo intervallo di modifica non dimostra
casualità; una firma non dimostra la correttezza della velocità. La traccia non
stabilisce inoltre che la formula segreta sia lineare.

Entrambe le tracce richiedono una blockchain, ma non impongono nelle slide
consultate un particolare algoritmo post-quantum. Il progetto dovrà risolvere
prima il problema applicativo della nuova traccia.

Fonti originali, collegate dalla [pagina ufficiale IXH26](https://www.decifris.it/ixh26/):

- [Traccia IXH24, Track 1](https://drive.google.com/file/d/17NaxyjnmY-VAdZkmY0pDQbstzSYeB6LZ/view).
- [Traccia IXH25, Track 1](https://drive.google.com/file/d/1NkwMQN705u5xdYd7kk1a06ZXsT0FkGtH/view).

## 4. I tre ruoli dell'architettura attuale

| Ruolo | Cosa può fare | Quale potere non riceve automaticamente |
| --- | --- | --- |
| Utente registrato | Pubblicare contributi firmati con la propria chiave. | Non diventa validatore e non ottiene un diritto elettorale. |
| Validatore autorizzato | Verificare un contributo e firmare un esito positivo o negativo. | Non può cambiare da solo soglia, comitato o contributo. |
| Server coordinatore | Configurare una nuova sessione e raccogliere richieste e attestazioni. | Le sue sole dichiarazioni non sostituiscono le firme dei validatori. |

Chiunque disponga dei dati pubblici può controllare le firme. Nel quorum contano
soltanto i validatori elencati nella configurazione della sessione.

Resta una fiducia esplicita nel coordinatore per la configurazione iniziale,
la disponibilità dei dati, la completezza di ciò che mostra e l'orologio.
L'implementazione attuale non elimina queste responsabilità.

## 5. Il flusso concordato

### A. Apertura della sessione

Il coordinatore fissa e rende consultabili:

- identificatore del sistema e della sessione;
- elenco delle chiavi pubbliche dei validatori;
- numero di approvazioni richieste;
- scadenza;
- identificatore della regola applicativa da controllare.

La configurazione ha un'impronta crittografica. Le firme della sessione sono
legate a quell'impronta, che comprende anche la suite di firma.

**Elenco, soglia e scadenza non cambiano durante la sessione.** Una nuova
configurazione richiede una nuova sessione; non abbiamo introdotto un protocollo
di aggiornamento dinamico dei validatori.

### B. Registrazione pseudonima

Il client genera le chiavi CROSS e conserva la privata. Il server invia una sfida
casuale monouso; il client la firma e dimostra di controllare la chiave che vuole
registrare. La richiesta è legata anche alla configurazione della sessione.

Il registro consultabile contiene identificatore pseudonimo e chiave pubblica.
Non richiede nome, cognome o chiave privata. La stessa chiave non si registra
due volte nella sessione.

Questo è pseudonimato: i messaggi di una stessa chiave sono collegabili.
Non promettiamo anonimato di rete, impossibilità di identificazione indiretta
o un registro permanente tra sessioni, che non è ancora implementato.

### C. Pubblicazione del contributo

L'utente firma un messaggio che lega insieme autore, commitment, digest
dell'eventuale prova applicativa, nonce e configurazione della sessione.
Il nonce distingue le richieste e non può essere riutilizzato dallo stesso autore
nella stessa sessione.

Il coordinatore controlla registrazione, firma e regola applicativa prima di
ammettere il contributo alla raccolta delle attestazioni.

### D. Controllo dei validatori

Ogni nodo deve verificare autonomamente il contributo secondo la medesima regola
e firmare un esito riferito allo specifico contributo e alla configurazione.

Una firma valida risponde a «chi ha autorizzato questo messaggio?».
La regola applicativa risponde a «questo contributo rispetta i requisiti?».
Sono controlli distinti. Una maggioranza di firme non rende corretta una prova falsa.

### E. Decisione e scadenza

Il coordinatore accetta soltanto firme dei validatori configurati. Ogni validatore
conta una volta per contributo; firme di contributi o sessioni differenti non si
sommano. Una chiave non può essere elencata sotto due nomi per contare due volte.

| Stato | Condizione |
| --- | --- |
| `IN_ATTESA` | Non ci sono ancora abbastanza approvazioni, ma la soglia resta raggiungibile. |
| `APPROVATO` | La soglia è stata raggiunta prima della scadenza. |
| `RIFIUTATO` | Le attestazioni negative rendono impossibile raggiungerla. |
| `SCADUTO` | La scadenza arriva senza una decisione definitiva. |

Alla scadenza la soglia non si abbassa. Un'assenza non viene trasformata in
un'approvazione. Le decisioni già definitive restano tali.

## 6. Esempio: cinque validatori, quattro approvazioni

Il server apre S1 con cinque validatori e soglia quattro. Alice si registra
senza pubblicare il proprio nome e invia un commitment firmato.

1. Tre validatori approvano: il contributo resta in attesa.
2. Arriva la quarta approvazione valida: diventa approvato.
3. Un secondo contributo riceve soltanto tre approvazioni prima della scadenza:
   diventa scaduto, senza abbassare la soglia.
4. Se Alice crea cento nuovi account, nessuno entra automaticamente nel comitato.
   Quegli account non possono costruire un quorum a proprio favore.

Con soglia quattro su cinque, un solo esito negativo non basta a bloccare
definitivamente il contributo; due esiti negativi rendono impossibili quattro
approvazioni. Quattro su cinque è una configurazione dimostrativa, non una formula
universale di sicurezza. Contare firme non equivale a implementare consenso BFT.

## 7. Le idee scartate o rinviate

| Idea discussa | Decisione attuale | Motivo |
| --- | --- | --- |
| Tutti gli iscritti diventano validatori con lo stesso peso. | Scartata. | Una persona potrebbe creare molti account e controllare il quorum. |
| Ogni contributo richiede l'unanimità. | Scartata per questa prima versione. | Un solo nodo assente o ostile potrebbe bloccare tutto. |
| Soglia casuale, eventualmente con generatore post-quantum. | Scartata. | La casualità può produrre una soglia insufficiente e non definisce un modello di sicurezza. |
| Soglia aggiornata periodicamente in base agli utenti online. | Scartata. | Gli utenti non sono i validatori; ingressi e disconnessioni non devono cambiare le condizioni a processo iniziato. |
| Aggiornamento del comitato durante una sessione con approvazioni della configurazione precedente. | Rinviato. | Introduce complessità non necessaria al primo obiettivo. |
| Una persona può registrarsi una sola volta, sempre. | Rinviata alla traccia. | Chiavi e IP non dimostrano l'unicità personale; serve una procedura di abilitazione se il diritto è personale. |
| Il server genera chiavi private, segreto e quote per tutti. | Rimossa dal nuovo flusso. | Non realizza l'obiettivo di separare il coordinatore dai segreti degli utenti. |
| Tre backend di firma: CROSS, UOV e SNOVA. | Ridimensionata e rinviata. | Prima serve un protocollo completo. UOV resta un possibile confronto legato al lavoro di tesi; SNOVA un riferimento successivo. |
| Una ZKP generica risolve registrazione e legittimità. | Scartata come impostazione. | Occorre specificare esattamente la proprietà da provare e la procedura che attribuisce il diritto. |

### La distinzione tra account e diritti

Il confronto con Bitcoin ci ha aiutato a formulare meglio il problema: poter
creare molte chiavi non deve significare poter creare arbitrariamente potere.
Non stiamo copiando il consenso di Bitcoin, né implementando proof-of-work.

Per ora garantiamo una registrazione per chiave nella sessione, non una per
persona. Se la traccia richiederà «un voto per persona» o «un bonus iniziale per
persona», dovremo aggiungere una procedura di abilitazione. Il registro degli
account non la sostituisce.

## 8. Perché CROSS e quale ruolo può avere UOV

CROSS è stato scelto per autenticare richieste e attestazioni. È una firma derivata
da prove zero-knowledge, ma la sua prova interna non sostituisce una prova
applicativa sul voto, sul commitment o sull'unicità della persona.

UOV e SNOVA sono stati discussi per il lavoro di tesi di un componente del team.
La modularità della firma può essere utile come confronto dimostrativo, ma non
è il contributo principale del progetto. Non sono attualmente integrati.

La discussione sull'articolo di Craig Gidney ha inoltre chiarito che aggiungere
firme post-quantum ai messaggi applicativi non rende automaticamente post-quantum
la blockchain sottostante. Anche i verificatori e i collegamenti fra gli oggetti
firmati devono essere corretti: due firme non correggono una regola sbagliata.

Riferimenti: [CROSS](https://www.cross-crypto.com/),
[UOV](https://www.uovsig.org/homepage),
[articolo discusso](https://algassert.com/post/2602).

## 9. Cosa esiste oggi e cosa manca

| Componente | Stato attuale |
| --- | --- |
| Configurazione immutabile della sessione | Implementata. |
| Registrazione con sfida monouso e firma | Implementata in memoria, per sessione. |
| Registro pubblico degli pseudonimi e delle chiavi | Consultabile tramite API Python; non è ancora un servizio pubblico in rete. |
| Separazione fra utenti e validatori | Implementata. |
| Contributi e attestazioni legati alla stessa configurazione | Implementati. |
| Quorum fisso, duplicati, rifiuti e scadenza | Implementati. |
| Controllo applicativo del contenuto nascosto | Interfaccia esplicita; nella demo si verifica solo un commitment di 32 byte senza prova. |
| CROSS ufficiale con parametri conformi | Da integrare: si usa ancora il CROSS didattico personalizzato del toolkit. |
| Persistenza e ripristino | Da implementare. Un riavvio perde lo stato e i controlli di replay già consumati. |
| Comunicazione e sincronizzazione fra nodi distinti | Da implementare; la demo li simula nello stesso processo. |
| Identità personale, abilitazione elettorale e voto non collegabile all'account | Non implementati. Da valutare secondo la traccia. |
| Transazioni XRPL confermate e verifica dal ledger | Da integrare. Gli strumenti di studio preesistenti non sono il nuovo flusso on-chain. |
| Calcolo finale, completezza degli input e gestione dei segreti | Da definire e implementare sul caso d'uso. |

Sono passati 25 test: 15 sui nuovi scenari di sessione e 10 regressioni del
toolkit precedente. Sono verifiche di comportamento, non una dimostrazione
generale di sicurezza né un audit delle primitive.

Il materiale corrente è in `protocollo/sessione.py`,
`versione_facile/demo_sessione.py` e `tests/test_sessione.py`.
I documenti precedenti di flusso e changelog restano storici e descrivono anche
componenti che sono stati rimossi. I file runtime delle vecchie identità non sono
stati cancellati e non vengono usati dalla nuova demo.

## 10. Come mostrarlo e cosa costruire dopo

Dalla radice del repository:

```bash
python3 -B versione_facile/demo_sessione.py
python3 -B -m unittest discover -s tests -v
```

La demo mostra registrazione pseudonima, tentativo bloccato di autopromozione a
validatore, approvazione con quattro firme e scadenza con tre firme. Le chiavi sono
generate dai client simulati e non vengono stampate.

L'ordine di lavoro proposto è:

1. **Persistenza:** conservare configurazione, registrazioni, contributi, nonce e
   attestazioni, con ripristino coerente dopo un riavvio.
2. **Backend di firma conforme:** sostituire il CROSS didattico e verificarne
   l'integrazione con vettori di test appropriati.
3. **Nodi distinti:** trasportare i messaggi e far verificare a ciascun nodo gli
   stessi dati, affrontando disponibilità e possibili viste discordanti.
4. **Regole della traccia:** stabilire diritti, controlli applicativi, eventuali
   segreti distribuiti e funzione di calcolo del risultato.
5. **Ruolo di XRPL:** integrare il registro pubblico dove aggiunge una garanzia
   concreta, verificando transazioni e dati confermati.

Il messaggio da condividere nel team è: **stiamo costruendo un protocollo di
contributi firmati e verificati con comitato e quorum fissi per sessione.**
La gestione delle persone, il significato del contributo e il risultato da
certificare verranno specializzati sulla traccia. La priorità è rendere coerente
e verificabile il flusso, prima di aggiungere altre primitive o opzioni di demo.
