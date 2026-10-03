# Contributing

[Italiano in fondo](#italiano)

Thank you for helping. Blurry is small on purpose; its promises (offline, nothing left on disk,
metadata always removed, no silent fallbacks) matter more than features.

## Ground rules

- **No network code**, ever: no telemetry, update checks, crash reports or downloads. No servers or
  listening ports, not even local ones.
- **No silent fallbacks** to a weaker detector, another format or other settings.
- **Never overwrite an original**, never write paths or file names outside the chosen output.
- **No media of real people** in the repository, unless public domain or CC0 with the source
  recorded in `tests/fixtures/public/SOURCES.md`. Real media for local testing go in
  `tests/fixtures/private/`, which git ignores.
- **Check the licence of every new dependency.** Blurry's code stays MIT; anything GPL must be
  declared in `THIRD_PARTY_LICENSES.md`.
- Code, comments and commit messages in English. User-facing documentation in English and
  Italian.

## Development

You need [uv](https://docs.astral.sh/uv/) and, for the full test suite, `ffmpeg`, `ffprobe` and
`exiftool` (test tools only; Blurry never calls them).

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

`uv run blurry --help` runs the command from your checkout.

The recall test (`tests/test_image.py::test_recall_does_not_regress`) fails if detection gets
worse on the annotated public corpus. If a change improves recall, raise the floor in the same
pull request.

The baseline against the original OPSEC engine (`tests/test_baseline.py`) only runs when
`BLURRY_BASELINE_PYTHON` and `BLURRY_BASELINE_SCRIPT` are set.

## Pull requests

Keep them focused, with tests for new behaviour. CI runs lint and tests on macOS, Windows and
Linux, plus the whole suite in a Linux container with no network.

---

## Italiano

Grazie dell'aiuto. Blurry è piccolo apposta: le sue promesse (senza rete, niente tracce sul disco,
metadati sempre tolti, nessun ripiego silenzioso) contano più delle funzioni.

### Regole di base

- **Nessun codice di rete**, mai: niente telemetria, controllo degli aggiornamenti, invio dei crash
  o download. Niente server né porte in ascolto, nemmeno locali.
- **Nessun ripiego silenzioso** su un rilevatore più debole, un altro formato o altre impostazioni.
- **Mai sovrascrivere un originale**, mai scrivere percorsi o nomi di file fuori dall'output scelto.
- **Nessun media di persone reali** nella repository, salvo pubblico dominio o CC0 con la fonte
  registrata in `tests/fixtures/public/SOURCES.md`. I media reali per le prove in locale vanno in
  `tests/fixtures/private/`, che git ignora.
- **Controlla la licenza di ogni nuova dipendenza.** Il codice di Blurry resta MIT; ogni componente
  GPL va dichiarato in `THIRD_PARTY_LICENSES.md`.
- Codice, commenti e messaggi di commit in inglese. Documentazione per gli utenti in inglese e in
  italiano.

### Sviluppo

Serve [uv](https://docs.astral.sh/uv/) e, per tutti i test, `ffmpeg`, `ffprobe` ed `exiftool`
(servono solo ai test; Blurry non li chiama mai).

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

`uv run blurry --help` esegue il comando dalla tua copia.

Il test di recall (`tests/test_image.py::test_recall_does_not_regress`) fallisce se il rilevamento
peggiora sul corpus pubblico annotato. Se una modifica migliora la recall, alza la soglia nella
stessa pull request.

La baseline contro il motore OPSEC originale (`tests/test_baseline.py`) gira solo se sono
impostate `BLURRY_BASELINE_PYTHON` e `BLURRY_BASELINE_SCRIPT`.

### Pull request

Mantienile mirate, con i test per i comportamenti nuovi. La CI esegue lint e test su macOS, Windows
e Linux, più l'intera suite in un container Linux senza rete.
