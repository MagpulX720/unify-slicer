# Unify Slicer: settings box check (runs last, from apply_unify_phase3.py).
# The unit text shown INSIDE a settings box (sidetext) must be the unit only - "%", "°", "mm/s", "s", "layers".
# A longer text covers the number in the box (issue #8, and the Inner wall speed box in the Nov 20 build).
# Ranges and notes like "0 = auto" belong in the tooltip. This file shortens the existing ones and then stops
# the build if any Unify setting still has a long unit text.
import re

print("Checking Unify settings boxes")

_SHORTEN = [
    ('def->sidetext = L("layers (2-50)");', 'def->sidetext = L("layers");'),
    ('def->sidetext = L("s (20-40)");', 'def->sidetext = L("s");'),
    ('def->sidetext = L("° (10-60)");', 'def->sidetext = L("°");'),
    ('def->sidetext = L("mm/s (10-500)");', 'def->sidetext = L("mm/s");'),
    ('def->sidetext = L("mm/s (5-30)");', 'def->sidetext = L("mm/s");'),
    ('def->sidetext = L("° (30-85)");', 'def->sidetext = L("°");'),
    ('def->sidetext = L("% of inner wall speed");', 'def->sidetext = L("%");'),
    ('def->sidetext = L("% (0 = auto)");', 'def->sidetext = L("%");'),
    # the ranges move into the tooltips
    ('"The inner wall slows down where the outer wall overhangs this much or more (degrees from vertical).")',
     '"The inner wall slows down where the outer wall overhangs this much or more (degrees from vertical). Min 30, max 85.")'),
    ('"Manual mode: speed of the slowed inner wall, as a % of its normal inner wall speed.")',
     '"Manual mode: speed of the slowed inner wall, as a % of its normal inner wall speed. Min 5, max 100.")'),
]
_pc = ROOT / "src/libslic3r/PrintConfig.cpp"
_txt = _pc.read_text(encoding="utf-8")
for _old, _new in _SHORTEN:
    if _old in _txt:
        _txt = _txt.replace(_old, _new)
        print(f"  + {_new.strip()[:70]}")
_pc.write_text(_txt, encoding="utf-8")

# The check: every Unify setting (unify_* and the wall_direction_* options Unify added) keeps a short unit text.
_MAX = 6
_bad = []
_key = None
for _line in _txt.splitlines():
    _m = re.search(r'def = this->add\("([^"]+)"', _line)
    if _m:
        _key = _m.group(1)
        continue
    _m = re.search(r'def->sidetext = (?:L\()?"([^"]*)"', _line)
    if _m and _key and (_key.startswith("unify_") or _key.startswith("wall_direction_")):
        if len(_m.group(1)) > _MAX:
            _bad.append(f"{_key}: \"{_m.group(1)}\"")
if _bad:
    sys.exit("ERROR: unit text too long for the settings box (keep it to the unit, put ranges in the tooltip):\n  "
             + "\n  ".join(_bad))
print("  settings boxes OK (unit texts are short)")
