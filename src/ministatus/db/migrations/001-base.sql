CREATE TABLE setting (
    name TEXT PRIMARY KEY,
    value,
    secret BOOLEAN NOT NULL DEFAULT 0
);

CREATE TABLE discord_user (user_id INTEGER PRIMARY KEY);
CREATE TABLE discord_guild (guild_id INTEGER PRIMARY KEY);

CREATE TABLE discord_channel (
    channel_id INTEGER PRIMARY KEY,
    guild_id INTEGER
        REFERENCES discord_guild (guild_id)
        ON DELETE CASCADE
);

CREATE TABLE discord_message (
    message_id INTEGER PRIMARY KEY,
    channel_id INTEGER NOT NULL
        REFERENCES discord_channel (channel_id)
        ON DELETE CASCADE
);

CREATE TABLE discord_member (
    guild_id INTEGER
        REFERENCES discord_guild (guild_id)
        ON DELETE CASCADE,
    user_id INTEGER
        REFERENCES discord_user (user_id)
        ON DELETE CASCADE,
    PRIMARY KEY (guild_id, user_id)
);

-- Cascading foreign key indexes
CREATE INDEX ix_discord_channel_guild_id ON discord_channel (guild_id);
CREATE INDEX ix_discord_message_channel_id ON discord_message (channel_id);
CREATE INDEX ix_discord_member_user_id ON discord_member (user_id);
