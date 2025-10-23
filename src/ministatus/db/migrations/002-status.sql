-- Server statuses to track
CREATE TABLE status (
    status_id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES discord_user (user_id) ON DELETE CASCADE,
    label TEXT NOT NULL, -- User-defined label

    title TEXT,     -- Cached server name
    address TEXT,   -- Cached address for players to connect
    thumbnail BLOB, -- Cached server thumbnail

    enabled_at TIMESTAMP
);

-- Discord channels to send downtime alerts to
CREATE TABLE status_alert (
    status_id BIGINT PRIMARY KEY
        REFERENCES status (status_id) ON DELETE CASCADE,
    channel_id BIGINT NOT NULL
        REFERENCES status (status_id) ON DELETE CASCADE,

    enabled_at TIMESTAMP

    -- In theory multiple status alerts could be defined,
    -- but most users are fine with one alert channel.
    -- PRIMARY KEY (status_id, channel_id)
);

-- Discord messages to periodically display status info
CREATE TABLE status_display (
    message_id BIGINT PRIMARY KEY
        REFERENCES discord_message (message_id) ON DELETE CASCADE,
    status_id BIGINT NOT NULL
        REFERENCES status (status_id) ON DELETE CASCADE,

    enabled_at TIMESTAMP,
    accent_colour INTEGER NOT NULL DEFAULT 0xFFFFFF CHECK (accent_colour BETWEEN 0 AND 0xFFFFFF),
    graph_colour INTEGER NOT NULL DEFAULT 0xFFFFFF CHECK (graph_colour BETWEEN 0 AND 0xFFFFFF)
);

-- Timeseries data for each status
CREATE TABLE status_history (
    status_history_id BIGINT PRIMARY KEY,
    created_at TIMESTAMP NOT NULL,
    status_id BIGINT NOT NULL
        REFERENCES status (status_id) ON DELETE CASCADE,
    online BOOLEAN NOT NULL
);

-- Players online at a given status datapoint
CREATE TABLE status_history_player (
    status_history_player_id BIGINT PRIMARY KEY,
    status_history_id BIGINT NOT NULL
        REFERENCES status_history (status_history_id) ON DELETE CASCADE,
    player_name TEXT NOT NULL
);

-- Methods to query server statuses
CREATE TABLE status_query (
    status_id BIGINT
        REFERENCES status (status_id) ON DELETE CASCADE,
    host TEXT NOT NULL,
    port BIGINT NOT NULL CHECK (port BETWEEN 0 AND 65535), -- port 0 means SRV lookup
    type TEXT NOT NULL, -- Type of query to perform (should be an enum)
    priority INTEGER NOT NULL DEFAULT 0, -- Order in which query methods are used (usually one per status)

    enabled_at TIMESTAMP,
    extra JSONB, -- Extra data relevant to query type
    failed_at TIMESTAMP, -- Time since last successful query

    PRIMARY KEY (status_id, host, port)
);

-- Cascading foreign key indexes
CREATE INDEX ix_status_user_id ON status (user_id);
CREATE INDEX ix_status_alert_channel_id ON status_alert (channel_id);
CREATE INDEX ix_status_display_status_id ON status_display (status_id);
CREATE INDEX ix_status_history_status_id ON status_history (status_id);
CREATE INDEX ix_status_history_player_status_history_id ON status_history_player (status_history_id);

-- Optimize time-based queries on status history (largest index)
CREATE INDEX ix_status_history_status_id_created_at ON status_history (status_id, created_at);
