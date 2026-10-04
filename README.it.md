# Blurry

**Copre i volti e cancella i metadati di foto e video, sul tuo computer e senza rete.**

[English](README.md) · [Modello delle minacce](THREAT_MODEL.it.md) · [Sicurezza](SECURITY.md) · Licenza: [MIT](LICENSE)

Blurry trova i volti, li copre con un rettangolo nero (o con la pixelazione) e scrive un file nuovo
senza metadati: niente posizione GPS, niente modello della fotocamera, niente date, niente
miniatura nascosta dell'originale. Funziona tutto senza rete: niente server, account, telemetria o
controllo degli aggiornamenti, e rifiuta di aprire connessioni anche se qualcosa ci prova.

> Blurry è un'**app** (trascini foto e video, controlli i riquadri, esporti) e un **comando da
> terminale** per gli script. Su Mac è un'app nativa che si scarica come `Blurry.dmg`; su Windows
> e Linux l'app e il comando si installano con Python, come spiegato sotto.

## Che cosa fa

- **Copre i volti** in foto e video, con il rilevatore YuNet (incluso; il suo SHA-256 si controlla
  a ogni avvio, e se non corrisponde Blurry non parte).
- **Toglie tutti i metadati**:
  - foto: EXIF (compresa la miniatura incorporata), GPS, XMP, IPTC, profili colore e commenti;
  - video: tag del contenitore e delle tracce (luogo QuickTime, dispositivo, date), capitoli,
    sottotitoli, tracce dati (come il GPS di GoPro e droni) e copertine.
- **Applica prima la rotazione** di foto e video del telefono ai pixel, così i volti di lato non
  sfuggono, e il risultato si vede come prima senza portarsi dietro i metadati di rotazione.
- **Toglie l'audio di default**, perché le voci possono identificare. Per tenerlo: `--keep-audio`.
- **Non sovrascrive mai niente**: l'originale resta intatto, e se il nome di uscita è già preso
  ne usa uno numerato.
- **Non tace mai se non trova volti**: avvisa, e con `--strict` non scrive niente ed esce con
  codice 2.

## Che cosa non fa

Leggi il [modello delle minacce](THREAT_MODEL.it.md) prima di fidarti di Blurry. In breve, **non**
nasconde corpi, vestiti, tatuaggi, voci, luoghi, riflessi né l'impronta del sensore della
fotocamera; non può coprire un volto che il rilevatore non trova; non cancella l'originale, che può
essere sincronizzato anche su iCloud o Google Foto.

**Il rilevatore può mancare dei volti**, soprattutto di profilo, al buio, molto piccoli o girati di
lato. Guarda sempre il risultato prima di condividerlo. I file con rilevamenti incerti sono elencati
sotto `flags` nel resoconto `--json`.

## Installazione

### Mac

Apple Silicon (M1 o successivi), macOS 14 o successivo.

