ALTER TABLE status_history ADD COLUMN down BOOLEAN NOT NULL DEFAULT 0;

-- Consider 3 consecutive offline rows as downtime
UPDATE status_history AS h SET down = (n_online < 1)
FROM (
    SELECT
        status_history_id,
        SUM(online) OVER (ROWS 2 PRECEDING) AS n_online
    FROM status_history
) AS recent
WHERE h.status_history_id = recent.status_history_id;
