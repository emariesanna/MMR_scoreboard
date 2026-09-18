# Specifica di un sistema di ranking pairwise per partite tra amici (Rocket League)

## 1. Obiettivo e contesto

Sistema di ranking per un gruppo di amici che gioca partite di Rocket League in formati eterogenei (1v1, 2v2, 3v3, 3v2 e altre composizioni sbilanciate), con livelli di attività molto disomogenei tra i giocatori (alcuni giocano centinaia di partite, altri poche decine).

Requisiti che hanno guidato le scelte di design:

- Il sistema deve gestire **team di dimensioni diverse** (incluso lo sbilanciamento numerico, es. 3v2).
- Non deve penalizzare né avvantaggiare ingiustamente i giocatori in base alla **quantità** di partite giocate: un giocatore con pochi dati non deve né "galleggiare" in classifica per mancanza di prove negative, né essere considerato automaticamente "nella media".
- Deve tenere conto della **confidenza** della stima (più dati → stima più affidabile), sia a livello di singolo giocatore che di singola coppia di giocatori.
- Deve rappresentare, come dato secondario consultabile, gli **scontri diretti** tra coppie di giocatori (anche in caso di dinamiche non transitive tipo A batte B, B batte C, C batte A).
- Deve poter pesare le partite in modo non binario (vittoria/sconfitta ai supplementari, margine di vittoria, recenza).

## 2. Struttura dati di base

### 2.1 Storico partite (dato grezzo, sempre conservato)

Per ogni partita si registra:

- **team_A**: lista di giocatori
- **team_B**: lista di giocatori
- **squadra vincente**: A o B
- **goal_A**, **goal_B**: punteggio finale (serve per il fattore margine)
- **overtime**: booleano, se la partita è finita ai supplementari
- **timestamp** o **indice cronologico**: necessario per il discount temporale pairwise (vedi §5)

Questo storico **non va mai scartato**: a differenza di un sistema incrementale (Elo/TrueSkill), qui la matrice aggregata viene ricalcolata da zero a ogni aggiornamento, quindi serve conservare tutte le partite individuali, non solo un aggregato.

### 2.2 Matrice pairwise `w_ij`

Matrice N×N (N = numero giocatori), non necessariamente simmetrica, dove la cella `w_ij` rappresenta il "punteggio di vittoria pesato e scontato" accumulato da *i* su *j* nel corso di tutte le partite in cui si sono trovati in squadre avversarie.

**Importante**: in una partita a squadre (es. 2v2), ogni giocatore del team vincente viene registrato come "vincitore" contro ogni giocatore del team perdente — cioè si aggiornano tutte le coppie incrociate tra i due team, non solo un confronto aggregato.

`w_ij` **non** è un conteggio intero: è una somma di pesi (vedi §4), quindi è a valori reali.

## 3. Modello statistico: Bradley-Terry esteso ai team

### 3.1 Modello base

