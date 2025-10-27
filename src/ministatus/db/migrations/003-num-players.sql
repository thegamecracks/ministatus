ALTER TABLE status_history ADD COLUMN
    num_players INTEGER NOT NULL DEFAULT 0 CHECK (max_players >= 0);
