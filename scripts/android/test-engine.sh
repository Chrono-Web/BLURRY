#!/bin/zsh
# Test del motore Android (android/engine) contro il motore Python: prima il
# riferimento (riferimento.py scrive build/parity/), poi i test strumentali su
# un emulatore o un telefono collegato, infine exiftool sui file scritti dal
# motore. Servono exiftool e ffmpeg (brew install exiftool ffmpeg) e un
# dispositivo arm64: un telefono collegato, un emulatore acceso o, se non c'è
# niente, l'AVD blurry36, che lo script accende e poi spegne.
#
#   scripts/android/test-engine.sh
set -euo pipefail

ROOT=${0:A:h:h:h}
cd "$ROOT"
export ANDROID_HOME=${ANDROID_HOME:-$HOME/Library/Android/sdk}
ADB=$ANDROID_HOME/platform-tools/adb
# Without a phone or a running emulator, start the AVD (BLURRY_AVD, default
# blurry36) headless and stop it at the end.
STARTED=""
if [[ -z "$($ADB devices | sed -n '2,$p' | grep -w device)" ]]; then
  AVD=${BLURRY_AVD:-blurry36}
  $ANDROID_HOME/emulator/emulator -list-avds | grep -qx "$AVD" || { echo "nessun dispositivo per adb e nessun AVD $AVD"; exit 1; }
  echo "avvio l'emulatore $AVD"
  $ANDROID_HOME/emulator/emulator -avd "$AVD" -no-window -no-audio -no-boot-anim -no-snapshot-save >/dev/null 2>&1 &
  STARTED=1
  $ADB wait-for-device
  until [[ "$($ADB shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" == 1 ]]; do sleep 2; done
fi
stop_emulator() { [[ -n "$STARTED" ]] && $ADB emu kill >/dev/null 2>&1 || true; }
trap stop_emulator EXIT

uv run --frozen python scripts/coreml/riferimento.py
(cd android && ./gradlew --quiet :engine:connectedDebugAndroidTest)

# R3: exiftool on what the engine wrote (ImageTest.outputsHoldNoMetadata).
# Gradle uninstalls the test APK, and its files with it: run that test again
# by hand, take the files, then uninstall.
PKG=com.chronocol.blurry.engine.test
OUT=$(mktemp -d)
trap 'rm -rf "$OUT"; $ADB uninstall $PKG >/dev/null 2>&1 || true; stop_emulator' EXIT
(cd android && ./gradlew --quiet :engine:installDebugAndroidTest)
$ADB shell am instrument -w -e class com.chronocol.blurry.engine.ImageTest#outputsHoldNoMetadata \
    $PKG/androidx.test.runner.AndroidJUnitRunner | grep -q '^OK (1 test)' || { echo "outputsHoldNoMetadata fallito"; exit 1; }
$ADB pull /sdcard/Android/data/com.chronocol.blurry.engine.test/files/outputs "$OUT" >/dev/null
leaked=$(exiftool -j -a -G1 "$OUT"/outputs/* | uv run --frozen python -c '
import json, sys
private = ["GPS", "XMP", "IPTC", "ICC", "Thumbnail", "Orientation", "Make", "Model",
           "DateTimeOriginal", "Creator", "Comment", "Description", "Copyright"]
for f in json.load(sys.stdin):
    for k in f:
        if not k.startswith(("System:", "ExifTool:")) and k != "SourceFile" and any(p.lower() in k.lower() for p in private):
            print(f["SourceFile"].rsplit("/", 1)[-1], k)
')
count=$(ls "$OUT"/outputs | wc -l | tr -d ' ')
[[ $count -ge 3 ]] || { echo "exiftool: attesi 3 file, trovati $count"; exit 1; }
if [[ -n "$leaked" ]]; then echo "metadati rimasti:\n$leaked"; exit 1; fi
echo "exiftool: $count file puliti"
