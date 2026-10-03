# Security policy

[Italiano in fondo](#italiano)

## Reporting a vulnerability

**Please do not open a public issue for security problems.** Use GitHub's private vulnerability
reporting: on <https://github.com/Chrono-Web/BLURRY>, go to **Security → Report a vulnerability**.

Especially welcome:

- metadata that survives in an output file (with the input that causes it, or how to build one);
- any way to make Blurry open a network connection or read something other than the given file;
- files left on disk besides the chosen output (temporary files, logs, caches, recent folders);
- crashes or hangs on crafted input files;
- problems in the release process (checksums, attestations, the PyPI package).

Please do **not** send media of real people: describe the problem or build a test file from public
domain material.

We aim to acknowledge reports within 7 days and to publish a fix and an advisory as soon as one
is ready. Reporters are credited unless they prefer otherwise.

## Supported versions

Only the latest release receives security fixes.

## Scope

Faces the detector misses are a known limit, described in the [threat model](THREAT_MODEL.md),
not a vulnerability; reports that help improve detection are still welcome as ordinary issues
(without real people's media).

---

## Italiano

### Segnalare una vulnerabilità

**Non aprire issue pubbliche per i problemi di sicurezza.** Usa la segnalazione privata di GitHub:
su <https://github.com/Chrono-Web/BLURRY>, vai in **Security → Report a vulnerability**.

Sono benvenute soprattutto:

- metadati che restano in un file di output (con il file che li provoca, o come costruirne uno);
- qualsiasi modo per far aprire a Blurry una connessione di rete o leggere qualcosa di diverso dal
  file indicato;
- file lasciati sul disco oltre all'output scelto (file temporanei, log, cache, cartelle recenti);
- crash o blocchi con file costruiti apposta;
- problemi nel processo di rilascio (checksum, attestazioni, pacchetto PyPI).

**Non** mandare media di persone reali: descrivi il problema o costruisci un file di prova con
materiale di pubblico dominio.

Cerchiamo di rispondere entro 7 giorni e di pubblicare la correzione e un avviso appena sono
pronti. Chi segnala viene citato, a meno che preferisca di no.

### Versioni supportate

Solo l'ultima release riceve correzioni di sicurezza.

### Ambito

I volti che il rilevatore non trova sono un limite noto, descritto nel [modello delle
minacce](THREAT_MODEL.it.md), non una vulnerabilità; le segnalazioni che aiutano a migliorare il
rilevamento sono comunque benvenute come issue normali (senza media di persone reali).
