"""Run the ORIGINAL OPSEC engine on images and print its face boxes as JSON.

This file runs inside a separate virtualenv built from the original
requirements (see tests/test_baseline.py); it does not import Blurry.

    python baseline_dump.py ORIGINAL_SCRIPT MODEL LEVEL IMAGE...
"""

import contextlib
import importlib.util
import io
import json
import os
import sys

script, model, level, *images = sys.argv[1:]
os.environ["OPSEC_YUNET_MODEL"] = model
spec = importlib.util.spec_from_file_location("media_processor", script)
mod = importlib.util.module_from_spec(spec)
with contextlib.redirect_stderr(io.StringIO()):
    spec.loader.exec_module(mod)
    proc = mod.OpsecFaceProcessor(opsec_level=level)
assert proc.detector == "yunet", "the original engine fell back to Haar"
import cv2  # noqa: E402

out = {}
for path in images:
    image = cv2.imread(path)
    out[os.path.basename(path)] = [[int(v) for v in b] for b in proc.detect_all_faces(image)]
print(json.dumps(out))
