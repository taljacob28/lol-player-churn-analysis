"""
Stage 3 (revised): build the study population with a windowed pull.

For each seed player, pull ranked match ids separately for the feature period
(first 4 months) and the outcome period (last 2 months).

Keep only engaged players, those with at least MIN_FEATURE_GAMES ranked games in
the feature period. The question is why committed players leave, not why casual
players drift off.

The churn label comes free from the outcome period. A player is churned if they
played zero ranked games in the outcome period. No match details are needed for
the outcome period, which saves a large amount of pulling. Match details are
pulled later only for feature period games of engaged players.

Output: data/population.json, one record per seed player processed, with an
engaged flag, feature match ids, counts, and the churn label for engaged players.
Players already processed are skipped, so the run resumes after an interruption
or a key refresh.

Run from the project root:
    python src/build_population.py
"""

import json
from datetime import datetime, timedelta, timezone

from riot_client import get, regional_url
import config


def load_players():
    with open(config.PLAYERS_FILE, encoding="utf-8") as f:
        return json.load(f)


def windows():
    """Return feature and outcome window bounds in epoch seconds."""
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=config.OBSERVATION_MONTHS * 30)
    split = now - timedelta(days=config.OUTCOME_MONTHS * 30)
    feature = (int(window_start.timestamp()), int(split.timestamp()))
    outcome = (int(split.timestamp()), int(now.timestamp()))
    return feature, outcome


def fetch_ids(puuid, start_time, end_time, cap):
    """Page through the matchlist for one window and collect ranked solo ids."""
    ids = []
    start_index = 0
    while len(ids) < cap:
        path = (
            f"/lol/match/v5/matches/by-puuid/{puuid}/ids"
            f"?startTime={start_time}&endTime={end_time}"
            f"&queue={config.MATCH_QUEUE_ID}&type=ranked"
            f"&start={start_index}&count={config.MATCH_IDS_PAGE_SIZE}"
        )
        batch = get(regional_url(path))
        if not batch:
            break
        ids.extend(batch)
        if len(batch) < config.MATCH_IDS_PAGE_SIZE:
            break
        start_index += config.MATCH_IDS_PAGE_SIZE
    return ids[:cap]


def load_existing():
    if config.POPULATION_FILE.exists():
        with open(config.POPULATION_FILE, encoding="utf-8") as f:
            return json.load(f)
    return []


def save(rows):
    with open(config.POPULATION_FILE, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)


def main():
    players = load_players()
    feature_win, outcome_win = windows()

    rows = load_existing()
    done = {r["puuid"] for r in rows}

    for i, p in enumerate(players, 1):
        puuid = p["puuid"]
        if puuid in done:
            continue

        feature_ids = fetch_ids(puuid, feature_win[0], feature_win[1],
                                config.MATCHES_PER_PLAYER_CAP)

        if len(feature_ids) < config.MIN_FEATURE_GAMES:
            rows.append({
                "puuid": puuid,
                "tier": p["tier"],
                "feature_count": len(feature_ids),
                "engaged": False,
            })
            done.add(puuid)
            print(f"[{i}/{len(players)}] {p['tier']} -> "
                  f"{len(feature_ids)} feature games, not engaged")
            continue

        outcome_ids = fetch_ids(puuid, outcome_win[0], outcome_win[1],
                                config.MATCHES_PER_PLAYER_CAP)
        churned = len(outcome_ids) == 0

        rows.append({
            "puuid": puuid,
            "tier": p["tier"],
            "rank": p.get("rank"),
            "engaged": True,
            "feature_ids": feature_ids,
            "feature_count": len(feature_ids),
            "outcome_count": len(outcome_ids),
            "churned": churned,
        })
        done.add(puuid)
        label = "churned" if churned else "retained"
        print(f"[{i}/{len(players)}] {p['tier']} -> {len(feature_ids)} feature, "
              f"{len(outcome_ids)} outcome, {label}")

        engaged_so_far = sum(1 for r in rows if r.get("engaged"))
        if engaged_so_far % 10 == 0:
            save(rows)

    save(rows)
    engaged = [r for r in rows if r.get("engaged")]
    churned_n = sum(1 for r in engaged if r["churned"])
    print(
        f"Done. {len(rows)} players processed, {len(engaged)} engaged "
        f"(>= {config.MIN_FEATURE_GAMES} feature games), "
        f"{churned_n} churned, {len(engaged) - churned_n} retained."
    )


if __name__ == "__main__":
    main()
