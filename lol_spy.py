"""Discord bot that announces when your friends start a League of Legends game."""

import asyncio
import json
import sys
import time
from collections import deque
from pathlib import Path

import aiohttp
import discord
from discord.ext import tasks

CONFIG_PATH = Path(__file__).with_name("config.json")

REQUIRED_KEYS = ("DISCORD_TOKEN", "RIOT_API_KEY", "CHANNEL_ID", "FRIENDS_LIST")

DEFAULTS = {
    # Platform routing for spectator data, and regional routing for account lookups.
    # See https://developer.riotgames.com/docs/lol#routing-values
    "PLATFORM": "la2",
    "REGION": "americas",
    "POLL_SECONDS": 60,
    "REQUESTS_PER_MINUTE": 100,
    "ANNOUNCE_WHEN_IDLE": False,
}

# Riot's champion list changes only on patch day.
CHAMPIONS_TTL_SECONDS = 12 * 60 * 60


def load_config(path=CONFIG_PATH):
    """Return the bot configuration, with defaults filled in for anything absent.

    Raises SystemExit if the file is missing, malformed, or lacks a required key.
    """
    if not path.exists():
        raise SystemExit(
            f"No {path.name} found. Copy config.example.json to {path.name} and fill it in."
        )

    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SystemExit(f"{path.name} is not valid JSON: {error}")

    missing = [key for key in REQUIRED_KEYS if not config.get(key)]
    if missing:
        raise SystemExit(f"{path.name} is missing: {', '.join(missing)}")

    if not isinstance(config["FRIENDS_LIST"], list) or not config["FRIENDS_LIST"]:
        raise SystemExit("FRIENDS_LIST must hold at least one {gameName, tagLine} entry")

    for friend in config["FRIENDS_LIST"]:
        if not friend.get("gameName") or not friend.get("tagLine"):
            raise SystemExit(f"Each friend needs a gameName and a tagLine: {friend!r}")

    return {**DEFAULTS, **config}


