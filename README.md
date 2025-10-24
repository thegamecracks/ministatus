# ministatus

![Terminal demonstration](https://github.com/user-attachments/assets/17f4ce1f-a40c-4244-9e80-132f2bc7cfdc)

A Discord bot for managing game server status embeds.

## Setup

This project requires Python 3.11 or newer. You can manually install this
project into a virtual environment:

```sh
/ $ git clone https://github.com/thegamecracks/ministatus
/ $ cd ministatus
/ministatus $ python3 -m venv
/ministatus $ .venv/bin/activate
(.venv) /ministatus $ pip install .
(.venv) /ministatus $ ministatus  # or python3 -m ministatus
```

Or use one of [pipx] or [uv] to manage the virtual environment for you:

```sh
/ministatus $ pipx install .
/ministatus $ ministatus
# Or:
/ministatus $ uv tool install .
/ministatus $ ministatus
# Or:
/ministatus $ uv run -m ministatus
```

[pipx]: https://pipx.pypa.io/latest/
[uv]: https://docs.astral.sh/uv/

## Usage

```sh
$ ministatus
Usage: ministatus [OPTIONS] COMMAND [ARGS]...

  A Discord bot for managing game server status embeds.

Options:
  -p, --password SECRET  The password to unlock the database, if any
  -v, --verbose          Increase logging verbosity.
  -V, --version          Show the version and exit.
  -h, --help             Show this message and exit.

Commands:
  appdirs  Show directories and important files used by this application.
  config   Get or set a configuration setting.
  db       Manage the application database.
  start    Start the Discord bot in the current process.
  status   Manage server statuses.
```

View where files are saved:

```sh
$ ministatus appdirs
user_data_path    = /home/thegamecracks/.local/share/ministatus
user_log_path     = /home/thegamecracks/.local/state/ministatus/log
DB_PATH           = /home/thegamecracks/.local/share/ministatus/ministatus.db
```

Enable database encryption:

```sh
$ export MIST_PASSWORD=abc123
$ ministatus db encrypt
Successfully encrypted!
# Alteneratively use -p/--pasword:
$ ministatus -p abc123 db decrypt
Database is already encrypted 😴
# Or type the password interactively:
$ unset MIST_PASSWORD
$ ministatus config
There are no settings defined 🙁
```

> [!NOTE]
> This requires [SQLite3MultipleCiphers], [SQLCipher], or an equivalent library
> with `PRAGMA key` and `PRAGMA rekey` support.

[SQLite3MultipleCiphers]: https://github.com/utelle/SQLite3MultipleCiphers
[SQLCipher]: https://github.com/sqlcipher/sqlcipher

Start the bot and store your bot token:

```sh
$ ministatus start
2025-10-23 04:01:17 INFO     ministatus.db.migrations Migrating database to v1
2025-10-23 04:01:17 INFO     ministatus.db.migrations Migrating database to v2
No Discord bot token found in config.
Would you like to enter your token now?
You can change your token at any time using the 'config' command.
 [y/N]: y
Your Discord bot token should look something like this:
    MTI0NjgyNjg0MTIzMTMyNzI3NQ.GTIAZm.x2fbSNuYJgpAocvMM53ROlMC23NixWt-0NOjMc
Token:
2025-10-23 04:01:21 WARNING  discord.client PyNaCl is not installed, voice will NOT be supported
2025-10-23 04:01:21 INFO     discord.client logging in using static token
2025-10-23 04:01:21 INFO     ministatus.bot.bot Loading extension ministatus.bot.cogs.status
2025-10-23 04:01:21 INFO     ministatus.bot.bot Loaded jishaku extension (v2.6.3)
2025-10-23 04:01:21 INFO     ministatus.bot.cogs.status.cog Waiting 38.22s before starting query loop...
2025-10-23 04:01:22 INFO     discord.gateway Shard ID None has connected to Gateway (Session ID: 9bd2e577bbc4a21be5eed933900d076f).
```

View or change configuration settings:

```sh
$ ministatus config
Settings:
    token = ****

$ ministatus config token xyz
$ ministatus config token
xyz
```

TODO: create server status

## License

This project is written under the [MIT License].

[MIT License]: /LICENSE
