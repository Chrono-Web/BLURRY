"""Compare the Swift results (results-*.json) with the engine's (data/reference.json).

Exits with an error if a results-fp32-*.json file is not identical to the engine.
"""

import json
import sys
from pathlib import Path

from compare import match

ref = json.loads(Path("data/reference.json").read_text())
failed = []
for path in sys.argv[1:]:
    got = json.loads(Path(path).read_text())
    exact = missing = extra = dmax = 0
    smax = 0.0
    notes = []
    for name, boxes in got.items():
        r = [tuple(b) for b in ref[name]]
        g = [tuple(int(v) for v in b[:4]) + (b[4],) for b in boxes]
        m, e, d, s, ok = match(r, g)
        exact += ok
        missing += len(m)
        extra += len(e)
        dmax, smax = max(dmax, d), max(smax, s)
        if m or e:
            marks = " ".join(f"[{'-' if b in m else '+'}{b[4]:.3f}]" for b in m + e)
            notes.append(f"{name}: {marks}")
    print(
        f"{path:28s} identical {exact}/{len(got)}  missing {missing}  extra {extra}  "
        f"max Δbox {dmax}px  max Δscore {smax:.4f}"
    )
    for n in notes:
        print("   ", n)
    if path.startswith("results-fp32-") and exact != len(got):
        failed.append(path)
if failed:
    sys.exit(f"fp32 differs from the engine: {', '.join(failed)}")
