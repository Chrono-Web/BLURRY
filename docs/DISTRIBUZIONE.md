# Distribuzione desktop e verifiche

Aggiornato: 2026-10-04. Versione sorgente preparata: **0.1.2**, non pubblicata.
La richiesta estende i pacchetti pronti oltre macOS.
Python rimane pienamente supportato: vedi [contratto CLI](CLI_CONTRACT.md).

## Formati scelti

| Sistema | Formato / installazione | Stato |
|---|---|---|
| macOS 14+, Apple Silicon | `Blurry.dmg`, SwiftUI con motore congelato | distribuzione esistente preservata |
| Windows 11 x64 | `Blurry-<versione>-windows-x64-setup.exe`, Inno Setup, per utente senza amministratore | [x] costruito e provato su runner Windows Server 2025; desktop Windows 11 reale da verificare |
| Ubuntu 24.04 desktop x86-64 | `Blurry-<versione>-linux-x86_64.tar.gz`, `sh install.sh`, per utente | [x] costruito e provato in Ubuntu 24.04 pulito, senza Python né rete; desktop reale da verificare |
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
Il test Windows usa il runtime incorporato con PATH limitato alle directory di
sistema e senza PYTHONHOME/PYTHONPATH/VIRTUAL_ENV, ma il runner contiene Python
e strumenti di sviluppo: non equivale a una macchina Windows pulita. Il container Linux runtime
non ha Python, checkout o rete e prova Qt con Xvfb. CI non sostituisce una prova
interattiva su Windows 11 e Ubuntu con desktop reali.

Il workflow release riusa lo stesso job sul tag, mantiene wheel/sdist, SBOM e DMG,
e aggiunge gli installer, SBOM con Qt, SHA256SUMS complessivo e attestazioni GitHub.
La pubblicazione GitHub è bloccata se uno dei build/test dei pacchetti fallisce.
I workflow CI sono stati eseguiti e hanno generato i pacchetti; nessuna release è
stata pubblicata. Gli artefatti verificati sono scaricabili dai run della
[PR #2](https://github.com/Chrono-Web/BLURRY/pull/2). I link `releases/latest` ai
nuovi installer saranno validi solo dopo la pubblicazione di una release.
La CI attesta i pacchetti dei branch interni dopo i test; le PR da fork non
richiedono permessi di attestazione. Il workflow release attesta anche l’insieme
completo di file pubblicati.

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
- [x] Build installer Windows x64 e archivio Linux x86-64 in GitHub Actions.
- [x] Windows installato: CLI, GUI e worker congelati, foto/video, revisione manuale,
  IT/EN, onboarding, impostazioni, aggiornamento che conserva le preferenze,
  disinstallazione e reinstallazione. Runner Windows Server 2025, UI offscreen.
- [x] Linux runtime pulito senza Python, checkout o rete: CLI e GUI sotto Xvfb,
  foto/video, revisione manuale, IT/EN, onboarding, impostazioni, aggiornamento,
  disinstallazione e reinstallazione. Utente non privilegiato in Ubuntu 24.04.
- [x] Suite del codice su Windows Server 2022, Ubuntu 24.04 e macOS 14; suite Linux
  anche con rete disabilitata; wheel base senza Qt e wheel con extra GUI.
- [x] Primo run completo: [37205750933](https://github.com/Chrono-Web/BLURRY/actions/runs/37205750933).
- [x] Run con pipe UTF-8, percorsi Unicode, PATH Windows isolato e attestazioni:
  [37206055793](https://github.com/Chrono-Web/BLURRY/actions/runs/37206055793).
- [x] Checksum dei pacchetti scaricati controllati localmente; modello YuNet nel
  pacchetto Linux verificato con SHA-256. Audit del bundle Linux: 84 testi di
  licenza/avvisi, manifest nativo con Python 3.12.3 e OpenCV 5.0.0.93.
  Il ramo include l’aggiornamento OpenCV già approvato su main; nessun downgrade.
- [ ] Sessione desktop Windows 11 pulita, senza Python: SmartScreen, avvio dal menu,
  foto/HEIC/video, revisione, IT/EN, impostazioni, aggiornamento, disinstallazione,
  reinstallazione e onboarding.
- [ ] Sessione Ubuntu 24.04 pulita, senza Python, su X11 e Wayland: stessi scenari,
  nomi di cartelle con spazi/Unicode, launcher e disinstallazione esterna.

Docker Desktop locale non riesce ad avviarsi. Dopo il login GitHub CLI sono stati
usati i runner nativi: i binari Windows/Linux provengono dalla CI, non dal bundle
Qt Mac di prova. Non sono stati pubblicati su una release o su PyPI.

Gli artefatti locali non hanno attestazioni GitHub: queste vengono generate solo
nel workflow remoto. I checksum locali sono in `build/python-dist/SHA256SUMS`.
La versione 0.1.2 è allineata in pyproject, `blurry_opsec.__version__`, lock e
Info.plist macOS. La release pubblica corrente resta 0.1.1; i suoi tag e pacchetti
non includono le modifiche di questo ramo. Non rinominare i vecchi artefatti 0.1.1:
per 0.1.2 servono nuovi build. La verifica del DMG è obbligatoria anche nel workflow
di release. Vedi [prove desktop da completare](VERIFICA_DESKTOP.md).
