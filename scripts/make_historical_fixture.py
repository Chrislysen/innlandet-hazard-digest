"""Build data/fixtures/historical_hamar_2023 by placing the real archived Hamar warning into a
CountySummary-shaped payload (all other municipalities stay green). Content is verbatim from NVE."""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "data" / "fixtures"
warning = json.loads((ROOT / "data/evidence/flood_hamar_20230810_no.json").read_text(encoding="utf-8"))[0]

flood = json.loads((FIX / "real_green/flood.json").read_text(encoding="utf-8"))
for county in flood["CountyList"]:
    for m in county["MunicipalityList"] or []:
        if county["Id"] == "34" and m["Id"] == "3403":
            m["WarningList"] = m["WarningList"] + [copy.deepcopy(warning)]  # keep the green days, add the archived one

out = FIX / "historical_hamar_2023"
out.mkdir(parents=True, exist_ok=True)
(out / "flood.json").write_text(json.dumps(flood, ensure_ascii=False), encoding="utf-8")
(out / "landslide.json").write_text((FIX / "real_green/landslide.json").read_text(encoding="utf-8"), encoding="utf-8")
(out / "label.txt").write_text(
    "HISTORICAL REPLAY: a genuine NVE warning (Hamar, orange flood, valid 2023-08-10) inserted into a "
    "2026-10-28 all-green background. Not a current warning." + chr(10), encoding="utf-8")
print("wrote", out)
