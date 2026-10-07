#!/bin/zsh
# Test di BlurryKit (ios/BlurryKit), il motore Swift dell'app iOS, contro il
# motore Python: prima il riferimento (riferimento.py scrive build/parity/),
# poi swift test in release, che è molte volte più veloce del debug sui
# cicli di pixel. Serve exiftool (brew install exiftool).
#
#   scripts/coreml/test-kit.sh
set -euo pipefail

ROOT=${0:A:h:h:h}
cd "$ROOT"
uv run --frozen python scripts/coreml/riferimento.py
swift test --package-path ios/BlurryKit -c release -Xswiftc -enable-testing