Ogni giocatore *i* ha una forza latente `s_i > 0` (equivalentemente `θ_i = log(s_i)`, che vive su tutta la retta reale ed è la scala su cui si ragiona per l'incertezza).

Probabilità che *i* batta *j* (1v1):

```
P(i batte j) = s_i / (s_i + s_j) = e^θ_i / (e^θ_i + e^θ_j)
```

### 3.2 Estensione ai team

Per team di dimensione qualsiasi (inclusi team sbilanciati, es. 3v2):

```
forza_team = Σ_{k ∈ team} s_k

P(team A batte team B) = forza_A / (forza_A + forza_B)
```

Questo gestisce automaticamente lo sbilanciamento numerico: se un team più piccolo vince, è un segnale forte che i suoi membri sono sottostimati, e l'aggiornamento successivo lo riflette in proporzione maggiore.

### 3.3 Stima dei parametri: criterio di massima verosimiglianza

Si cercano i valori di `s_i` (o `θ_i`) che massimizzano la log-verosimiglianza dei risultati osservati nella matrice pesata `w_ij`.

### 3.4 Algoritmo risolutivo: iterazione di Zermelo

Formula di aggiornamento iterativo (caso 1v1 semplice, poi da estendere ai team — vedi nota sotto):

```
              W_i
s_i_nuovo = ─────────────
            Σ_j n_ij/(s_i+s_j)
```

dove:
- `W_i` = somma della riga *i* della matrice pesata (vittorie pesate totali di *i*)
- `n_ij` = `w_ij + w_ji` (totale "peso di incontri" tra *i* e *j*)

Si parte da `s_i = 1` per tutti, si itera su tutti i giocatori finché i valori convergono (tipicamente poche decine di iterazioni sono sufficienti; criterio di stop: variazione massima tra iterazioni sotto una soglia, es. 1e-6).

**Nota implementativa sull'estensione ai team**: la formula sopra è per confronti 1v1 diretti. Per gestire correttamente i team, l'implementazione deve generalizzare l'aggiornamento di Zermelo al caso Bradley-Terry-Luce per team (in cui ogni partita di squadra contribuisce all'update di tutti i giocatori coinvolti in proporzione al loro contributo alla forza di squadra). In alternativa più semplice e pragmatica: si può comunque costruire la matrice pairwise `w_ij` espandendo ogni partita di team in tutti i confronti incrociati membro-vs-membro (ogni giocatore del team vincente "batte" ogni giocatore del team perdente), e poi applicare Zermelo standard sulla matrice pairwise risultante. Questa seconda via è più semplice da implementare ed è quella assunta come default in questa specifica, salvo si preferisca implementare la versione team-level esatta per maggiore rigore statistico.

### 3.5 Normalizzazione

Il modello è definito a meno di un fattore di scala: dopo la convergenza, si può normalizzare (es. media dei punteggi = 1, o = 1000 per leggibilità). Solo i rapporti/differenze tra `s_i` (o `θ_i`) sono significativi.

## 4. Pesatura delle partite (valore non unitario)

Ogni partita contribuisce a `w_ij` non con un +1 fisso, ma con un peso calcolato come prodotto di più fattori indipendenti:

```
peso_partita = fattore_overtime × fattore_margine × fattore_discount_pairwise
```

### 4.1 Fattore overtime

```
fattore_overtime = 0.5  se la partita è andata ai supplementari
fattore_overtime = 1.0  altrimenti
```

### 4.2 Fattore margine (differenza reti)

Scala lineare da 1 (differenza minima, 1 goal) a 2 (differenza ≥ 6 goal, con saturazione):

```
diff = |goal_A - goal_B|
diff_clampata = min(diff, 6)
fattore_margine = 1 + (diff_clampata - 1) / 5
```

(diff=1 → 1.0; diff=6 → 2.0; diff=3 → 1.4; diff>6 → satura a 2.0)

### 4.3 Fattore discount temporale, calcolato **per coppia** (pairwise)

Non un discount globale né per-giocatore, ma specifico per ogni coppia (i,j): il "tempo" di riferimento è il numero di scontri diretti successivi tra quella specifica coppia, non le partite giocate da altri o da uno dei due contro avversari terzi.

```
fattore_discount = 0.99 ^ (numero di scontri diretti tra i e j avvenuti dopo questa partita)
```

L'ultimo scontro diretto tra *i* e *j* pesa 1.0, il penultimo 0.99, quello prima ancora 0.98, ecc. Il contatore avanza solo quando quella specifica coppia rigioca tra loro.

**Motivazione della scelta pairwise** (rispetto a discount globale o per-giocatore): evita che l'attività di altri giocatori nel gruppo "invecchi" artificialmente lo storico di una coppia che semplicemente si incontra di rado; cattura la freschezza dell'informazione in modo granulare, coerente con tutto il resto del sistema che è pensato pairwise.

**Parametro tarabile**: la base 0.99 implica un dimezzamento del peso dopo circa 69 scontri diretti tra la stessa coppia (`ln(0.5)/ln(0.99) ≈ 69`). Regolabile in base a quanto spesso si incontrano tipicamente le stesse coppie.

**Nota implementativa**: richiede di ordinare cronologicamente le partite dirette tra ogni coppia (i,j) e contare, per ciascuna, quante ne sono seguite tra la stessa coppia.

## 5. Regolarizzazione (Laplace smoothing pairwise)

