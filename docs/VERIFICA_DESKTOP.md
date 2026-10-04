# Verifica interattiva prima della pubblicazione

Aggiornato: 2026-10-04. Versione in prova: 0.1.2b1, pubblicata come beta.
*(2026-10-04: dopo la 0.1.2b1 l'interfaccia Qt è stata rifatta sul modello dell'app per Mac;
gli scenari 2 e 4 vanno provati sulla prima build che la contiene.)*
Sistemi supportati, dipendenze e risultati automatici vivono in
[DISTRIBUZIONE.md](DISTRIBUZIONE.md). Questa procedura serve per le prove mancanti.

## Ambiente

Usare un account di prova su Windows 11 x64 e Ubuntu 24.04 desktop x86-64,
senza Python installato. Su Ubuntu ripetere la sessione su X11 e Wayland.
Non usare la VPS `ssh chrono`: è Debian 12 senza desktop e ospita servizi condivisi;
il collaudo desktop richiede una macchina diversa. Il 2026-10-04 è stato preparato
un runtime headless per il backend Chrono, collaudato su una foto pubblica prima del
deploy. Questa prova non verifica GUI o installer Linux e non usa container.
Vedi anche il documento operativo in SITO/BACKEND/docs/BLURRY.md.

Scaricare i pacchetti dalla pre-release v0.1.2b1 e verificare il checksum
prima di installarli. Conservare commit, versione, checksum, versione del sistema
e tipo di sessione nel verbale. Usare immagini pubbliche o sintetiche e un breve
video sintetico; evitare dati personali nelle schermate o nelle segnalazioni.

## Scenari

1. Installare con un utente normale e aprire Blurry dal menu applicazioni.
   Registrare gli avvisi effettivi del sistema (incluso SmartScreen su Windows).
2. Verificare che l'introduzione appaia al primo avvio, che si possa completare e
   richiamare (Aiuto › Rivedi la guida), e che i tre suggerimenti accompagnino il
   primo file; chiudere e riaprire: l'introduzione non deve ripartire da sola.
3. Passare fra italiano e inglese nelle impostazioni, inclusi i pulsanti dei
   dialoghi standard. Cambiare sensibilità, copertura e margine, riaprire e
   verificare la persistenza; provare il ripristino delle impostazioni consigliate.
4. Elaborare JPEG, HEIC e un video con audio da una cartella con spazi e Unicode.
   Correggere manualmente un riquadro nella foto e una traccia/intervallo nel video.
   Controllare l'anteprima prima di esportare (il video si riproduce coperto);
   «Esporta…» deve partire dalla cartella dell'originale con `<nome>_blurry`.
   Poi aprire i risultati con un'altra applicazione. Confermare la rimozione di metadati e audio secondo le opzioni
   scelte, e confrontare i checksum degli originali prima e dopo.
5. Provare un file senza volti: l'esportazione deve richiedere la conferma prevista.
   Provare un file corrotto e annullare un'elaborazione: l'interfaccia deve restare
   utilizzabile e non presentare un risultato parziale come completato.
6. Aprire il pannello aggiornamenti: mostra la versione, senza richieste di rete
   automatiche. L'apertura del browser deve avvenire soltanto premendo il pulsante.
7. Chiudere e reinstallare sopra la stessa versione: le preferenze devono restare.
8. Disinstallare completamente dalle impostazioni. Verificare la rimozione
   dell'app, del launcher e delle preferenze, preservando originali ed esportazioni.
   Su Linux provare anche la rimozione esterna con l'app chiusa.
9. Reinstallare e aprire dal menu: deve ripartire l'onboarding.
10. Eseguire `blurry-engine --version` e una chiamata con argomenti, `--json` e
    stdin chiuso: nessuna finestra, guida o interazione. Il contratto completo è
    in [CLI_CONTRACT.md](CLI_CONTRACT.md).

## Verbale

Per ogni sistema annotare data, commit, versione, SHA-256 del pacchetto, sessione
(X11/Wayland se applicabile), scenari superati e difetti con passi riproducibili.
Una prova offscreen o Xvfb non chiude questa verifica. Le caselle dei desktop reali
in DISTRIBUZIONE.md restano aperte finché il verbale non documenta i risultati.
