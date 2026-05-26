/* ============================================================
   02_basic_queries.sql
   Foundational analyst queries, simple to medium.
   Counts, GROUP BY, AVG, CASE bucketing, HAVING, basic JOIN.
   The everyday SQL an analyst writes. Advanced window work lives
   in 03_advanced_queries.sql.
   ============================================================ */
USE LoLChurnAnalysis;
GO

/* ---- 1. Dataset overview ---- */
SELECT COUNT(DISTINCT puuid)    AS players,
       COUNT(*)                 AS player_match_rows,
       COUNT(DISTINCT champion) AS champions,
       MIN(game_date)           AS first_day,
       MAX(game_date)           AS last_day
FROM fact_player_match;
GO

/* ---- 2. Players and average win rate by tier ---- */
SELECT tier,
       COUNT(*)                                   AS players,
       CAST(100.0 * AVG(win_rate) AS DECIMAL(5,1)) AS avg_win_rate_pct
FROM dim_player
GROUP BY tier
ORDER BY players DESC;
GO

/* ---- 3. Churn rate by tier band ---- */
SELECT t.tier_band,
       COUNT(*)       AS players,
       SUM(p.churned) AS churned,
       CAST(100.0 * SUM(p.churned) / COUNT(*) AS DECIMAL(5,1)) AS churn_rate_pct
FROM dim_player p
JOIN dim_tier t ON t.tier = p.tier
GROUP BY t.tier_band
ORDER BY churn_rate_pct DESC;
GO

/* ---- 4. Churn rate by primary role, low and mid tiers only ---- */
SELECT p.primary_role,
       COUNT(*)       AS players,
       SUM(p.churned) AS churned,
       CAST(100.0 * SUM(p.churned) / COUNT(*) AS DECIMAL(5,1)) AS churn_rate_pct
FROM dim_player p
JOIN dim_tier t ON t.tier = p.tier
WHERE t.tier_band IN ('low','mid')
GROUP BY p.primary_role
ORDER BY churn_rate_pct DESC;
GO

/* ---- 5. Average games per player by tier band ---- */
SELECT t.tier_band,
       COUNT(*)                                          AS players,
       CAST(AVG(CAST(p.total_games AS FLOAT)) AS DECIMAL(6,1)) AS avg_games_per_player
FROM dim_player p
JOIN dim_tier t ON t.tier = p.tier
GROUP BY t.tier_band
ORDER BY avg_games_per_player DESC;
GO

/* ---- 6. Activity by hour of day (UTC) ---- */
SELECT game_hour_utc,
       COUNT(*) AS matches
FROM fact_player_match
GROUP BY game_hour_utc
ORDER BY game_hour_utc;
GO

/* ---- 7. Activity by weekday ---- */
SELECT d.weekday_name,
       COUNT(*) AS matches
FROM fact_player_match f
JOIN dim_date d ON d.game_date = f.game_date
GROUP BY d.weekday_name
ORDER BY matches DESC;
GO

/* ---- 8. Engagement segments and churn rate ----
   Bucket players by how many games they played, then read churn
   per segment. Labels are numbered so they sort in order. ---- */
WITH segments AS (
    SELECT churned,
           CASE WHEN total_games < 50  THEN '1 low (<50)'
                WHEN total_games < 100 THEN '2 medium (50-99)'
                ELSE                        '3 high (100+)'
           END AS engagement_segment
    FROM dim_player
)
SELECT engagement_segment,
       COUNT(*)       AS players,
       SUM(churned)   AS churned,
       CAST(100.0 * SUM(churned) / COUNT(*) AS DECIMAL(5,1)) AS churn_rate_pct
FROM segments
GROUP BY engagement_segment
ORDER BY engagement_segment;
GO

/* ---- 9. Churn rate per tier, only tiers with enough players ----
   HAVING drops sparse tiers so each rate rests on a real sample. ---- */
SELECT p.tier,
       COUNT(*)       AS players,
       SUM(p.churned) AS churned,
       CAST(100.0 * SUM(p.churned) / COUNT(*) AS DECIMAL(5,1)) AS churn_rate_pct
FROM dim_player p
GROUP BY p.tier
HAVING COUNT(*) >= 20
ORDER BY churn_rate_pct DESC;
GO

/* ---- 10. Churn rate by account age bucket ---- */
WITH ages AS (
    SELECT churned,
           CASE WHEN account_level < 100 THEN '1 new (<100)'
                WHEN account_level < 300 THEN '2 mid (100-299)'
                ELSE                          '3 veteran (300+)'
           END AS account_age
    FROM dim_player
)
SELECT account_age,
       COUNT(*)     AS players,
       SUM(churned) AS churned,
       CAST(100.0 * SUM(churned) / COUNT(*) AS DECIMAL(5,1)) AS churn_rate_pct
FROM ages
GROUP BY account_age
ORDER BY account_age;
GO
