"""Stage 1: fetch official NVE/Varsom warnings. Network + files only; no agent involved."""
import json
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from . import config


class FetchError(RuntimeError):
    pass


def fetch_hazard(hazard: str, start: date, end: date) -> dict:
    url = config.API_BASE.format(hazard=hazard, start=start.isoformat(), end=end.isoformat())
    req = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT, "Accept": "application/json"})
    last = None
    for attempt in range(1, config.FETCH_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=config.FETCH_TIMEOUT_S) as r:
                data = json.loads(r.read().decode("utf-8"))
            if not isinstance(data, dict) or "CountyList" not in data:
                raise FetchError(f"unexpected payload shape from {hazard} API")
            return data
        except Exception as e:  # network, HTTP, JSON, shape
            last = e
            time.sleep(2 ** attempt * 0.5)
    raise FetchError(f"{hazard}: failed after {config.FETCH_RETRIES} attempts: {last}")


def fetch_all(today: date | None = None, save_dir: Path | None = None) -> dict[str, dict]:
    today = today or date.today()
    end = today + timedelta(days=config.DAYS_AHEAD)
    out = {h: fetch_hazard(h, today, end) for h in config.HAZARDS}
    save_dir = save_dir or config.RAW_DIR / today.isoformat()
    save_dir.mkdir(parents=True, exist_ok=True)
    for h, d in out.items():
        (save_dir / f"{h}.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return out


def load_dir(path: Path) -> dict[str, dict]:
    """Offline source: load previously saved raw payloads (used for fixtures and tests)."""
    return {h: json.loads((path / f"{h}.json").read_text(encoding="utf-8")) for h in config.HAZARDS}
