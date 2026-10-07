"""BlurryKit (ios/, the Swift engine of the iOS app) shares two facts with this
engine: the detection levels and the model. Both are checked here; the
behaviour is checked by its own parity tests (scripts/coreml/test-kit.sh)."""

import re
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / "ios/BlurryKit/Sources/BlurryKit"


def test_levels_json_is_generated_from_levels_py():
    gen = runpy.run_path(str(ROOT / "scripts/coreml/levels_json.py"))
    committed = (KIT / "Resources/levels.json").read_text(encoding="utf-8")
    assert committed == gen["levels_json"](), "run scripts/coreml/levels_json.py"


def test_model_hash_pinned_in_swift_matches_the_model():
    gen = runpy.run_path(str(ROOT / "scripts/coreml/model_hash.py"))
    source = (KIT / "Model.swift").read_text(encoding="utf-8")
    pinned = re.search(r'static let sha256 = "([0-9a-f]{64})"', source)
    assert pinned, "MODEL_SHA256 not found in Model.swift"
    assert gen["model_hash"](KIT / "Resources/YuNet.mlmodelc") == pinned.group(1)
