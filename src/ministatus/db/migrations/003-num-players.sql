ALTER TABLE status_history ADD COLUMN
    num_players INTEGER NOT NULL DEFAULT 0 CHECK (num_players >= 0);
ALTER TABLE status_display ADD COLUMN
    graph_interval INTERVAL NOT NULL DEFAULT 86400000 CHECK (graph_interval >= 0);

-- Convert second-based timestamps to milliseconds
UPDATE status SET enabled_at = enabled_at * 1000, failed_at = failed_at * 1000;
UPDATE status_alert SET enabled_at = enabled_at * 1000, failed_at = failed_at * 1000;
UPDATE status_display SET enabled_at = enabled_at * 1000, failed_at = failed_at * 1000;
UPDATE status_history SET created_at = created_at * 1000;
UPDATE status_query SET enabled_at = enabled_at * 1000, failed_at = failed_at * 1000;
