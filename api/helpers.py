import io

import aiohttp
import discord
from discord.ext import commands, tasks

import breadcord
from .abc import AbstractOAuthAPI, AbstractAPI, UniversalTrack
from .types import APIInterface

__all__ = [
    "PlatformConverter",
    "PlatformAPICog",
    "track_embed",
    "track_to_query",
    "url_to_file"
]

from .platforms import (
    SpotifyAPI,
    YoutubeAPI,
    YoutubeMusicAPI,
    BeatSaverAPI,
)


class PlatformConverter(commands.Converter):
    async def convert(self, ctx: commands.Context, argument: str) -> APIInterface | None:
        # This should only ever be used in this cog, and thus we know that ctx.cog will never be None
        # noinspection PyUnresolvedReferences
        return ctx.cog.api_interfaces.get(argument.strip())


class PlatformAPICog(breadcord.module.ModuleCog):
    def __init__(self, module_id: str):
        super().__init__(module_id)

        self.session: None | aiohttp.ClientSession = None
        # Lie to make the type checker happy
        # It will get sorted out in cog_load
        self.api_interfaces: dict[str, APIInterface] = {
            "spotify": SpotifyAPI,
            "youtube": YoutubeAPI,
            "youtube_music": YoutubeMusicAPI,
            "beatsaver": BeatSaverAPI,
        }

    async def cog_load(self) -> None:
        self.session = aiohttp.ClientSession()
        handled_api_interfaces: dict[str, APIInterface] = {}

        for platform_name in self.settings.active_platforms.value:
            api_interface: type[APIInterface] | None = self.api_interfaces.get(platform_name)
            if api_interface is None:
                self.logger.warning(f"Unknown platform {platform_name}")
                continue

            if issubclass(api_interface, AbstractOAuthAPI):
                platform_settings: breadcord.config.SettingsGroup = getattr(self.settings, platform_name)
                handled_api_interfaces[platform_name] = api_interface(
                    client_id=platform_settings.client_id.value,
                    client_secret=platform_settings.client_secret.value,
                    session=self.session
                )
            elif issubclass(api_interface, AbstractAPI):
                handled_api_interfaces[platform_name] = api_interface(session=self.session)

        self.api_interfaces = handled_api_interfaces
        self.refresh_access_tokens.start()

    async def cog_unload(self) -> None:
        await self.session.close()

    @tasks.loop(minutes=20)
    async def refresh_access_tokens(self):
        if self.session.closed:
            return
        for api in self.api_interfaces.values():
            if hasattr(api, "refresh_access_token"):
                self.logger.debug(f"Refreshing {api.__class__.__name__} access token")
                await api.refresh_access_token()
                self.logger.debug(f"Refreshed {api.__class__.__name__} access token")


def track_embed(
    track: UniversalTrack,
    *,
    random_colour: bool = False,
    colour: discord.Colour | None = None,
    cover_url: str | None = None,
) -> discord.Embed:
    description = f"**Artist{'s' if len(track.artist_names) > 1 else ''}:** {', '.join(track.artist_names)}"
    if track.album:
        description += f"\n**Album:** {track.album}"

    return discord.Embed(
        title=track.title.strip(),
        url=track.url,
        description=description,
        colour=discord.Colour.random(seed=track.url) if random_colour else colour
    ).set_thumbnail(url=cover_url or track.cover_url)


def track_to_query(track: UniversalTrack) -> str:
    return f"{track.title} {' '.join(track.artist_names)}"


async def url_to_file(url: str, *, session: aiohttp.ClientSession) -> io.BytesIO:
    async with session.get(url) as response:
        return io.BytesIO(await response.read())

