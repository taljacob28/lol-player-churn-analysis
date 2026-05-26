/* ============================================================
   01_star_schema.sql
   Build the star schema dimensions from the loaded base tables.
   Run after src/load_to_sqlserver.py has created
   fact_player_match and dim_player. Safe to re-run.
   ============================================================ */
USE LoLChurnAnalysis;
GO

/* ---- Convert loaded text columns to bounded types ----
   pandas loads text as NVARCHAR(MAX), which cannot be indexed
   or used as a key, so we size them down first. ---- */
ALTER TABLE dim_player        ALTER COLUMN puuid VARCHAR(100) NOT NULL;
GO
ALTER TABLE fact_player_match ALTER COLUMN puuid     VARCHAR(100);
GO
ALTER TABLE fact_player_match ALTER COLUMN champion  VARCHAR(50);
GO
ALTER TABLE fact_player_match ALTER COLUMN game_date DATE;
GO

/* ---- dim_player: primary key on the player table ---- */
IF NOT EXISTS (SELECT 1 FROM sys.key_constraints WHERE name = 'PK_dim_player')
    ALTER TABLE dim_player ADD CONSTRAINT PK_dim_player PRIMARY KEY (puuid);
GO

/* ---- dim_champion: one row per champion ---- */
IF OBJECT_ID('dim_champion', 'U') IS NOT NULL DROP TABLE dim_champion;
GO
SELECT IDENTITY(INT, 1, 1) AS champion_key,
       CAST(champion AS VARCHAR(50)) AS champion
INTO dim_champion
FROM (SELECT DISTINCT champion FROM fact_player_match) c;
GO
ALTER TABLE dim_champion ADD CONSTRAINT PK_dim_champion PRIMARY KEY (champion_key);
GO

/* ---- dim_date: one row per calendar date with attributes ---- */
IF OBJECT_ID('dim_date', 'U') IS NOT NULL DROP TABLE dim_date;
GO
SELECT IDENTITY(INT, 1, 1) AS date_key,
       game_date,
       DATEPART(YEAR,     game_date) AS [year],
       DATEPART(MONTH,    game_date) AS [month],
       DATEPART(ISO_WEEK, game_date) AS iso_week,
       DATENAME(WEEKDAY,  game_date) AS weekday_name
INTO dim_date
FROM (SELECT DISTINCT game_date FROM fact_player_match) d;
GO
ALTER TABLE dim_date ADD CONSTRAINT PK_dim_date PRIMARY KEY (date_key);
GO

/* ---- dim_tier: tier to band lookup ---- */
IF OBJECT_ID('dim_tier', 'U') IS NOT NULL DROP TABLE dim_tier;
GO
CREATE TABLE dim_tier (tier VARCHAR(20) PRIMARY KEY, tier_band VARCHAR(10));
INSERT INTO dim_tier VALUES
 ('IRON','low'),('BRONZE','low'),('SILVER','low'),
 ('GOLD','mid'),('PLATINUM','mid'),('EMERALD','mid'),
 ('DIAMOND','high'),('MASTER','high'),('GRANDMASTER','high'),('CHALLENGER','high');
GO

/* ---- indexes on the fact for the analysis joins ---- */
DROP INDEX IF EXISTS IX_fact_puuid    ON fact_player_match;
DROP INDEX IF EXISTS IX_fact_champion ON fact_player_match;
DROP INDEX IF EXISTS IX_fact_date     ON fact_player_match;
GO
CREATE INDEX IX_fact_puuid    ON fact_player_match (puuid);
CREATE INDEX IX_fact_champion ON fact_player_match (champion);
CREATE INDEX IX_fact_date     ON fact_player_match (game_date);
GO

PRINT 'Star schema built: fact_player_match, dim_player, dim_champion, dim_date, dim_tier.';
GO
