# ministatus

[![](https://img.shields.io/pypi/v/ministatus?style=flat-square&logo=pypi)](https://pypi.org/project/ministatus/)
[![](https://img.shields.io/github/actions/workflow/status/thegamecracks/ministatus/publish.yml?style=flat-square&logo=uv&label=build)](https://docs.astral.sh/uv/)
[![](https://img.shields.io/github/actions/workflow/status/thegamecracks/ministatus/pyright-lint.yml?style=flat-square&label=pyright)](https://microsoft.github.io/pyright/#/)
[![](https://img.shields.io/github/actions/workflow/status/thegamecracks/ministatus/ruff-check.yml?style=flat-square&logo=ruff&label=lints)](https://docs.astral.sh/ruff/)
[![](https://img.shields.io/github/actions/workflow/status/thegamecracks/ministatus/ruff-format.yml?style=flat-square&logo=ruff&label=style)](https://docs.astral.sh/ruff/)

![Ministatus banner](https://github.com/user-attachments/assets/d8276cec-727d-4805-8eff-b97c52e85fcf)

A Discord bot for managing game server status embeds.

## Table of Contents

- [ministatus](#ministatus)
  - [Table of Contents](#table-of-contents)
  - [Supported Games / Query Protocols](#supported-games--query-protocols)
  - [Installation](#installation)
  - [Setup](#setup)
  - [Docker](#docker)
  - [Usage](#usage)
    - [Alerts](#alerts)
    - [Displays](#displays)
    - [Queries](#queries)
  - [Downtime Detection](#downtime-detection)
  - [Refresh Intervals](#refresh-intervals)
  - [DNS Lookups (Technical)](#dns-lookups-technical)
  - [Other CLI commands](#other-cli-commands)
  - [Environment Variables](#environment-variables)
  - [License](#license)

## Supported Games / Query Protocols

- Arma 3
- Arma Reforger
- FiveM
- Minecraft (Bedrock Edition)
- Minecraft (Java Edition)
- Project Zomboid
- TeamSpeak 3
- Valve Source Query (A2S)

## Installation

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

Or run in a container with [Docker] or [Podman]:

```sh
$ docker pull ghcr.io/thegamecracks/ministatus
$ docker run --rm -it ministatus
```

![Terminal demonstration](https://github.com/user-attachments/assets/9d134fb4-446b-47cf-9697-867ab748d346)

[pipx]: https://pipx.pypa.io/latest/
[uv]: https://docs.astral.sh/uv/
[Docker]: https://docs.docker.com/
[Podman]: https://podman.io/

## Setup

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

## Docker

Our Docker images are hosted in the [GitHub Container Registry]. Starting a container
from an image doesn't run the bot immediately, but it instead provides the command-line
interface shown in the previous section. If you're planning to host from an image,
you should mount a volume to persist the bot's application state:

```sh
$ mkdir data && chmod 777 data  # see warning at end
$ VOLUME=./data:/home/nonroot/.local/share
$ docker pull ghcr.io/thegamecracks/ministatus
$ docker run --rm -it -v $VOLUME ministatus
Usage: ministatus [OPTIONS] COMMAND [ARGS]...

  A Discord bot for managing game server status embeds.
```

[GitHub Container Registry]: https://github.com/thegamecracks/ministatus/pkgs/container/ministatus

To start the bot without manually entering your bot token, pass the
[MIST_TOKEN](#environment-variables) environment variable with `-e MIST_TOKEN=value`
or `--env-file <path>`, and invoke the `start` command:

```sh
$ echo 'MIST_TOKEN=abc.def.xyz' > .env
$ docker run --rm -it --env-file .env -v $VOLUME ministatus start
2025-11-28 04:48:03 INFO     ministatus.db.migrations Migrating database to v5
2025-11-28 04:48:03 INFO     ministatus.cli.commands Reading token from MIST_TOKEN environment variable
2025-11-28 04:48:04 INFO     discord.client logging in using static token
...
```

> [!WARNING]
> This ministatus image uses a non-root user for execution.
>
> If you have a bind mount like `-v ./data:/home/nonroot/.local/share`,
> you may need to change the host directory's permissions, `data` in this example,
> such that other users are allowed to write to it. Otherwise, it's possible to
> get an error like this:
>
> ```py
> $ docker run --rm -it -v ./data:/home/nonroot/.local/share ministatus start
> Traceback (most recent call last):
>   ...
> PermissionError: [Errno 13] Permission denied: '/home/nonroot/.local/share/ministatus'`
> ```
>
> If you see this permission error, try the following to fix it (assuming a Linux host):
>
> ```sh
> $ chmod 777 data
> $ docker run --rm -it -v ./data:/home/nonroot/.local/share ministatus start
> ```
>
> If you need to delete your data directory and encounter a permission error like
> `rm: cannot remove 'data/ministatus/ministatus.db': Permission denied`,
> you can either delete it as root or use another container with root access to
> delete it (and of course, **please make sure you're deleting the right directory**):
>
> ```
> $ ls data
> ministatus
> $ sudo rm -rf data
> # or:
> $ docker run --rm -it -v ./data:/data docker.io/library/busybox rm -rf /data
> rm: can't remove '/data': Device or resource busy
> $ rm -rf data
> ```
>
> Alternatively, you can use a named volume instead of a bind mount which allows
> Docker to correctly handle the permissions for you:
>
> ```sh
> $ docker run --rm -it -v mist-data:/home/nonroot/.local/share ministatus start
> # To remove:
> $ docker volume rm mist-data
> ```

## Usage

When added to a server, any members with the Manage Server permission can use
the `/status manage` slash command to create statuses for that server.
A Discord server can have multiple statuses to track different game servers.
Each status can define one or more of the following components:
1. Alerts
2. Displays
3. Queries

All three components can be enabled and disabled at any time, allowing you to switch
between components without permanently deleting them. For example, you could have a
status that has one alert and one display, but two queries for different game servers,
with only one query enabled to display whichever game's stats you want at a given time.
As well, the status itself can be disabled to halt all its components at once.

Statuses are specific to each Discord server, so admins in one server won't
be able to share or modify statuses in another server.

![Command demonstration](https://github.com/user-attachments/assets/c382fc35-ab9e-4ae6-9874-6e52e3dd8c94)

> [!CAUTION]
> To avoid potential abuse, it is strongly recommended to **NOT** use this
> in a public bot. You should only invite this bot to servers with admins
> that you trust.

### Alerts

Alerts are channels that the bot uses to send events related to its status.

Alert messages are categorized into audit and downtime. Downtime events indicate when
the server goes online or offline, while audit events indicate failures in the status,
such as missing permissions to edit a display or a misconfigured query.

Alerts can be filtered to one or both events, so you might send downtime notifications
to a public channel for members to see, and audit events to a private channel
for staff to help diagnose failing statuses.

### Displays

Displays are messages sent by the bot which are routinely updated to reflect
the latest data provided by the status's queries. Displays have an accent colour,
graph colour, and a graph period between 1 hour and 30 days.
A status can have multiple displays, allowing the same data to be rendered
across many messages. For most users, we recommend one display per status.

Displays are dependent on queries, and will only update if the parent status
has at least one enabled query. Displays only show information from the first
successful query in the status (see [Queries](#queries) below). If you need
two displays to show different game servers, you should create two statuses
and add a display + query to each one.

While the bot is online, deleting a display through the `/status manage` command
will automatically delete its Discord message, and vice versa. If the parent status
is deleted, all its displays are deleted with it.

### Queries

Queries are the protocols used to query game servers for their state.
The admin must provide the server's address or hostname, the query type
(see [Supported Games](#supported-games--query-protocols)), the game / query port,
and a priority value (0). The game port is the port used by players to connect,
shown next to the server's address, and the query port is the port used by the bot
to query the server. Some query types only require the game port, in which case
the bot won't prompt for a query port.

Queries operate independently of displays, so a status without any displays can
still query its game server and trigger downtime alerts.

If multiple queries are enabled on a single status, the query with the highest
priority (lowest number) is tested first, and if it fails, the next query is
tested instead. If all queries fail, the status is recorded as offline.
For most users, we recommend adding and enabling exactly one query per status.

Continuously failing query methods will be automatically disabled after 24 hours.
This triggers an audit alert with the reason `Offline for extended period of time`.

## Downtime Detection

After a query fails once, displays won't immediately report the server as `Offline 🔴`,
but will instead show an intermediary `Online 🟡` status and continue to present the
last known player count and list.

If the server responds within two queries, the status re-appears as `Online 🟢`
and the player list is updated like normal. However, if three consecutive queries fail,
the status returns `Offline 🔴` and downtime alerts are sent. The next time the query
succeeds, the status will return online and a corresponding alert will be sent.

Player graphs will avoid rendering `Online 🟡` intermediary datapoints,
reducing outliers that cause "spikes" in the graph.

## Refresh Intervals

By default, all status displays and queries are updated every minute, with image
attachments being re-uploaded every ten minutes. Server admins cannot change these
intervals, but the hoster can change this globally using the `ministatus config`
CLI command:

```sh
$ ministatus config status-interval 60
$ ministatus config status-interval-attachments 600
```

The max concurrency is also set to one by default, meaning the bot will process
all queries and displays of one status at a time. You can increase this to update
multiple statuses in parallel, at the cost of higher peak CPU usage and network
traffic per interval:

```sh
$ ministatus config status-max-concurrency 16
```

## DNS Lookups (Technical)

When a domain name is specified, like `ia.420thdelta.net`, the bot will attempt
to resolve any `A` record associated with that hostname to find an IPv4 address
to query. If not present, an `AAAA` record is looked up for its IPv6 address instead.
If either DNS record can be found, the query is sent to that address with the provided
game / query port. Otherwise, the query is considered invalid and disabled, sending
an audit alert with the reason `DNS name does not exist`. If multiple `A` or `AAAA`
records are defined, only the first one will be used.

For certain games, that being Arma 3, FiveM, Minecraft (Java Edition), and TeamSpeak 3\*,
you can also specify port 0 to indicate that an `SRV` record should be looked up instead.
If the record exists, it will use its defined target hostname and port to query the server,
performing the same `A` / `AAAA` record lookups on the target.
The game port will also be omitted from displays, since members can connect using
the hostname directly. If the query port is 0 and no `SRV` record exists, or the
game type doesn't support `SRV` records, the query is invalidated.
`SRV` records are never used if an explicit game / query port is provided.

> [!NOTE]
> For TeamSpeak 3, the "game port" and "query port" as shown by Ministatus maps to the
> TS query port and voice port respectively. This is because only the latter supports
> SRV records, and the TS query port has no SRV record. If you specify 0 for both
> "game port" and "query port", the TS query port is assumed to be 10011, and the
> voice port will be looked up using the SRV record.

## Other CLI commands

View where files are saved:

```sh
$ ministatus appdirs
user_data_path    = /home/thegamecracks/.local/share/ministatus
user_log_path     = /home/thegamecracks/.local/state/ministatus/log
$ ministatus db path
/home/thegamecracks/.local/share/ministatus/ministatus.db
```

View or change configuration settings:

```sh
$ ministatus config
Settings:
    appid = 1430326736775544903
    status-interval = 60
    status-interval-attachments = 600
    status-max-concurrency = 1
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
