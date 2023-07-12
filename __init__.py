import asyncio
import re

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

import breadcord
from .abc import AbstractAPI, AbstractOAuthAPI
from .errors import InvalidURLError
from .platforms import *

APIInterfaces = AbstractAPI | AbstractOAuthAPI


class NoSpotify(breadcord.module.ModuleCog):
    def __init__(self, module_id: str, /):
        super().__init__(module_id)

        self.session: None | aiohttp.ClientSession = None
        self.api_interfaces: dict[str, APIInterfaces | type[APIInterfaces]] = {
            "spotify": SpotifyAPI,
            "youtube": YoutubeAPI,
            "youtube_music": YoutubeMusicAPI,
        }

        self.refresh_access_tokens.start()

    async def cog_load(self) -> None:
        self.session = aiohttp.ClientSession()
        handled_api_interfaces: dict[str, APIInterfaces] = {}

        for platform_name in self.settings.active_platforms.value:
            api_interface: type[APIInterfaces] | None = self.api_interfaces.get(platform_name)
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

    async def cog_unload(self) -> None:
        await self.session.close()

    @tasks.loop(minutes=20)
    async def refresh_access_tokens(self):
        for api in self.api_interfaces.values():
            if hasattr(api, "refresh_access_token"):
                self.logger.debug(f"Refreshing {api.__class__.__name__} access token")
                await api.refresh_access_token()
                self.logger.debug(f"Refreshed {api.__class__.__name__} access token")

    async def platform_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> list[app_commands.Choice[str]]:
        self.api_interfaces: dict[str, APIInterfaces]

        if not current:
            return [
                app_commands.Choice(name=platform_name, value=platform_name)
                for platform_name in self.api_interfaces
            ][:25]

        return [
            app_commands.Choice(name=platform_name, value=platform_name)
            for platform_name in breadcord.helpers.search_for(
                query=current,
                objects=list(self.api_interfaces.keys()),
            )
        ][:25]

    # noinspection PyIncorrectDocstring
    @commands.hybrid_command()
    @app_commands.autocomplete(
        from_platform=platform_autocomplete, # type: ignore
        to_platform=platform_autocomplete, # type: ignore
    )
    async def track_convert(self, ctx: commands.Context, from_platform: str, to_platform: str, url: str):
        """Converts music from one platform to another

        Parameters
        -----------
        from_platform: str
            the platform to convert from
        to_platform: str
            the platform to convert to
        url: str
            the url to the track to convert
        """

        if url.startswith("<") and url.endswith(">"):
            url = url[1:-1]

        from_platform = self.api_interfaces.get(from_platform.lower())
        to_platform = self.api_interfaces.get(to_platform.lower())

        try:
            query = await from_platform.url_to_query(url)
        except InvalidURLError:
            await ctx.reply("Invalid url")
            return

        track = await to_platform.search(query)
        await ctx.reply(track.url)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        disliked_platforms: list[str] = self.settings.disliked_platforms.value
        preferred_platform_interface = self.api_interfaces.get(self.settings.preferred_platform.value)
        if preferred_platform_interface is None:
            raise ValueError("No valid preferred platform is set")

        # Partially to make the bot not respond to itself
        # and because bots talking to each other is gets annoying
        if message.author.bot or not disliked_platforms:
            return

        urls = re.findall("<?(?:https:|http:)\S+>?", message.content)
        urls = tuple(filter(
            lambda found_url: not found_url.startswith("<") and not found_url.endswith(">"),
            urls
        ))
        if not urls:
            return

        async def convert_url(url: str) -> str:
            for platform_name, api_interface in self.api_interfaces.items():
                if not await api_interface.is_valid_url(url):
                    continue
                elif platform_name not in disliked_platforms:
                    break
                query = await api_interface.url_to_query(url)
                track = await preferred_platform_interface.search(query)
                return track.url

        converted_urls = tuple(filter(bool, await asyncio.gather(*map(convert_url, urls))))
        if converted_urls:
            await message.reply(" ".join(converted_urls))

async def setup(bot: breadcord.Bot):
    await bot.add_cog(NoSpotify("no_spotify"))
