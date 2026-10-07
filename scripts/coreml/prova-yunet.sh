#!/bin/zsh
# Prova per un'eventuale app iOS: YuNet convertito in Core ML trova gli stessi
# volti del motore (cv2.FaceDetectorYN)? Stato e risultati nel piano
# (CHRONO/docs/piani/PIANO_BLURRY.md, fase 5).
#
#   scripts/coreml/prova-yunet.sh
#
# 1. convert.py: ONNX → Core ML, fp32 e fp16, ingresso di qualunque dimensione.
# 2. compare.py: le uscite Core ML (da Python) contro il motore, sugli stessi
#    pixel; controlla anche che la decodifica + NMS riscritta sia identica a
#    quella di OpenCV.
# 3. yunet.swift: la stessa decodifica in Swift con Core ML, come in un'app;
#    anche con le immagini aperte da ImageIO invece che da Pillow.
#
# Esce con errore se fp32 non dà esattamente i riquadri del motore.
# Tutto finisce in build/coreml/ (ignorata da git), compresi i pixel delle
# fixture private. Gli strumenti di conversione stanno in un ambiente a parte
# (requirements.txt), mai nel pacchetto né in uv.lock.
set -euo pipefail

ROOT=${0:A:h:h:h}
HERE=${0:A:h}
WORK="$ROOT/build/coreml"
mkdir -p "$WORK"
cd "$WORK"

if [[ ! -x .venv/bin/python ]]; then
  uv venv -q -p 3.12 .venv
fi
VIRTUAL_ENV=.venv uv pip install -q -e "$ROOT" -r "$HERE/requirements.txt"
PY=.venv/bin/python

$PY "$HERE/convert.py"
$PY "$HERE/compare.py"

for p in fp32 fp16; do
  xcrun coremlcompiler compile "YuNet-$p.mlpackage" . >/dev/null
done
swiftc -O -o yunet "$HERE/yunet.swift"
for p in fp32 fp16; do
  for u in cpu all; do
    print -n "swift $p/$u: "
    ./yunet "YuNet-$p.mlmodelc" $u data "results-$p-$u.json"
  done
done
print -n "swift fp32/all, ImageIO: "
./yunet YuNet-fp32.mlmodelc all data results-imageio-fp32.json "$ROOT/tests/fixtures"

$PY "$HERE/check_swift.py" results-fp32-cpu.json results-fp32-all.json \
  results-fp16-cpu.json results-fp16-all.json results-imageio-fp32.json
