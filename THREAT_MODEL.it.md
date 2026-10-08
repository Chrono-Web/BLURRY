# Modello delle minacce

[English](THREAT_MODEL.md)

Blurry ti aiuta a condividere una foto o un video **senza rivelare chi c'è dentro, né dove e quando
è stato fatto attraverso i metadati**. Questa pagina dice da che cosa protegge e, soprattutto, da
che cosa no.

## Che cosa protegge

- **I volti che il rilevatore trova**, coperti di default da un rettangolo nero pieno. Un
  rettangolo pieno non si può "togliere"; la pixelazione (`--mode pixel`) è più debole e va usata
  solo quando basta.
- **I metadati**: posizione GPS, modello di fotocamera e telefono, numeri di serie, date,
  software, la miniatura EXIF (che può contenere l'originale scoperto), XMP, IPTC, profili colore,
  luogo e dispositivo nei video, capitoli, sottotitoli, tracce dati e copertine.
- **I tuoi file restano sul tuo computer**: Blurry non contiene codice di rete, blocca i socket di
  rete nel proprio processo e impedisce a FFmpeg di aprire qualsiasi cosa che non sia un file
  locale. Non scrive niente oltre al file che hai chiesto: niente log con i nomi dei file, niente
  copie temporanee dei tuoi media.
- **Un rilevatore manomesso**: lo SHA-256 del modello si controlla a ogni avvio; non c'è nessun
  ripiego silenzioso su un rilevatore più debole.

## Che cosa NON protegge

- **I volti che il rilevatore non trova.** Volti di profilo, al buio, molto piccoli, mossi, in
  parte nascosti o girati di lato possono sfuggire. Guarda ogni risultato prima di condividerlo, e
  controlla i file elencati sotto `flags`.
- **Tutto quello che non è un volto**: corporatura, vestiti, tatuaggi, cicatrici, scarpe, borse,
  andatura e postura nei video, mani e anelli.
- **Le voci**, se tieni l'audio (`--keep-audio`). Per questo l'audio si toglie di default.
- **Luoghi e sfondo**: edifici, cartelli stradali, insegne, paesaggi, il cielo, targhe, e tutto
  quello che si vede nei **riflessi** (vetrine, occhiali, occhi, pozzanghere).
- **Il testo nell'immagine**: tesserini, cartellini col nome, schermi, documenti.
- **L'impronta del sensore della fotocamera** (PRNU): il rumore minuscolo di un sensore può
  collegare più foto alla stessa fotocamera, anche senza metadati.
- **Chi ha scattato, dal contesto**: l'angolazione, il momento, chi poteva trovarsi lì.
- **Un computer già compromesso.** Se qualcuno controlla il tuo dispositivo, può vedere gli
  originali.

## L'originale è ancora lì

Blurry non cancella e non modifica mai l'originale. Dopo aver controllato il risultato:

1. **Cancella l'originale** se non ti serve più, e svuota il cestino.
2. **Controlla le copie sincronizzate**: se la foto o il video sono finiti su **Foto di iCloud**,
   **Google Foto**, OneDrive, Dropbox o nel backup di un'app di messaggi, l'originale è anche lì.
   Cancellalo anche da quei servizi (e dalle loro cartelle "eliminati di recente").
3. **Cifra il disco**: **FileVault** su macOS, **BitLocker** (o Crittografia dispositivo) su
   Windows, **LUKS** su Linux. Da un disco non cifrato i file cancellati si possono recuperare.

## Dove finiscono i file

Blurry scrive il risultato accanto all'originale, o nella cartella che scegli con `-o`. Mentre lo
scrive, il file si chiama `.<nome>.blurry-partial` e alla fine viene rinominato; se qualcosa va
storto, il file parziale viene cancellato.

## iPhone e iPad

L'app iOS ha un motore suo, scritto in Swift. A ogni modifica la CI lo
confronta con quello desktop: stessi riquadri, stessa copertura, stessi metadati tolti. Le regole
qui sopra valgono, con queste differenze:

- **Niente rete, ma senza blocco dei socket.** L'app non ha codice di rete e non è collegata a
  nessun framework di rete (lo si controlla ogni volta che si costruisce l'`.ipa`), ma iOS non
  permette a un'app di vietarsi la rete come fa il motore desktop bloccando i socket nel proprio
  processo.
- **Solo le foto che scegli.** Le foto arrivano dal selettore di sistema, che dà a Blurry le foto
  scelte e nient'altro della libreria: Blurry non chiede mai l'accesso alla libreria. I file
  aperti da un'altra app vengono copiati da iOS nella cartella Inbox di Blurry; Blurry li legge in
  memoria e cancella subito la copia.
- **Dove va il file pulito.** In File, o a un'altra app con il foglio di condivisione. «Salva
  immagine» è tolto apposta dal foglio: salvare in Foto manda il file anche su Foto di iCloud, se
  lo usi.
- **Il selettore delle app.** Quando Blurry non è sullo schermo, un velo lo copre: l'istantanea
  che iOS conserva per il selettore delle app non mostra mai una foto scoperta.
- **Che cosa resta sul dispositivo.** Solo le impostazioni (sensibilità, copertura, margine) e se
  hai visto la guida. Le copie lasciate dai selettori vengono cancellate all'avvio e ogni volta
  che Blurry esce dallo schermo.
- **I video si copiano mentre ci lavori.** Un video è troppo grande per stare in memoria: finché è
  nella coda di Blurry, una copia sta nella cartella temporanea privata dell'app, protetta dalla
  cifratura del dispositivo. La copia si cancella quando togli il video dalla coda, e a ogni avvio
  di Blurry. Il file pulito resta nella stessa cartella solo finché il foglio di salvataggio o di
  condivisione non si chiude.
- **Video: solo MP4, MOV e M4V.** iOS non legge MKV, WebM e AVI. I video HDR dell'iPhone escono in
  SDR, convertiti come sul desktop.
- **In secondo piano.** Da iOS 26, un'analisi o l'esportazione di un video continua anche se
  esci da Blurry, se iOS concede il tempo: l'avanzamento compare nella schermata di blocco e nella
  Dynamic Island, senza nomi di file. Altrimenti, e prima di iOS 26, il lavoro si ferma e riparte
  quando torni.
- **L'originale resta nella libreria**, e su Foto di iCloud se lo usi: vedi «L'originale è ancora
  lì», e ricorda l'album «Eliminati di recente».
- **Installazione non firmata.** L'`.ipa` non è firmata da Apple: AltStore o SideStore la firmano
  con il tuo Apple ID. Controllala con `SHA256SUMS` e `gh attestation verify` prima di
  installarla (vedi il README).

## Segnalare un problema

Se trovi un modo in cui Blurry lascia passare qualcosa che dice di togliere, segnalalo in privato:
vedi [SECURITY.md](SECURITY.md).
