/* ============================================================
   03_advanced_queries.sql
   Advanced analytical queries. CTEs and window functions:
   CASE aggregation, ranking, running totals, NTILE, and a
   gaps and islands streak calculation.
   Run the foundational set in 02_basic_queries.sql first.
   ============================================================ */
USE LoLChurnAnalysis;
GO

/* ---- 1. Driver comparison: average behavior, churned vs retained (low and mid) ---- */
SELECT CASE WHEN p.churned = 1 THEN 'churned' ELSE 'retained' END AS [group],
       COUNT(*)                                           AS players,
       AVG(p.total_games)                                 AS avg_total_games,
       AVG(p.games_trend)                                 AS avg_games_trend,
       CAST(AVG(p.games_per_active_day) AS DECIMAL(10,2))  AS avg_games_per_active_day,
       AVG(p.days_since_last)                             AS avg_days_since_last,
       AVG(p.unique_champions)                            AS avg_unique_champs,
       AVG(p.account_level)                               AS avg_account_level
FROM dim_player p
JOIN dim_tier t ON t.tier = p.tier
WHERE t.tier_band IN ('low','mid')
GROUP BY p.churned;
GO

/* ---- 2. Activity timeline: ranked matches per ISO week ----
   Uses the ISO year, not the calendar year, so late December and
   early January fall in the right week. ---- */
SELECT
    CASE WHEN d.[month] = 12 AND d.iso_week = 1   THEN d.[year] + 1
         WHEN d.[month] = 1  AND d.iso_week >= 52 THEN d.[year] - 1
         ELSE d.[year] END                          AS iso_year,
    d.iso_week,
    COUNT(*) AS matches
FROM fact_player_match f
JOIN dim_date d ON d.game_date = f.game_date
GROUP BY
    CASE WHEN d.[month] = 12 AND d.iso_week = 1   THEN d.[year] + 1
         WHEN d.[month] = 1  AND d.iso_week >= 52 THEN d.[year] - 1
         ELSE d.[year] END,
    d.iso_week
ORDER BY iso_year, d.iso_week;
GO

/* ---- 3. Most played champions among churned players (low and mid) ---- */
SELECT TOP 15
       f.champion,
       COUNT(*) AS games,
       CAST(100.0 * AVG(CAST(f.win AS FLOAT)) AS DECIMAL(5,1)) AS win_rate_pct
FROM fact_player_match f
JOIN dim_player p ON p.puuid = f.puuid
JOIN dim_tier  t ON t.tier  = p.tier
WHERE p.churned = 1 AND t.tier_band IN ('low','mid')
GROUP BY f.champion
ORDER BY games DESC;
GO

/* ---- 4. Top 3 most picked champions in each tier ----
   ROW_NUMBER restarts the ranking inside every tier, then we keep
   the top three. ---- */
WITH champ_rank AS (
    SELECT p.tier,
           f.champion,
           COUNT(*) AS games,
           ROW_NUMBER() OVER (PARTITION BY p.tier ORDER BY COUNT(*) DESC) AS rk
    FROM fact_player_match f
    JOIN dim_player p ON p.puuid = f.puuid
    GROUP BY p.tier, f.champion
)
SELECT tier, champion, games
FROM champ_rank
WHERE rk <= 3
ORDER BY tier, games DESC;
GO

/* ---- 5. Weekly activity: count, running total, week over week change ----
   A CTE counts matches per ISO week. Then window functions add a
   running total (SUM OVER) and the previous week's count (LAG), and
   the final step turns that into a percent change. ---- */
WITH weekly AS (
    SELECT
        CASE WHEN d.[month] = 12 AND d.iso_week = 1   THEN d.[year] + 1
             WHEN d.[month] = 1  AND d.iso_week >= 52 THEN d.[year] - 1
             ELSE d.[year] END AS iso_year,
        d.iso_week,
        COUNT(*) AS matches
    FROM fact_player_match f
    JOIN dim_date d ON d.game_date = f.game_date
    GROUP BY
        CASE WHEN d.[month] = 12 AND d.iso_week = 1   THEN d.[year] + 1
             WHEN d.[month] = 1  AND d.iso_week >= 52 THEN d.[year] - 1
             ELSE d.[year] END,
        d.iso_week
),
metrics AS (
    SELECT iso_year, iso_week, matches,
           SUM(matches) OVER (ORDER BY iso_year, iso_week
                              ROWS UNBOUNDED PRECEDING) AS cumulative_matches,
           LAG(matches) OVER (ORDER BY iso_year, iso_week) AS prev_week_matches
    FROM weekly
)
SELECT iso_year, iso_week, matches, cumulative_matches,
       CAST(100.0 * (matches - prev_week_matches) / prev_week_matches
            AS DECIMAL(6,1)) AS wow_change_pct
FROM metrics
ORDER BY iso_year, iso_week;
GO

/* ---- 6. Activity quartiles and churn (low and mid) ----
   NTILE splits players into four equal groups by total games, then
   we read the churn rate in each quartile. ---- */
WITH quartiles AS (
    SELECT p.churned, p.total_games,
           NTILE(4) OVER (ORDER BY p.total_games) AS activity_quartile
    FROM dim_player p
    JOIN dim_tier t ON t.tier = p.tier
    WHERE t.tier_band IN ('low','mid')
)
SELECT activity_quartile,
       COUNT(*)           AS players,
       MIN(total_games)   AS min_games,
       MAX(total_games)   AS max_games,
       CAST(100.0 * SUM(churned) / COUNT(*) AS DECIMAL(5,1)) AS churn_rate_pct
FROM quartiles
GROUP BY activity_quartile
ORDER BY activity_quartile;
GO

/* ---- 7. Each player's longest losing streak ----
   Gaps and islands. Number the games per player, number the losses,
   the difference is constant within a consecutive losing run, so we
   group on it to size each run, then take the longest run per player.
   One row per player. ---- */
WITH seq AS (
    SELECT puuid, win, game_start,
           ROW_NUMBER() OVER (PARTITION BY puuid ORDER BY game_start) AS rn,
           ROW_NUMBER() OVER (PARTITION BY puuid, win ORDER BY game_start) AS rn_win
    FROM fact_player_match
),
loss_runs AS (
    SELECT puuid, (rn - rn_win) AS grp, COUNT(*) AS run_len
    FROM seq
    WHERE win = 0
    GROUP BY puuid, (rn - rn_win)
),
player_max AS (
    SELECT puuid, MAX(run_len) AS longest_loss_streak
    FROM loss_runs
    GROUP BY puuid
)
SELECT p.tier, p.churned, pm.longest_loss_streak
FROM player_max pm
JOIN dim_player p ON p.puuid = pm.puuid
ORDER BY pm.longest_loss_streak DESC;
GO
