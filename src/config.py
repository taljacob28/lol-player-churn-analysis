"""Central project settings. Edit values here, not inside the scripts."""

from pathlib import Path

# --- Routing ---
PLATFORM = "euw1"          # summoner-v4 and league endpoints
REGION = "europe"          # account-v1 and match-v5 endpoints
QUEUE = "RANKED_SOLO_5x5"  # league endpoints queue name
MATCH_QUEUE_ID = 420       # match-v5 queue id for ranked solo

# --- Seed sampling (stratified across tiers) ---
TIERS = [
    "IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM",
    "EMERALD", "DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER",
]
DIVISIONS = ["I", "II", "III", "IV"]            # regular tiers
APEX_TIERS = ["MASTER", "GRANDMASTER", "CHALLENGER"]  # use division I only

PLAYERS_PER_TIER = 12          # first run: about 12 x 10 tiers = ~120 players
PLAYERS_PER_TIER_EXPANDED = 40  # later, after the pipeline is validated

# --- Observation window ---
OBSERVATION_MONTHS = 6
FEATURE_MONTHS = 4
OUTCOME_MONTHS = 2
MIN_FEATURE_GAMES = 30         # regular players, about twice a week over the window

# --- Match pull caps ---
MATCHES_PER_PLAYER_CAP = 200   # cap match ids per player to keep pulls feasible
MATCH_IDS_PAGE_SIZE = 100      # max per match-v5 matchlist call

# --- Paths ---
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW_MATCHES = DATA / "raw_matches"
PLAYERS_FILE = DATA / "players.json"
MATCH_IDS_FILE = DATA / "match_ids.json"
POPULATION_FILE = DATA / "population.json"

DATA.mkdir(parents=True, exist_ok=True)
RAW_MATCHES.mkdir(parents=True, exist_ok=True)