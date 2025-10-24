-- Server statuses to track
CREATE TABLE status (
    status_id INTEGER PRIMARY KEY,
    guild_id INTEGER NOT NULL REFERENCES discord_guild (guild_id) ON DELETE CASCADE,
    label TEXT NOT NULL, -- User-defined label

    title TEXT,     -- Cached server name
    address TEXT,   -- Cached address for players to connect
    thumbnail BLOB, -- Cached server thumbnail

    enabled_at TIMESTAMP
);

-- Discord channels to send downtime alerts to
CREATE TABLE status_alert (
    status_id INTEGER
        REFERENCES status (status_id) ON DELETE CASCADE,
    channel_id INTEGER -- CAUTION: missing constraint on status.guild_id
        REFERENCES discord_channel (channel_id) ON DELETE CASCADE,

    enabled_at TIMESTAMP,

    PRIMARY KEY (status_id, channel_id)
);

-- Discord messages to periodically display status info
CREATE TABLE status_display (
    message_id INTEGER PRIMARY KEY -- CAUTION: missing constraint on status.guild_id
        REFERENCES discord_message (message_id) ON DELETE CASCADE,
    status_id INTEGER NOT NULL
        REFERENCES status (status_id) ON DELETE CASCADE,

    enabled_at TIMESTAMP,
    accent_colour INTEGER NOT NULL DEFAULT 0xFFFFFF CHECK (accent_colour BETWEEN 0 AND 0xFFFFFF),
    graph_colour INTEGER NOT NULL DEFAULT 0xFFFFFF CHECK (graph_colour BETWEEN 0 AND 0xFFFFFF)
);

-- Timeseries data for each status
CREATE TABLE status_history (
    status_history_id INTEGER PRIMARY KEY,
    created_at TIMESTAMP NOT NULL,
    status_id INTEGER NOT NULL
        REFERENCES status (status_id) ON DELETE CASCADE,
    online BOOLEAN NOT NULL,

    max_players INTEGER NOT NULL DEFAULT 0 CHECK (max_players >= 0)
);

-- Players online at a given status datapoint
CREATE TABLE status_history_player (
    status_history_player_id INTEGER PRIMARY KEY,
    status_history_id INTEGER NOT NULL
        REFERENCES status_history (status_history_id) ON DELETE CASCADE,
    player_name TEXT NOT NULL
);

-- Methods to query server statuses
CREATE TABLE status_query (
    status_query_id INTEGER PRIMARY KEY,
    status_id INTEGER NOT NULL
        REFERENCES status (status_id) ON DELETE CASCADE,
    host TEXT NOT NULL,
    port INTEGER NOT NULL CHECK (port BETWEEN 0 AND 65535), -- port 0 means SRV lookup
    type TEXT NOT NULL, -- Type of query to perform (should be an enum)
    priority INTEGER NOT NULL DEFAULT 0, -- Order in which query methods are used (usually one per status)

    enabled_at TIMESTAMP,
    extra JSONB, -- Extra data relevant to query type
    failed_at TIMESTAMP, -- Time since last successful query

    CONSTRAINT unique_status_host_port UNIQUE (status_id, host, port)
);

-- Cascading foreign key indexes
CREATE INDEX ix_status_alert_channel_id ON status_alert (channel_id);
CREATE INDEX ix_status_display_status_id ON status_display (status_id);
CREATE INDEX ix_status_history_status_id ON status_history (status_id);
CREATE INDEX ix_status_history_player_status_history_id ON status_history_player (status_history_id);

-- Ensure status.label uniqueness per guild
CREATE UNIQUE INDEX ix_status_guild_id_label ON status (guild_id, label);

-- Optimize time-based queries on status history (largest index)
CREATE INDEX ix_status_history_status_id_created_at ON status_history (status_id, created_at);
