# Contratto CLI e processi separati

Aggiornato: 2026-10-04. Contratto dell’attuale CLI 0.1.x, verificato da
`tests/test_cli_contract.py`. L’interfaccia Qt e quella SwiftUI chiamano lo stesso
`blurry_opsec.engine`, tramite worker; nessun secondo motore negli installer.

## Distribuzioni e avvio senza interfaccia

- `pip install blurry-opsec`: motore e comando `blurry`, senza dipendenza Qt.
- `pip install 'blurry-opsec[gui]'`: aggiunge Qt. `blurry` senza argomenti e `blurry-app`
  aprono l’app; `blurry INPUT ...` resta sempre senza finestre e senza onboarding.
- `python -m blurry_opsec INPUT ...` ha lo stesso contratto.
- Negli installer `blurry-engine[.exe] INPUT ...` usa la stessa CLI. `Blurry[.exe]`
  è il launcher grafico. Il motore congelato mantiene stdout/stderr anche su Windows.

Per server e container installare il pacchetto base. Nessuna UI, prompt, browser,
preferenza Qt o conferma durante l’elaborazione CLI, anche con l’extra GUI presente.
Usare percorsi locali assoluti, output già esistente e argomenti separati (mai una
stringa interpolata in una shell). `--` separa le opzioni dai nomi che iniziano con `-`.
L’assenza di volti genera un avviso, oppure blocca quel file con `--strict`.

```sh
blurry --json --strict --level high -o /work/output -- /work/input.jpg
```

## Stdout: JSON Lines

Le pipe di CLI e worker usano UTF-8, anche con code page Windows legacy.
Con `--json`, una riga JSON per input, nell’ordine degli argomenti, immediatamente
flushed. Niente testo di avanzamento su stdout. Il consumer deve accumulare i chunk
fino a newline e accettare campi aggiuntivi. Non cercare un singolo JSON nell’intero stream.

| Campo | Presenza / tipo |
|---|---|
| `input`, `level`, `mode`, `padding` | sempre per input; basename, stringhe e numero |
| `kind` | dopo il riconoscimento: `image` oppure `video` |
| `faces` | dopo analisi: intero; riquadri nelle foto, tracce nei video |
| `flags` | dopo analisi: array di oggetti con `kind` e indici opzionali `frame`, `track`, `box` |
| `frames`, `max_simultaneous` | solo video analizzati; interi |
| `status` | `ok`, `no_faces` (con strict), `error` |
| `output`, `metadata_removed`, `audio` | solo successo: basename, array di stringhe, stato audio |
| `error` | errore per file: testo diagnostico, non un codice da interpretare |

Errori globali (modello non valido, output inesistente) e errori argparse possono
terminare senza report per input. Non presumere che un report esista solo perché il
processo è terminato. I messaggi d’errore possono contenere dettagli dell’input:
il chiamante decide cosa mostrare e non deve registrarli come cronologia.

## Stderr: avanzamento e diagnostica

Righe `__PROGRESS__ {json}` con `stage` (stringa), `percent`, `framesProcessed`,
`totalFrames` (interi). I conteggi sono locali alla fase, non al batch; `percent` è
0–99 prima del completamento e 100 con `stage=completed`. La percentuale può
ripartire passando da analisi a render e da un file al successivo. Non è una
percentuale globale monotona. Le foto possono emettere solo `completed`.
Nessun evento `completed` per un file fallito o bloccato da strict. Stderr può
contenere avvisi del decoder e diagnostica non JSON: interpretarli separatamente.
Il risultato si decide da report e uscita del processo, mai dal solo avanzamento.

## Codici di uscita

| Codice | Significato |
|---|---|
| 0 | tutti gli input elaborati; `--help` e `--version` terminano con 0 |
| 1 | errore globale o almeno un errore per input senza strict no-face |
| 2 | almeno un file senza volti con `--strict`; anche errore d’uso argparse |

Per compatibilità, in un batch strict il codice 2 prevale anche se altri input
falliscono: controllare tutti i report. Un segnale o timeout del chiamante è un
fallimento distinto. Blurry continua gli altri input dopo un errore per file.
Gli originali non vengono sovrascritti; collisioni nell’output producono nomi numerati.

## Riferimento Chrono e integrazione futura

Letti, senza modifiche, il 2026-10-04:

- BACKEND `scripts/media_processor.py`: input e output posizionali, `--blur-faces`,
  `--opsec-level`, `--face-blocks`, report `success`, `faces_blurred` ecc.
- BACKEND `src/api/media-processor/controllers/media-processor.ts`: `spawn` Python,
  stdout raccolto, righe stderr ricomposte fra chunk e parser `__PROGRESS__`;
  progresso riportato nello stato del job.
- FRONTEND `src/services/mediaProcessingService.js`: chiamate al backend, polling
  del job e mapping di `X-OPSEC-*`/payload HTTP, nessuna esecuzione Python nel browser.

Blurry non è un sostituto a riga di comando del vecchio script. L’adattatore
Chrono implementato nel backend mappa `off` a `--no-faces`, passa gli altri livelli esplicitamente,
legge il nome di output dal report, traduce i campi del risultato e mantiene il
contratto HTTP attuale. Chrono usa esplicitamente `--mode pixel` per foto e video. La pixelazione per blocchi non equivale a `--mode pixel`;
non ignorare opzioni non supportate. Default differenti: Blurry usa high/solid e
rimuove l’audio, Chrono usa pixel, livelli per job e conserva l’audio video. Non applicare fallback a un rilevatore diverso.

`examples/backend-process.mjs` dimostra una singola chiamata senza shell, con stdin
chiuso, buffer limitati, timeout e annullamento. È una libreria di esempio in questa
repo, non un endpoint o un’integrazione attiva. Non conserva percorsi o report su disco.
Le politiche di coda, concorrenza, revisione umana, pulizia degli upload e dei file
parziali dopo SIGKILL spettano al backend nella successiva integrazione. Non
pubblicare automaticamente un file solo perché `status=ok`.
