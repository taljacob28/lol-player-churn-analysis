"""
Stage 2: seed the player population from the ranked ladder.

Uses league-exp-v4, which returns the puuid directly inside each ranked entry,
so no summoner-v4 conversion step is needed. Pulls a stratified sample, an equal
number of players from every tier, and saves them to data/players.json.

Run from the project root:
    python src/seed_players.py
"""

import json
import random

from riot_client import get, platform_url
import config


def fetch_tier(tier, target_count):
    """Pull ranked entries for one tier until target_count players are collected."""
    players = []
    seen = set()
    divisions = ["I"] if tier in config.APEX_TIERS else config.DIVISIONS

    for division in divisions:
        page = 1
        while len(players) < target_count:
            path = (
                f"/lol/league-exp/v4/entries/"
                f"{config.QUEUE}/{tier}/{division}?page={page}"
            )
            entries = get(platform_url(path))
            if not entries:
                break
            for e in entries:
                puuid = e.get("puuid")
                if not puuid or puuid in seen:
                    continue
                seen.add(puuid)
                players.append({
                    "puuid": puuid,
                    "tier": tier,
                    "rank": e.get("rank"),
                    "leaguePoints": e.get("leaguePoints"),
                    "wins": e.get("wins"),
                    "losses": e.get("losses"),
                    "inactive": e.get("inactive"),
                })
            page += 1
        if len(players) >= target_count:
            break

    random.shuffle(players)
    return players[:target_count]


def main():
    target = config.PLAYERS_PER_TIER
    all_players = []

    for tier in config.TIERS:
        print(f"Pulling {tier} ...")
        tier_players = fetch_tier(tier, target)
        print(f"  got {len(tier_players)} players")
        all_players.extend(tier_players)

    with open(config.PLAYERS_FILE, "w", encoding="utf-8") as f:
        json.dump(all_players, f, indent=2)

    print(f"Saved {len(all_players)} players to {config.PLAYERS_FILE}")


if __name__ == "__main__":
    main()
