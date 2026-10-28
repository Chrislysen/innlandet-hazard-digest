"""Central settings. Everything safety-relevant lives here so it is easy to audit."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "out"
CONTEXT_DIR = ROOT / "context"
KILL_FILE = ROOT / "KILL"
FAILURE_STREAK_FILE = OUT_DIR / ".failure_streak"

COUNTY_ID = "34"  # Innlandet
HAZARDS = ("flood", "landslide")
API_BASE = "https://api01.nve.no/hydrology/forecast/{hazard}/v1.0.10/api/CountySummary/1/{start}/{end}"
USER_AGENT = "KIUA2003-student-project (University of Inland Norway)"
FETCH_TIMEOUT_S = 30
FETCH_RETRIES = 3
MIN_MUNICIPALITIES_PER_HAZARD = 40  # Innlandet has 46; far fewer means a degraded/changed feed, not good news
DAYS_AHEAD = 2  # today + 2 days = 3-day outlook

MIN_LEVEL = 2  # 1 = green (no warning); 2 yellow, 3 orange, 4 red
LEVEL_COLORS = {2: ("gult", "yellow"), 3: ("oransje", "orange"), 4: ("rødt", "red")}
HAZARD_NAMES = {"flood": ("flom", "flood"), "landslide": ("jordskred", "landslide")}
SOURCE_URL = "https://www.varsom.no/flom-og-jordskred/"
URL_ALLOWLIST = ("varsom.no",)
ATTRIBUTION = {
    "flood": "Varsler fra Flomvarslingen i Norge og www.varsom.no",
    "landslide": "Varsler fra Jordskredvarslingen i Norge og www.varsom.no",
}

# Safe operation
MAX_BUDGET_USD = 0.25          # hard cap per run, enforced by the claude CLI
MAX_DRAFT_ATTEMPTS = 2         # first try + one repair attempt with validator feedback
MAX_CONSECUTIVE_FAILURES = 3   # kill switch: halt autonomous runs after this many failed runs
MAX_SOURCE_TEXT_CHARS = 1200   # cap on untrusted text passed to the agent per field
