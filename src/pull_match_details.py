"""
Stage 4 (revised): pull full match detail JSON only for the feature period
matches of engaged players, churned players first.

The churned players are the rare and valuable class, so their feature matches are
pulled before any retained player. If a development key runs out of time, every
churned player still ends up with full features, and retained players fill in the
rest. Each match is cached to data/raw_matches/{matchId}.json and skipped if
already present, so the pull resumes after an interruption or a key refresh.

Run from the project root:
    python src/pull_match_details.py
"""

import json

from riot_client import get, regional_url
import config


def load_population():
    with open(config.POPULATION_FILE, encoding="utf-8") as f:
        return json.load(f)


def ordered_feature_ids(rows):
    """Return feature match ids with churned players first, deduplicated.

    Also returns how many ids belong to the churned block, so the caller can
    report when the churned class is fully pulled.
    """
    seen = set()
    churned_ids = []
    retained_ids = []

    for r in rows:
        if r.get("engaged") and r.get("churned"):
            for mid in r.get("feature_ids", []):
                if mid not in seen:
                    seen.add(mid)
                    churned_ids.append(mid)

    for r in rows:
        if r.get("engaged") and not r.get("churned"):
            for mid in r.get("feature_ids", []):
                if mid not in seen:
                    seen.add(mid)
                    retained_ids.append(mid)

    return churned_ids + retained_ids, len(churned_ids)


def match_path(match_id):
    return config.RAW_MATCHES / f"{match_id}.json"


def fetch_match(match_id):
    return get(regional_url(f"/lol/match/v5/matches/{match_id}"))


def main():
    rows = load_population()
    all_ids, churned_count = ordered_feature_ids(rows)
    print(f"{len(all_ids)} unique feature matches to pull "
          f"({churned_count} from churned players, pulled first).")

    pulled = 0
    cached = 0
    for i, match_id in enumerate(all_ids, 1):
        if i == churned_count + 1:
            print("Churned block complete. Continuing with retained players.")
        out = match_path(match_id)
        if out.exists():
            cached += 1
            continue
        data = fetch_match(match_id)
        if data:
            with open(out, "w", encoding="utf-8") as f:
                json.dump(data, f)
            pulled += 1
        if i % 50 == 0:
            print(f"[{i}/{len(all_ids)}] pulled {pulled}, already cached {cached}")

    print(f"Done. Pulled {pulled} new matches, {cached} already cached.")


if __name__ == "__main__":
    main()