Prima di applicare Zermelo, si corregge la matrice grezza aggiungendo **1 vittoria fittizia e 1 sconfitta fittizia per ogni coppia possibile di giocatori del gruppo**, comprese le coppie che non si sono mai incontrate:

```
w_ij_corretta = w_ij + 1
w_ji_corretta = w_ji + 1
```

applicato a **tutte** le coppie (i,j), i ≠ j, non solo a quelle con dati sbilanciati.

### Motivazioni:

1. **Evita la separazione perfetta**: se *i* ha vinto tutte le partite contro *j* (o viceversa), l'MLE di Bradley-Terry non sarebbe definito (stima che tende a infinito) senza questa correzione.
2. **Non introduce bias verso una forza "media" assoluta**: a differenza di un fantasma globale con forza fissa `s_0`, questa correzione è locale a ogni coppia — non assume che i giocatori siano "nella media del gruppo", dice solo che ogni confronto specifico parte da un'incertezza massima (50/50) finché non arrivano prove dirette.
3. **Garantisce connessione del grafo**: se sottogruppi di amici non si sono mai incontrati direttamente, Bradley-Terry richiederebbe altrimenti un grafo di confronti connesso per dare stime sensate su tutti. Aggiungendo 1-1 fittizio a ogni coppia possibile, il grafo è sempre completamente connesso.
4. **Effetto quantitativo verificato**: prima di ogni scontro diretto reale, P(i batte j) = 50%. Dopo una prima vittoria reale di *i* su *j*: `w_ij=2, w_ji=1` → P = 66.7% (non 100%). L'effetto della correzione si stempera progressivamente mano a mano che si accumulano più scontri diretti reali tra la stessa coppia.

**Nota sull'interazione col discount temporale (§4.3)**: la correzione di smoothing è un termine fisso (+1/+1) aggiunto alla matrice pesata e scontata. Non è soggetta essa stessa a discount (è "sempre presente" con peso 1, indipendentemente da quando sono avvenuti gli scontri reali).

## 6. Stima dell'incertezza (σ_i)

Dopo la convergenza di Zermelo (sulla matrice corretta con smoothing), si calcola l'incertezza di ciascun giocatore tramite l'**informazione di Fisher**:

```
I_i = Σ_j  n_ij × p_ij × (1 - p_ij)

σ_i ≈ 1 / √I_i
```

dove:
- `n_ij` = peso totale di incontri tra i e j nella matrice corretta (w_ij_corretta + w_ji_corretta)
- `p_ij` = P(i batte j) secondo il modello stimato, con i `θ` convergenti

Interpretazione: `p_ij(1-p_ij)` è massimo per confronti equilibrati (p_ij vicino a 0.5) e minimo per confronti scontati (p_ij vicino a 0 o 1) — quindi le partite tra avversari di forza comparabile sono più "informative". `n_ij` alto (tante partite, pesate/scontate) aumenta l'informazione raccolta indipendentemente dal valore stimato di θ_i — coerente col requisito di non voler assumere nulla sulla posizione della stima, solo penalizzare la scarsità di dati.

## 7. Punteggio finale (classifica ufficiale)

```
score_i = θ_i - k × σ_i
```

con `k` tipicamente tra 2 e 3 (parametro tarabile: più alto = più conservativo verso chi ha pochi/incerti dati).

Questo è l'equivalente, nel framework Bradley-Terry, del rating conservativo `mu - k*sigma` usato da TrueSkill — ma qui `σ_i` è derivato rigorosamente dal modello (Fisher information) e riflette sia la quantità sia la recenza/qualità dei dati per coppia, non un'euristica separata.

## 8. Comportamento atteso e casi di verifica (da includere nei test)

Il sistema dovrebbe produrre questi comportamenti, utili come test di sanity check:

