ALTER TABLE status_history ADD COLUMN
    num_players INTEGER NOT NULL DEFAULT 0 CHECK (num_players >= 0);
ALTER TABLE status_display ADD COLUMN
    graph_interval INTERVAL NOT NULL DEFAULT 86400000 CHECK (graph_interval >= 0);
