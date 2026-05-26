"""
Optional enrichment: add account level (summonerLevel) to each seed player.

Account level is a tenure proxy and a feature in the churn model. This uses
summoner-v4 by-puuid, one extra call per player, so run it only when you want
that feature. Players already enriched are skipped.

Run from the project root:
    python src/enrich_players.py
"""

import json

from riot_client import get, platform_url
import config


def main():
    with open(config.PLAYERS_FILE, encoding="utf-8") as f:
        players = json.load(f)

    for i, player in enumerate(players, 1):
        if "summonerLevel" in player:
            continue
        data = get(platform_url(
            f"/lol/summoner/v4/summoners/by-puuid/{player['puuid']}"
        ))
        if data:
            player["summonerLevel"] = data.get("summonerLevel")
        if i % 10 == 0:
            print(f"[{i}/{len(players)}] enriched")

    with open(config.PLAYERS_FILE, "w", encoding="utf-8") as f:
        json.dump(players, f, indent=2)
    print("Account levels added.")


if __name__ == "__main__":
    main()
