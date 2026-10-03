# Threat model

[Italiano](THREAT_MODEL.it.md)

Blurry helps you share a photo or video **without revealing who is in it or where and when it was
taken through its metadata**. This page says what it protects against and, more importantly, what
it does not.

## What Blurry protects

- **Faces the detector finds**, covered with a solid black box by default. A solid box cannot be
  "un-blurred"; pixelation (`--mode pixel`) is weaker and should be used only when that is enough.
- **Metadata**: GPS position, camera and phone model, serial numbers, dates, software, the EXIF
  thumbnail (which can contain the uncovered original), XMP, IPTC, colour profiles, video
  location and device tags, chapters, subtitles, data tracks and cover art.
- **Your files staying on your computer**: Blurry has no network code, blocks network sockets in
  its own process, and stops FFmpeg from opening anything but local files. It writes nothing but
  the output you asked for: no logs with file names, no temporary copies of your media.
- **A tampered detector**: the model's SHA-256 is checked on every start; there is no silent
  fallback to a weaker detector.

## What Blurry does NOT protect

- **Faces the detector misses.** Faces in profile, in the dark, very small, blurred by motion,
  partly hidden or turned sideways can be missed. Look at every result before sharing it, and
  check the files listed under `flags`.
- **Everything except faces**: body shape, clothes, tattoos, scars, shoes, bags, gait and posture
  in videos, hands and rings.
- **Voices**, if you keep the audio (`--keep-audio`). Audio is removed by default for this reason.
- **Places and background**: buildings, street signs, shop names, landscapes, the sky, licence
  plates, and anything visible in **reflections** (windows, glasses, eyes, puddles).
- **Text in the picture**: badges, name tags, screens, documents.
- **The camera's sensor fingerprint** (PRNU): the tiny noise pattern of a sensor can link several
  photos to the same camera, even without metadata.
- **Who shot it, from context**: the angle, the moment, and who could have been standing there.
- **A computer that is already compromised.** If someone controls your device, they can see the
  originals.

## The original is still there

Blurry never deletes or changes the original. After you have checked the result:

1. **Delete the original** if you no longer need it, and empty the trash.
2. **Check synced copies**: if the photo or video was synced to **iCloud Photos**, **Google
   Photos**, OneDrive, Dropbox or a messaging app backup, the original is also there. Delete it
   from those services too (and from their "recently deleted" folders).
3. **Encrypt your disk**: **FileVault** on macOS, **BitLocker** (or Device Encryption) on Windows,
   **LUKS** on Linux. Deleted files can be recovered from an unencrypted disk.

## Where the files go

Blurry writes the output next to the original, or in the folder you choose with `-o`. While a file
is being written it is called `.<name>.blurry-partial` and is renamed at the end; if something
fails, the partial file is removed.

## Reporting a problem

If you find a way in which Blurry leaks something it claims to remove, please report it privately:
see [SECURITY.md](SECURITY.md).
