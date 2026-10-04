# Distribuzione desktop e verifiche

Aggiornato: 2026-10-04. La richiesta estende i pacchetti pronti oltre macOS.
Python rimane pienamente supportato: vedi [contratto CLI](CLI_CONTRACT.md).

## Formati scelti

| Sistema | Formato / installazione | Stato |
|---|---|---|
| macOS 14+, Apple Silicon | `Blurry.dmg`, SwiftUI con motore congelato | distribuzione esistente preservata |
| Windows 11 x64 | `Blurry-<versione>-windows-x64-setup.exe`, Inno Setup, per utente senza amministratore | [~] implementato, da costruire e provare su Windows |
| Ubuntu 24.04 desktop x86-64 | `Blurry-<versione>-linux-x86_64.tar.gz`, `sh install.sh`, per utente | [~] implementato, da costruire e provare su Linux |
| Server/container/pipeline con Python 3.12 | `blurry-opsec` su PyPI, CLI senza Qt; extra `[gui]` facoltativo | supporto preservato e contratti testati |

Nessuna promessa di compatibilità con Windows ARM, Windows 10, Linux ARM, altre
versioni di Ubuntu o altre distribuzioni. La matrice indica i target, non certifica
verifiche ancora non eseguite. I build PyInstaller sono nativi: un eseguibile Mac
non si converte in un eseguibile Windows/Linux.

Windows: `%LOCALAPPDATA%\Programs\Blurry`, menu Start e disinstallatore registrato.
Linux: `~/.local/opt/blurry`, launcher `~/.local/share/applications/blurry.desktop`.
La cartella del programma resta separata da originali ed esportazioni. Il modello,
Python 3.12, librerie di elaborazione, Qt, font, licenze e metadati delle dipendenze
sono inclusi. Non servono pip, Python o ffmpeg esterni. `blurry-engine[.exe]` nello
stesso pacchetto espone la CLI per eventuali automazioni.

Qt su Linux usa le librerie desktop del sistema. Su Ubuntu 24.04 desktop sono
richiesti `libegl1 libgl1 libxkbcommon0 libfontconfig1 libdbus-1-3 libglib2.0-0
libxcb-cursor0 libxkbcommon-x11-0 libxcb-icccm4 libxcb-keysyms1 libxcb-shape0
libxcb-xinerama0`. Se mancano, installarle con apt prima di aprire Blurry. Non
chiamare il pacchetto universalmente portabile. Il test in container installa solo
queste librerie, font e Xvfb; nessun Python. Wayland e X11 reali restano da verificare.

## Installazione, aggiornamento e rimozione

Windows: eseguire l’installer. Linux: estrarre l’archivio e lanciare `sh install.sh`
dalla cartella `Blurry-linux`; aprire poi Blurry dal menu applicazioni.
Chiudere Blurry prima di installare una nuova versione sopra la precedente:
l’aggiornamento mantiene le cinque preferenze consentite, senza salvare cronologie.
L’app non verifica aggiornamenti e non scarica file. Impostazioni → Aggiornamenti
mostra versione e istruzioni; solo il pulsante esplicito apre il browser esterno.

Disinstallare dalle Impostazioni. Windows avvia il disinstallatore di Inno Setup
(disponibile anche in Impostazioni Windows → App); questo cancella solo il dominio
HKCU `Software\chronocol.com\blurry` oltre ai file installati. Linux avvia
`~/.local/opt/blurry/uninstall.sh`, dopo la conferma e senza lavori in corso; il
helper attende la chiusura dell’app, poi rimuove cartella, launcher e
`${XDG_CONFIG_HOME:-~/.config}/chronocol.com/blurry.conf`. Lo stesso script si può
eseguire dall’esterno con l’app chiusa. La reinstallazione completa riparte dalla
guida. Una rimozione manuale della sola cartella dell’app lascia le preferenze.
Non cambiare XDG_CONFIG_HOME fra uso e disinstallazione se si vuole rimuovere lo
stesso archivio di preferenze. Nessun file scelto o esportato viene cancellato.

## Build e release

Su un host nativo x64 del target, dalla root della repo:

