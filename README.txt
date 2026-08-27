# WH40K 11th Edition Companion — PWA

App web progressiva (PWA) per consultare datasheet, regole, costruire armate e giocare a Warhammer 40,000 11th Edition.

Fonte dati: Wahapedia.ru

## File dell'app

| File | Descrizione |
|------|-------------|
| `index.html` | Interfaccia principale (datasheet, regole, army builder, game mode) |
| `data.json` | Dati generati dallo script Python (unità, regole, tooltip) |
| `manifest.json` | Manifest PWA (installazione su dispositivo) |
| `sw.js` | Service Worker (cache offline + auto-update dati) |

## Come pubblicare su GitHub Pages (gratis)

1. Vai su https://github.com e crea un nuovo repository (es. `wh40k-companion`)
2. Carica i 4 file (`index.html`, `data.json`, `manifest.json`, `sw.js`) nella root del repository
3. Vai su **Settings → Pages**
4. In **Source**, seleziona **Deploy from a branch**
5. Seleziona il branch `main` e la cartella `/ (root)`
6. Clicca **Save**
7. Dopo 1-2 minuti, l'app sarà disponibile all'URL:
   `https://TUO-USERNAME.github.io/wh40k-companion/`

## Come usarla come app

### Su PC/Mac:
- Apri l'URL nel browser (Chrome o Edge)
- Clicca l'icona "Installa" nella barra degli indirizzi
- L'app si aprirà in una finestra separata

### Su Android:
- Apri l'URL in Chrome
- Menu (tre puntini) → "Aggiungi a schermata Home"
- L'app apparirà con la sua icona

### Su iPhone/iPad:
- Apri l'URL in Safari
- Tocca il pulsante Condividi → "Aggiungi a Home"
- L'app apparirà con la sua icona, a schermo intero

## Funzionalità

- **Datasheet**: 1648 unità divise per 22 fazioni, con stats, armi, abilità, keyword, punti
- **Tooltip**: passando il mouse (o toccando su mobile) sulle keyword delle armi e delle abilità (es. LETHAL HITS, Feel No Pain, Deep Strike) compare un popup con la definizione della regola
- **Core Rules**: 170 regole con ricerca
- **Army Builder**: crea armate con limite punti, salva/carica liste nel browser, esporta come testo
- **Game Mode**: vista compressa di tutte le unità dell'armata per consultazione rapida durante il gioco

## Come aggiornare i dati

Quando Wahapedia pubblica nuovi datasheet o aggiornamenti:

1. Sul tuo PC, rilancia lo script Python:
   ```
   python wh40k11ed_scraper.py
   ```
   (legge dalla cache, scarica solo le pagine nuove)

2. Copia il file `data.json` generato nel repository GitHub

3. Sostituisci il vecchio `data.json` su GitHub (Edit file → incolla → Commit)

4. Tutti i dispositivi vedranno i nuovi dati al prossimo accesso.
   Il Service Worker scarica l'aggiornamento in background.

## Funzionamento offline

- Il Service Worker (`sw.js`) salva in cache `index.html` e `data.json`
- Una volta aperta l'app la prima volta con connessione, funziona anche offline
- I dati vengono aggiornati in background quando c'è connessione
- L'armata salvata nel browser (localStorage) persiste tra le sessioni

## Aggiornamento automatico (opzionale)

Per aggiornamenti completamente automatici dei dati, puoi configurare **GitHub Actions** per rilanciare lo script Python periodicamente. Vedi la documentazione GitHub Actions per i dettagli.
