# ministatus

[![](https://img.shields.io/pypi/v/ministatus?style=flat-square&logo=pypi)](https://pypi.org/project/ministatus/)
[![](https://img.shields.io/github/actions/workflow/status/thegamecracks/ministatus/publish.yml?style=flat-square&logo=uv&label=build)](https://docs.astral.sh/uv/)
[![](https://img.shields.io/github/actions/workflow/status/thegamecracks/ministatus/pyright-lint.yml?style=flat-square&label=pyright)](https://microsoft.github.io/pyright/#/)
[![](https://img.shields.io/github/actions/workflow/status/thegamecracks/ministatus/ruff-check.yml?style=flat-square&logo=ruff&label=lints)](https://docs.astral.sh/ruff/)
[![](https://img.shields.io/github/actions/workflow/status/thegamecracks/ministatus/ruff-format.yml?style=flat-square&logo=ruff&label=style)](https://docs.astral.sh/ruff/)

A Discord bot for managing game server status embeds.

![Status display](https://github.com/user-attachments/assets/f5420d7f-0865-41a0-81da-f1e45c4780d2)
![Terminal demonstration](https://github.com/user-attachments/assets/9d134fb4-446b-47cf-9697-867ab748d346)
![Command demonstration](https://github.com/user-attachments/assets/c382fc35-ab9e-4ae6-9874-6e52e3dd8c94)

## Supported Games / Query Protocols

- Arma 3
- Arma Reforger
- FiveM
- Minecraft (Bedrock Edition)
- Minecraft (Java Edition)
- Project Zomboid
- Valve Source Query (A2S)

## Setup

This project requires Python 3.11 or newer. You can manually install this
project into a virtual environment:

```sh
$ python3 -m venv
$ .venv/bin/activate
(.venv) $ pip install ministatus
(.venv) $ ministatus  # or python3 -m ministatus
```

Or use one of [pipx] or [uv] to manage the virtual environment for you:

```sh
$ pipx install ministatus
$ ministatus
# Or:
$ uv tool install ministatus
$ ministatus
# Or:
$ uvx ministatus
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
  invite   Print the bot's invite link.
  start    Start the Discord bot in the current process.
```

To start the bot and store your bot token:

```sh
$ ministatus start
2025-11-03 12:55:43 INFO     ministatus.db.migrations Migrating database to v5
No Discord bot token found in config.
Your token should look something like this:
MTI0NjgyNjg0MTIzMTMyNzI3NQ.GTIAZm.x2fbSNuYJgpAocvMM53ROlMC23NixWt-0NOjMc
Enter token:
2025-11-03 12:55:47 INFO     discord.client logging in using static token
2025-11-03 12:55:47 INFO     ministatus.bot.bot Loading extension ministatus.bot.cogs.cleanup
2025-11-03 12:55:47 INFO     ministatus.bot.bot Loading extension ministatus.bot.cogs.errors
2025-11-03 12:55:47 INFO     ministatus.bot.bot Loading extension ministatus.bot.cogs.owner
2025-11-03 12:55:47 INFO     ministatus.bot.bot Loading extension ministatus.bot.cogs.status
2025-11-03 12:55:47 INFO     ministatus.bot.bot Invite link:
    https://discord.com/oauth2/authorize?client_id=...
2025-11-03 12:55:47 INFO     ministatus.bot.cogs.status.cog Waiting 12.28s before starting query loop...
2025-11-03 12:55:47 INFO     discord.gateway Shard ID None has connected to Gateway.
```

To synchronize the bot's application commands with Discord, invite the bot to
a server and send the message, `@mention sync`, to run the sync command.
Alternatively, you can synchronize application commands during startup
by using the `--sync` flag:

```sh
$ ministatus start --sync
```

Make sure to **only** synchronize once to avoid being ratelimited by Discord.
If ministatus is updated with changes to application commands, you may need
to synchronize them again.

### Other commands

View where files are saved:

```sh
$ ministatus appdirs
user_data_path    = /home/thegamecracks/.local/share/ministatus
user_log_path     = /home/thegamecracks/.local/state/ministatus/log
$ ministatus db path
/home/ministatus/.local/share/ministatus/ministatus.db
```

View or change configuration settings:

```sh
$ ministatus config
Settings:
    appid = 1430326736775544903
    status-interval = 60
    token = ****

$ ministatus config --unset token  # unset token
$ ministatus config token xyz      # set token=xyz
$ ministatus config token          # get token
xyz
```

Enable database encryption (see notes below):

```sh
$ export MIST_PASSWORD=abc123
$ ministatus db encrypt
Successfully encrypted!
# Alteneratively use -p/--password:
$ ministatus -p abc123 db encrypt
Database is already encrypted 😴
# Or type the password interactively:
$ unset MIST_PASSWORD
$ ministatus config
Database Password:
There are no settings defined 🙁
```

> [!NOTE]
> This requires [SQLite3MultipleCiphers], [SQLCipher], or an equivalent extension
> with `PRAGMA key` and `PRAGMA rekey` support. This is only possible if you
> are able to replace the sqlite3.dll or .so shared library used by Python.
>
> In the case of uv-managed Python installations, they are statically built
> against SQLite and cannot be used with encryption extensions.

[SQLite3MultipleCiphers]: https://github.com/utelle/SQLite3MultipleCiphers
[SQLCipher]: https://github.com/sqlcipher/sqlcipher

## Environment Variables

The following environment variables are supported:

- `MIST_APPDIR_SUFFIX`

  The suffix to append to the application directory, changing where the database
  and log files are written to. This allows for multiple instances of ministatus
  to run on the same user, as each instance uses a separate database and can load
  different Discord bot tokens.

  For example, `MIST_APPDIR_SUFFIX=2` results in data files being stored in
  `~/.local/share/ministatus-2` on Linux, and
  `C:\Users\<name>\AppData\Local\thegamecracks\ministatus-2` on Windows.

- `MIST_PASSWORD`

  The password to use for encrypting and decrypting the database.
  Most commands will abort if the database isn't already encrypted,
  aside from `ministatus db encrypt` itself and commands that don't
  require database access like `ministatus appdirs`.

  Alternatively, you can use the `ministatus -p <password> ...` option to provide
  a password, `ministatus -p "" ...` to always prompt for a password, or simply
  omit it and let ministatus prompt for the database password when needed.
  Note that the `-p <password>` form may be logged by your terminal to some
  history like `.bash_history`.

- `MIST_TOKEN`

  The Discord bot's token. This supersedes any token stored in the database.
  This token will also not be committed to the database, so omitting this
  afterwards will use the previously stored token or prompt for a new token.

> [!NOTE]
> Environment variables defined in a `.env` file are currently not recognized
> by ministatus. You should set these using `export ABC=123` on Linux,
> `set ABC=123` on Windows, or another equivalent method.

## License

This project is written under the [MIT License].

[MIT License]: /LICENSE
