# LoL Spy

A Discord bot that posts in your server when a friend **starts** a League of Legends
game — who they are, which champion they picked, and which mode.

Each game is announced once, when it begins. When it ends the friend is forgotten, so
their next game announces again.

## Setup

```bash
pip install -r requirements.txt
cp config.example.json config.json
```

Then fill in `config.json`:

| Key | Required | Default | What it is |
|---|---|---|---|
| `DISCORD_TOKEN` | yes | | Bot token from the [Discord developer portal](https://discord.com/developers/applications). |
| `RIOT_API_KEY` | yes | | Key from the [Riot developer portal](https://developer.riotgames.com/). |
| `CHANNEL_ID` | yes | | The channel to post in. Enable Developer Mode in Discord, then right-click the channel and Copy ID. |
| `FRIENDS_LIST` | yes | | One `{"gameName": "...", "tagLine": "..."}` per friend — the two halves of a Riot ID, so `Faker#KR1` is `{"gameName": "Faker", "tagLine": "KR1"}`. |
| `PLATFORM` | no | `la2` | Which server your friends play on: `la1`, `la2`, `na1`, `euw1`, `kr`… |
| `REGION` | no | `americas` | Routing for Riot ID lookups: `americas`, `europe`, `asia`. |
| `POLL_SECONDS` | no | `60` | How often to check. |
| `REQUESTS_PER_MINUTE` | no | `100` | Cap on requests to Riot. A development key allows 100 per 2 minutes, so lower this to `50` if you are using one. |
| `ANNOUNCE_WHEN_IDLE` | no | `false` | Also post once when everyone has stopped playing. |

`config.json` is gitignored — your tokens stay out of the repository.

Run it:

```bash
python lol_spy.py
```

The bot needs no privileged intents. It reads game state from Riot rather than from
Discord presence, so there is nothing to enable in the developer portal beyond
creating the bot and inviting it.

## How it stays inside Riot's rate limits

Riot's limits are per-minute, so the bot enforces a **rolling sixty-second window**:
before every request it checks how many were started in the last minute and waits
exactly as long as the oldest one has left to age out.

Two things keep the request count down:

- The **champion list is fetched once per patch**, not per notification. It comes from
  Data Dragon, which is not rate limited, and is cached for twelve hours.
- A friend whose game has already been announced still costs one status check per
  round, but nothing more.

With eight friends at the default sixty-second interval that's roughly 8 requests a
minute, well inside a development key.

## When things go wrong

- A **malformed or incomplete `config.json`** names the missing key and stops, rather
  than failing later with a `KeyError`.
- A **Riot ID that will not resolve** is retried every round, so a hiccup at startup
  doesn't drop that friend for the bot's lifetime.
- A **429 from Riot** is respected: the bot reads `Retry-After` and waits.
- If **Data Dragon is unreachable**, the last known champion list is reused; if there
  isn't one yet, the announcement names the game mode without the champion.

## Requirements

- Python 3.9+
- [discord.py](https://pypi.org/project/discord.py/) and [aiohttp](https://pypi.org/project/aiohttp/)
