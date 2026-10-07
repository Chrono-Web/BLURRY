#!/bin/zsh
# Rigenera il modello di BlurryKit (ios/BlurryKit/.../Resources/YuNet.mlmodelc)
# dall'ONNX del motore: conversione fp32 (convert.py) e compilazione.
# Si lancia solo se il modello ONNX cambia. Il .mlmodelc è committato perché né
# la conversione né la compilazione sono riproducibili byte per byte: dopo,
# va aggiornato MODEL_SHA256 in Sources/BlurryKit/Model.swift con l'hash
# stampato qui, e vanno rifatti i test di parità (scripts/coreml/test-kit.sh).
#
#   scripts/coreml/modello.sh
set -euo pipefail

ROOT=${0:A:h:h:h}
HERE=${0:A:h}
WORK="$ROOT/build/coreml"
DEST="$ROOT/ios/BlurryKit/Sources/BlurryKit/Resources/YuNet.mlmodelc"
mkdir -p "$WORK"
cd "$WORK"

if [[ ! -x .venv/bin/python ]]; then
  uv venv -q -p 3.12 .venv
fi
VIRTUAL_ENV=.venv uv pip install -q -e "$ROOT" -r "$HERE/requirements.txt"

.venv/bin/python "$HERE/convert.py"
rm -rf compiled && mkdir compiled
xcrun coremlcompiler compile YuNet-fp32.mlpackage compiled >/dev/null
rm -rf "$DEST"
mv compiled/YuNet-fp32.mlmodelc "$DEST"
.venv/bin/python "$HERE/model_hash.py" "$DEST"