1. **Giocatore molto attivo con winrate medio-basso vs giocatore poco attivo con winrate alto**: es. 1000 partite al 40% vs 10 partite al 50% → il primo dovrebbe avere `θ_i` più basso ma `σ_i` molto piccola (score ≈ θ_i); il secondo dovrebbe avere `θ_i` vicino alla media ma `σ_i` grande (score tirato giù). L'ordinamento finale deve riflettere la maggiore affidabilità del primo.
2. **Team sbilanciati (3v2)**: una vittoria della squadra numericamente svantaggiata deve produrre un aggiornamento più marcato sui punteggi dei suoi membri rispetto a una vittoria a parità numerica.
3. **Dinamiche non transitive**: A batte B, B batte C, C batte A — la matrice pairwise grezza deve continuare a rappresentare correttamente questa situazione anche se il ranking scalare (θ_i) non può per costruzione catturarla appieno; è previsto uno scarto tra stima diretta (rapporto grezzo w_ij/(w_ij+w_ji)) e stima del modello globale, da esporre come dato interessante, non da "correggere".
4. **Sottogruppi poco connessi**: due sottogruppi di amici che si sono incontrati raramente o mai devono comunque ricevere una stima comparabile (grazie allo smoothing su tutte le coppie), sia pure con σ alta sulle coppie inter-gruppo.
5. **Vittoria ai supplementari con margine minimo**: deve pesare meno (circa la metà) di una vittoria netta a tempo regolamentare con ampio scarto di gol.
6. **Coppia che ha smesso di incontrarsi di recente**: la stima locale su quella coppia deve progressivamente perdere peso (discount pairwise), pur restando fresche le stime di ciascuno dei due contro altri avversari con cui continuano a giocare regolarmente.

## 9. Output del sistema verso l'utente

- **Classifica generale**: giocatori ordinati per `score_i`, eventualmente con `θ_i` e `σ_i` mostrati separatamente per trasparenza.
- **Matrice degli scontri diretti**: vista secondaria, mostra il conteggio/peso grezzo (senza smoothing) `w_ij` e la stima diretta di probabilità `w_ij/(w_ij+w_ji)` per ogni coppia che si è effettivamente incontrata — utile per rispondere a "chi ha la meglio tra X e Y" e per evidenziare eventuali dinamiche non transitive rispetto al ranking globale.
- **Ricalcolo**: l'intera pipeline (dalla matrice pesata fino allo score finale) viene ricalcolata da zero ogni volta che si vuole una classifica aggiornata (nessun aggiornamento incrementale "online" come in Elo/TrueSkill). Per un gruppo di amici (decine di giocatori, centinaia/migliaia di partite), il ricalcolo completo è computazionalmente banale (converge in millisecondi).

## 10. Parametri tarabili (da esporre come configurazione, non hard-coded)

| Parametro | Significato | Valore di partenza suggerito |
|---|---|---|
| `k` | Conservatività dello score finale rispetto a σ | 2–3 |
| `fattore_overtime` | Peso di una vittoria ai supplementari | 0.5 |
| `margine_min`, `margine_max` | Range del fattore margine gol (1 goal → 6+ goal) | 1 → 2, saturazione a 6 gol |
| `discount_base` | Base del decadimento esponenziale pairwise | 0.99 |
| soglia di convergenza Zermelo | Criterio di stop dell'iterazione | 1e-6 su variazione massima |

## 11. Struttura dati riepilogativa per l'implementazione

**Input persistente**: lista di partite, ciascuna con `{team_A: [...], team_B: [...], goal_A, goal_B, overtime: bool, timestamp}`.

**Pipeline di calcolo** (funzione pura, ricalcolata da zero ad ogni richiesta di classifica aggiornata):

1. Per ogni partita → calcola `peso_partita` (§4)
2. Espandi ogni partita nei confronti pairwise membro-vs-membro tra i due team, sommando i pesi in `w_ij` grezza
3. Applica smoothing +1/+1 a tutte le coppie possibili (§5)
4. Esegui iterazione di Zermelo sulla matrice corretta → `θ_i` per ogni giocatore (§3.4)
5. Calcola `σ_i` da Fisher information sulla stessa matrice corretta (§6)
6. Calcola `score_i = θ_i - k·σ_i` (§7)
7. Esponi sia la classifica (`score_i`) sia la matrice pairwise grezza (senza smoothing, per la vista "scontri diretti")

**Output**: classifica ordinata, matrice scontri diretti, eventualmente storico per audit/debug.