```sh
uv sync --frozen --no-dev --extra gui --group packaging
uv run --frozen --no-dev --extra gui --group packaging python scripts/build-desktop.py
```

Windows richiede Inno Setup 6 (`ISCC` nel PATH o nel percorso standard).
Gli output e checksum individuali sono in `build/desktop-packages/`.
Il bundle è onedir: DLL/librerie Qt rimangono sostituibili e le licenze sono
accessibili senza estrarre un eseguibile monolitico. `THIRD_PARTY/` contiene gli
avvisi effettivamente forniti dalle wheel; `dependencies.json` registra le versioni
native risolte. Vedi [licenze](../THIRD_PARTY_LICENSES.md) per i sorgenti.

La CI chiama `desktop.yml` su Windows Server 2025 x64 e Ubuntu 24.04 x64:
compila, installa, prova app e worker congelati, aggiorna, disinstalla e reinstalla.
Il test Windows usa il runtime incorporato, ma il runner contiene Python e strumenti
di sviluppo: non equivale a una macchina Windows pulita. Il container Linux runtime
non ha Python, checkout o rete e prova Qt con Xvfb. CI non sostituisce una prova
interattiva su Windows 11 e Ubuntu con desktop reali.

Il workflow release riusa lo stesso job sul tag, mantiene wheel/sdist, SBOM e DMG,
e aggiunge gli installer, SBOM con Qt, SHA256SUMS complessivo e attestazioni GitHub.
La pubblicazione GitHub è bloccata se uno dei build/test dei pacchetti fallisce.
Non abbiamo pubblicato release né eseguito i workflow remoti in questa sessione.
I link ai nuovi installer saranno validi solo quando una release li avrà generati.

## Verifiche realmente eseguite in questa sessione

- [x] Suite Python locale su macOS, inclusi rete bloccata, immagini, video e GUI offscreen.
- [x] Tre test Swift di lifecycle macOS, inclusa rimozione di un bundle temporaneo.
- [x] DMG macOS 0.1.1 esistente: struttura, firma ad-hoc, layout e versione del motore.
- [x] Wheel e sdist PyPI costruite; wheel installata in due ambienti separati,
  base senza PySide6 e con extra GUI: sette test di contratto CLI per ambiente.
- [x] Esempio Node con motore congelato: successo, report, avanzamento ed errore.
- [x] Congelamento Qt/engine sul Mac e smoke del bundle, senza usare Python esterno.
- [x] Script installer Linux in HOME temporanea: installazione, aggiornamento,
  rimozione delle preferenze e reinstallazione; originali preservati (eseguito su macOS).
- [x] Contratti CLI: stdin chiuso, display Qt invalido, JSON Lines, avanzamento,
  strict e codici di uscita, con l’extra Qt installato.
- [~] Build installer Windows x64 e archivio Linux x86-64: ricette e CI pronte,
  binari di questi target non generati su questo Mac.
- [~] Prove Windows installato e Linux runtime senza rete: script pronti, da eseguire.
- [ ] Sessione desktop Windows 11 pulita, senza Python: SmartScreen, avvio dal menu,
  foto/HEIC/video, revisione, IT/EN, impostazioni, aggiornamento, disinstallazione,
  reinstallazione e onboarding.
- [ ] Sessione Ubuntu 24.04 pulita, senza Python, su X11 e Wayland: stessi scenari,
  nomi di cartelle con spazi/Unicode, launcher e disinstallazione esterna.

Blocchi dell’ambiente locale: Docker Desktop non riesce ad avviarsi; `gh auth status`
segnala credenziali non valide. Non si possono quindi produrre/verificare qui i due
binari nativi né attestazioni autentiche di release. Un pacchetto di sorgenti o il
bundle Qt Mac di prova non sono installer Windows/Linux.

Gli artefatti locali non hanno attestazioni GitHub: queste vengono generate solo
nel workflow remoto. I checksum locali sono in `build/python-dist/SHA256SUMS`.
Prima del prossimo rilascio aggiornare coerentemente la versione in pyproject,
`blurry_opsec.__version__` e il lock, poi creare un nuovo tag: i tag esistenti non
includono le modifiche non pubblicate di questa sessione.