1. Scarica [`Blurry.dmg`](https://github.com/Chrono-Web/BLURRY/releases/latest/download/Blurry.dmg)
   dalla pagina delle [Release](https://github.com/Chrono-Web/BLURRY/releases).
2. Aprilo e trascina Blurry sulla cartella Applicazioni.
3. La prima volta macOS avvisa che non può verificare lo sviluppatore: Blurry non è firmato da
   Apple. Apri Impostazioni di Sistema › Privacy e sicurezza, scorri in fondo e premi **Apri
   comunque** accanto a Blurry. Serve una volta sola.

### Con Python (Windows, Linux, comando da terminale)

Serve Python 3.12. Il modo più semplice è [pipx](https://pipx.pypa.io/) (oppure `uv tool`). Con
l'app:

```bash
pipx install "blurry-opsec[gui]"
```

Solo il comando da terminale:

```bash
pipx install blurry-opsec
```

## L'app

**Su Mac** (`Blurry.dmg`):

1. **Trascina** foto e video nella finestra, oppure usa *Scegli file…* (⌘O).
2. Una **guida** prende un file alla volta: il file al centro e sotto una scelta alla volta
   (sensibilità, copertura, margine e, per i video, l'audio). Dalla copertura in poi l'immagine
   mostra esattamente quello che verrà esportato; in un video puoi riprodurre il risultato coperto.
3. **Correggi i riquadri** a mano se serve: nelle foto disegna, sposta, ridimensiona o togli i
   riquadri; nei video spegni una traccia che non è un volto, o disegna un riquadro fermo su un
   intervallo di tempo.
4. **Esporta…** apre il pannello di salvataggio sulla cartella dell'originale, con
   `<nome>_blurry`. L'originale non viene mai toccato. Se non ha trovato volti, Blurry chiede prima.

Tutti i file della sessione sono in Vista › Coda (⌘L). Una breve guida accompagna il primo file
(Aiuto › Rivedi la guida).

**Su Windows e Linux**, lancia `blurry` senza argomenti (oppure `blurry-app`) per aprire l'app
installata con Python:

1. **Trascina** foto e video nella finestra, oppure usa *Scegli file…*. Ogni file si analizza in
   un processo separato; niente esce dal tuo computer.
2. **Rivedi** i file. I riquadri trovati dal rilevatore sono gialli, quelli che aggiungi tu verde
   acqua. Trascina su un'area vuota per aggiungere un riquadro, trascina un riquadro per spostarlo,
   i suoi angoli per ridimensionarlo, premi Canc per eliminarlo. *Anteprima del risultato* mostra
   esattamente quello che verrà esportato.
   Nei video scorri la linea del tempo (i momenti incerti sono segnati in rosso), spegni una
   traccia che non è un volto, o disegna un riquadro che copre un'area per un intervallo di tempo.
3. **Esporta.** Se in un file non c'è nessun volto e non ne hai aggiunti, Blurry chiede conferma.

Le due app ricordano solo poche impostazioni (sensibilità, copertura, margine, lingua e, su Mac,
se la guida è già stata vista): mai nomi di file, cartelle o file recenti. L'app Qt usa un suo
selettore di file, perché i dialoghi di Qt tengono un elenco delle cartelle recenti; l'app per Mac
usa i pannelli del sistema e toglie quello che registrano appena si chiudono.

## Uso

```bash
blurry foto.jpg
```

scrive `foto.blurry.jpg` accanto all'originale.

```bash
blurry IMG_0001.HEIC clip.mov -o ~/Desktop/puliti
```

scrive `IMG_0001.blurry.jpg` e `clip.blurry.mp4` in `~/Desktop/puliti`.

```
blurry INPUT... [-o CARTELLA] [--level base|medium|high] [--mode solid|pixel]
    [--padding 0.25] [--keep-audio] [--no-faces] [--watermark TESTO]
    [--strict] [--json] [--debug]
```

| Opzione | Significato | Default |
|---|---|---|
| `-o CARTELLA` | Dove scrivere i file | accanto a ogni originale |
| `--level` | Sensibilità: `base` (solo volti evidenti e frontali), `medium`, `high` (anche volti piccoli o in parte nascosti) | `high` |
| `--mode` | Rettangolo nero `solid` o pixelazione `pixel` | `solid` |
| `--padding` | Margine attorno a ogni volto, in frazione del lato lungo, per ogni lato | `0.25` |
| `--keep-audio` | Tiene la traccia audio (ricodificata in AAC) | audio tolto |
| `--no-faces` | Toglie solo i metadati, non copre niente | |
| `--watermark TESTO` | Aggiunge una filigrana di testo | spenta |
| `--strict` | Se un file non ha volti, non scrive niente ed esce con codice 2 | |
| `--json` | Stampa su stdout un resoconto JSON per ogni file | |
| `--debug` | Messaggi di debug su stderr | spento |

**File accettati.** Foto: JPEG, PNG, WebP (statico), HEIC/HEIF. Video: MP4, MOV, M4V, MKV, WebM,
AVI. GIF e immagini animate si rifiutano. Le foto escono in JPEG (il PNG resta PNG); i video in
MP4 (H.264).

**Codici di uscita.** `0` tutto bene · `1` un errore · `2` nessun volto con `--strict`.

L'avanzamento va su stderr come righe `__PROGRESS__ {json}`, per script e integrazioni.

## Verificare quello che scarichi

Ogni release su GitHub ha un file `SHA256SUMS`, un SBOM CycloneDX e un'attestazione GitHub di
provenienza per ogni file, che dimostra che è stato costruito dal workflow di rilascio di questa
repository.

- macOS / Linux, nella cartella dei file scaricati:

  ```bash
  shasum -a 256 -c SHA256SUMS
  ```

- Windows (confronta il risultato con la riga in `SHA256SUMS`):

  ```
  CertUtil -hashfile <file> SHA256
  ```

- Provenienza, con la [GitHub CLI](https://cli.github.com/):

  ```bash
  gh attestation verify <file> --repo Chrono-Web/BLURRY
  ```

Il pacchetto su PyPI si pubblica dallo stesso workflow con Trusted Publishing (senza token), e PyPI
ne mostra la provenienza nella pagina del progetto.

## Limiti noti

- Volti di profilo, al buio, molto piccoli o girati di lato possono sfuggire (vedi sopra).
- I video HDR del telefono (HEVC a 10 bit) escono in H.264 SDR a 8 bit: i colori possono sembrare
  più spenti.
- Su macOS, elaborando un video compare un avviso innocuo `objc ... implemented in both`, perché
  OpenCV e PyAV portano ciascuno la propria copia di FFmpeg.

## Licenza

Blurry ha licenza MIT. Il pacchetto su PyPI contiene solo il codice di Blurry, il modello YuNet
(MIT) e il font Geist (OFL). L'app per Mac (`Blurry.dmg`) contiene anche FFmpeg con **x264 e x265,
che sono GPL-2.0-or-later**, e il bootloader di PyInstaller (GPL-2.0 con un'eccezione per i
programmi che avvia): in [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) trovi tutte le
licenze e i sorgenti esatti.
