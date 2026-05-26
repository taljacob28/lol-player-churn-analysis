"""
Stage 5: parse cached match JSON into a tidy player-match table.

Reads every match in data/raw_matches, extracts one row per engaged seed player
who appears in the match, flattens the fields needed for feature engineering, and
drops non ranked games, remakes, and very short games. Writes
data/player_match.csv, one row per engaged player per match.

Run from the project root:
    python src/parse_matches.py
"""

import json
from datetime import datetime, timezone

import pandas as pd

import config

MIN_DURATION_SEC = 300          # drop remakes and very short games
OUTPUT = config.DATA / "player_match.csv"


def load_engaged():
    """Return a puuid -> {tier, churned} map for engaged players only."""
    with open(config.POPULATION_FILE, encoding="utf-8") as f:
        rows = json.load(f)
    engaged = {}
    for r in rows:
        if r.get("engaged"):
            engaged[r["puuid"]] = {"tier": r.get("tier"), "churned": r.get("churned")}
    return engaged


def patch_of(game_version):
    if not game_version:
        return None
    parts = game_version.split(".")
    return f"{parts[0]}.{parts[1]}" if len(parts) >= 2 else game_version


def duration_seconds(info):
    d = info.get("gameDuration", 0)
    return int(d / 1000 if d > 60000 else d)   # guard against old ms format


def extract_rows(match, engaged):
    """Return flattened rows for engaged players who appear in this match."""
    info = match.get("info", {})
    if info.get("queueId") != config.MATCH_QUEUE_ID:
        return []

    duration = duration_seconds(info)
    start_ts = info.get("gameStartTimestamp")
    if not start_ts:
        return []
    start_dt = datetime.fromtimestamp(start_ts / 1000, tz=timezone.utc)
    patch = patch_of(info.get("gameVersion"))
    match_id = match.get("metadata", {}).get("matchId")
    minutes = duration / 60 if duration else 0

    parts = info.get("participants", [])
    # precompute deaths for the death-leader flags (needs all ten players)
    game_max_deaths = max((q.get("deaths", 0) for q in parts), default=0)
    team_max_deaths = {}
    for q in parts:
        t = q.get("teamId")
        team_max_deaths[t] = max(team_max_deaths.get(t, 0), q.get("deaths", 0))

    rows = []
    for p in parts:
        puuid = p.get("puuid")
        if puuid not in engaged:
            continue
        if p.get("gameEndedInEarlySurrender") or duration < MIN_DURATION_SEC:
            continue

        kills = p.get("kills", 0)
        deaths = p.get("deaths", 0)
        assists = p.get("assists", 0)
        kda = (kills + assists) / deaths if deaths > 0 else (kills + assists)
        cs = p.get("totalMinionsKilled", 0) + p.get("neutralMinionsKilled", 0)
        gold = p.get("goldEarned", 0)
        ch = p.get("challenges", {})
        team_id = p.get("teamId")
        frustration_pings = (p.get("assistMePings", 0) + p.get("enemyMissingPings", 0)
                             + p.get("getBackPings", 0) + p.get("retreatPings", 0)
                             + p.get("dangerPings", 0))
        multikills = (p.get("doubleKills", 0) + p.get("tripleKills", 0)
                      + p.get("quadraKills", 0) + p.get("pentaKills", 0))
        label = engaged[puuid]

        rows.append({
            "puuid": puuid,
            "match_id": match_id,
            "tier": label["tier"],
            "churned": label["churned"],
            "game_start": start_dt.isoformat(),
            "game_date": start_dt.date().isoformat(),
            "game_hour_utc": start_dt.hour,
            "patch": patch,
            "duration_sec": duration,
            "champion": p.get("championName"),
            "position": p.get("teamPosition") or "UNKNOWN",
            "win": int(bool(p.get("win"))),
            "surrender": int(bool(p.get("gameEndedInSurrender"))),
            "kills": kills,
            "deaths": deaths,
            "assists": assists,
            "kda": round(kda, 3),
            "cs": cs,
            "cs_per_min": round(cs / minutes, 2) if minutes else 0,
            "gold": gold,
            "gold_per_min": round(gold / minutes, 2) if minutes else 0,
            "damage_to_champs": p.get("totalDamageDealtToChampions", 0),
            "damage_taken": p.get("totalDamageTaken", 0),
            "vision_score": p.get("visionScore", 0),
            "champ_level": p.get("champLevel", 0),
            "account_level": p.get("summonerLevel", 0),
            # frustration, contribution, and highlight signals
            "time_dead_sec": p.get("totalTimeSpentDead", 0),
            "team_death_leader": int(deaths == team_max_deaths.get(team_id, 0)),
            "game_death_leader": int(deaths == game_max_deaths),
            "kill_participation": round(ch.get("killParticipation") or 0, 4),
            "team_damage_share": round(ch.get("teamDamagePercentage") or 0, 4),
            "solo_kills": ch.get("soloKills") or 0,
            "multikills": multikills,
            "frustration_pings": frustration_pings,
            "first_blood": int(bool(p.get("firstBloodKill"))),
        })
    return rows


def main():
    engaged = load_engaged()
    print(f"{len(engaged)} engaged players to match against.")

    files = sorted(config.RAW_MATCHES.glob("*.json"))
    print(f"{len(files)} match files to parse.")

    all_rows = []
    skipped = 0
    for i, path in enumerate(files, 1):
        try:
            with open(path, encoding="utf-8") as f:
                match = json.load(f)
        except (json.JSONDecodeError, OSError):
            skipped += 1
            continue
        all_rows.extend(extract_rows(match, engaged))
        if i % 5000 == 0:
            print(f"[{i}/{len(files)}] rows so far: {len(all_rows)}")

    df = pd.DataFrame(all_rows)
    df.sort_values(["puuid", "game_start"], inplace=True)
    df.to_csv(OUTPUT, index=False)

    churn_players = df[df["churned"]]["puuid"].nunique()
    print(f"\nDone. {len(df)} player-match rows from {df['puuid'].nunique()} players.")
    print(f"Players represented: {churn_players} churned, "
          f"{df['puuid'].nunique() - churn_players} retained.")
    print(f"Skipped {skipped} unreadable files.")
    print(f"Saved to {OUTPUT}")


if __name__ == "__main__":
    main()