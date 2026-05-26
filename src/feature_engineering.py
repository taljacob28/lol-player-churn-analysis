"""
Stage 8: feature engineering.

Collapses the player-match table (data/player_match.csv) into one row per player
(data/player_features.csv) with the churn label and the behavioral features used
for the driver analysis and the model.

The feature window is split at its global midpoint into a first half and a second
half, so engagement and performance trends can be measured. A player drifting
toward churn tends to show fewer games and a falling win rate in the second half.

Run from the project root:
    python src/feature_engineering.py
"""

import numpy as np
import pandas as pd

import config

INPUT = config.DATA / "player_match.csv"
OUTPUT = config.DATA / "player_features.csv"

TIER_BANDS = {
    "IRON": "low", "BRONZE": "low", "SILVER": "low",
    "GOLD": "mid", "PLATINUM": "mid", "EMERALD": "mid",
    "DIAMOND": "high", "MASTER": "high", "GRANDMASTER": "high", "CHALLENGER": "high",
}

NIGHT_HOURS = set(range(0, 7))     # 00:00 to 06:59 UTC


def longest_loss_streak(wins_in_order):
    longest = current = 0
    for w in wins_in_order:
        if w == 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def build_features(df):
    df = df.copy()
    df["game_start"] = pd.to_datetime(df["game_start"], format="ISO8601", utc=True)
    df.sort_values(["puuid", "game_start"], inplace=True)

    window_start = df["game_start"].min()
    window_end = df["game_start"].max()
    midpoint = window_start + (window_end - window_start) / 2
    window_weeks = max((window_end - window_start).days / 7, 1)

    rows = []
    for puuid, g in df.groupby("puuid"):
        total = len(g)
        first_half = g[g["game_start"] < midpoint]
        second_half = g[g["game_start"] >= midpoint]
        champ_counts = g["champion"].value_counts()
        active_days = g["game_date"].nunique()

        wr = g["win"].mean()
        wr_first = first_half["win"].mean() if len(first_half) else np.nan
        wr_second = second_half["win"].mean() if len(second_half) else np.nan

        rows.append({
            "puuid": puuid,
            "tier": g["tier"].iloc[0],
            "tier_band": TIER_BANDS.get(g["tier"].iloc[0], "mid"),
            "churned": int(bool(g["churned"].iloc[0])),

            # volume and engagement
            "total_games": total,
            "games_per_week": round(total / window_weeks, 2),
            "games_first_half": len(first_half),
            "games_second_half": len(second_half),
            "games_trend": len(second_half) - len(first_half),
            "active_days": active_days,
            "games_per_active_day": round(total / active_days, 2) if active_days else 0,

            # performance
            "win_rate": round(wr, 4),
            "win_rate_first_half": round(wr_first, 4) if not np.isnan(wr_first) else None,
            "win_rate_second_half": round(wr_second, 4) if not np.isnan(wr_second) else None,
            "win_rate_trend": round(wr_second - wr_first, 4)
                              if not (np.isnan(wr_first) or np.isnan(wr_second)) else None,
            "avg_kda": round(g["kda"].mean(), 3),
            "avg_cs_per_min": round(g["cs_per_min"].mean(), 2),
            "avg_gold_per_min": round(g["gold_per_min"].mean(), 2),
            "avg_duration_min": round(g["duration_sec"].mean() / 60, 1),
            "avg_vision_score": round(g["vision_score"].mean(), 1),

            # streaks
            "longest_loss_streak": longest_loss_streak(g["win"].tolist()),

            # champion variety
            "unique_champions": int(g["champion"].nunique()),
            "champion_diversity": round(g["champion"].nunique() / total, 3),
            "top_champion_share": round(champ_counts.iloc[0] / total, 3),

            # role
            "primary_role": g["position"].mode().iloc[0] if not g["position"].mode().empty else "UNKNOWN",
            "role_focus": round(g["position"].value_counts().iloc[0] / total, 3),

            # session and tenure
            "night_share": round(g["game_hour_utc"].isin(NIGHT_HOURS).mean(), 3),
            "account_level": int(g["account_level"].max()),
        })

    return pd.DataFrame(rows)


def main():
    df = pd.read_csv(INPUT)
    features = build_features(df)
    features.to_csv(OUTPUT, index=False)

    churned = int(features["churned"].sum())
    print(f"Done. {len(features)} players, {features.shape[1]} columns.")
    print(f"Churned {churned}, retained {len(features) - churned}.")
    print(f"Saved to {OUTPUT}")


if __name__ == "__main__":
    main()