class RateLimiter:
    """Caps how many requests are started within any rolling sixty seconds."""

    def __init__(self, per_minute, now=time.monotonic):
        self._per_minute = per_minute
        self._now = now
        self._started = deque()
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Return once starting another request stays within the limit.

        Waits only as long as the oldest request in the window has left to age out.
        """
        async with self._lock:
            while True:
                now = self._now()
                while self._started and now - self._started[0] >= 60:
                    self._started.popleft()

                if len(self._started) < self._per_minute:
                    self._started.append(now)
                    return

                await asyncio.sleep(60 - (now - self._started[0]))


class RiotClient:
    """Reads account and live-game data from Riot's API within a request budget."""

    def __init__(self, session, api_key, platform, region, limiter):
        self._session = session
        self._platform = platform
        self._region = region
        self._limiter = limiter
        self._headers = {"X-Riot-Token": api_key}
        self._champions = {}
        self._champions_fetched_at = None

    async def _get(self, url, headers=None, ok_missing=False):
        """Return the JSON body at `url`, or None when the request does not succeed.

        A 404 with `ok_missing` set is treated as an ordinary absence rather than an
        error, which is how Riot reports a summoner who is not currently in a game.
        """
        await self._limiter.acquire()
        try:
            async with self._session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                if response.status == 404 and ok_missing:
                    return None
                if response.status == 429:
                    retry_after = int(response.headers.get("Retry-After", 10))
                    print(f"[!] Rate limited by Riot, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                    return None
                print(f"[!] HTTP {response.status} from {url.split('?')[0]}")
                return None
        except aiohttp.ClientError as error:
            print(f"[!] Request failed: {error}")
            return None

    async def puuid(self, game_name, tag_line):
        """Return the PUUID for a Riot ID, or None if it could not be resolved."""
        url = (
            f"https://{self._region}.api.riotgames.com/riot/account/v1/accounts/"
            f"by-riot-id/{game_name}/{tag_line}"
        )
        data = await self._get(url, headers=self._headers)
        return data.get("puuid") if data else None

    async def active_game(self, puuid):
        """Return the live game a PUUID is in, or None when they are not in one."""
        url = (
            f"https://{self._platform}.api.riotgames.com/lol/spectator/v5/active-games/"
            f"by-summoner/{puuid}"
        )
        return await self._get(url, headers=self._headers, ok_missing=True)

    async def champion_names(self):
        """Return champion key to name, refetched at most once every twelve hours.

        Returns the previously cached mapping if a refresh fails, so a Data Dragon
        outage costs nothing.
        """
        fresh = (
            self._champions_fetched_at is not None
            and time.monotonic() - self._champions_fetched_at < CHAMPIONS_TTL_SECONDS
        )
        if fresh:
            return self._champions

        versions = await self._get("https://ddragon.leagueoflegends.com/api/versions.json")
        if not versions:
            return self._champions

        data = await self._get(
            f"https://ddragon.leagueoflegends.com/cdn/{versions[0]}/data/en_US/champion.json"
        )
        if not data:
            return self._champions

        self._champions = {
            champion["key"]: champion["name"] for champion in data["data"].values()
        }
        self._champions_fetched_at = time.monotonic()
        print(f"[+] Loaded {len(self._champions)} champions from patch {versions[0]}")
        return self._champions


class Watcher:
    """Decides what is worth announcing as friends start and finish games."""

    def __init__(self, announce_when_idle=False):
        self._announce_when_idle = announce_when_idle
        self._announced = {}
        self._anyone_playing = False

    def update(self, games_by_friend):
        """Return which friends just started a game, and whether everyone just stopped.

        `games_by_friend` maps a friend's name to the game they are in, or to None.
        A friend keeps their place until their game ends, so one game is announced
        once; when it ends they are forgotten, so their next game announces again.

        Returns a (started, went_idle) pair, where `started` holds (friend, game)
        pairs and `went_idle` is only ever true on the transition into nobody playing.
        """
        started = []

        for friend, game in games_by_friend.items():
            if game is None:
                self._announced.pop(friend, None)
                continue
            if self._announced.get(friend) != game["gameId"]:
                self._announced[friend] = game["gameId"]
                started.append((friend, game))

        playing = bool(self._announced)
        went_idle = self._announce_when_idle and self._anyone_playing and not playing
        self._anyone_playing = playing

        return started, went_idle


def describe(friend, game, puuid, champions):
    """Return the announcement text for a friend's live game."""
    participant = next((p for p in game["participants"] if p.get("puuid") == puuid), None)
    champion = champions.get(str(participant["championId"])) if participant else None

    if champion:
        return f"**{friend}** is playing **{champion}** in **{game['gameMode']}**"
    return f"**{friend}** is in a **{game['gameMode']}** game"


def build_client(config):
    """Return the Discord client, wired to poll Riot on the configured interval."""
    # No privileged intents: the bot reads game state from Riot, not from Discord.
    client = discord.Client(intents=discord.Intents.default())

    channel_id = int(config["CHANNEL_ID"])
    friends = config["FRIENDS_LIST"]
    watcher = Watcher(config["ANNOUNCE_WHEN_IDLE"])
    state = {}

    async def send(**embed_fields):
        channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
        await channel.send(embed=discord.Embed(**embed_fields))

    @tasks.loop(seconds=config["POLL_SECONDS"])
    async def poll():
        riot = state["riot"]

        # Friends whose PUUID has not been resolved yet are retried each round, so a
        # transient failure at startup does not drop them for the bot's lifetime.
        for friend in friends:
            name = friend["gameName"]
            if name not in state["puuids"]:
                found = await riot.puuid(name, friend["tagLine"])
                if found:
                    state["puuids"][name] = found
                    print(f"[+] Resolved {name}#{friend['tagLine']}")

        champions = await riot.champion_names()

        games = {}
        for name, puuid in state["puuids"].items():
            games[name] = await riot.active_game(puuid)

        started, went_idle = watcher.update(games)

        for name, game in started:
            await send(
                title="A friend is in a game",
                description=describe(name, game, state["puuids"][name], champions),
                color=discord.Color.green(),
            )

        if went_idle:
            await send(
                title="All quiet",
                description="Nobody is in a game right now.",
                color=discord.Color.greyple(),
            )

    @poll.before_loop
    async def before_poll():
        await client.wait_until_ready()

    @client.event
    async def on_ready():
        print(f"[+] Connected as {client.user}")
        session = aiohttp.ClientSession()
        state["session"] = session
        state["puuids"] = {}
        state["riot"] = RiotClient(
            session,
            config["RIOT_API_KEY"],
            config["PLATFORM"],
            config["REGION"],
            RateLimiter(config["REQUESTS_PER_MINUTE"]),
        )
        if not poll.is_running():
            poll.start()

    return client


def main():
    """Run the bot until it is stopped."""
    config = load_config()
    build_client(config).run(config["DISCORD_TOKEN"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
