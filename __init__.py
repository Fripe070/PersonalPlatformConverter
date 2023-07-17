import asyncio
import re

import discord
from discord import app_commands
from discord.ext import commands

import breadcord
from .api import helpers
from .api.abc import AbstractAPI, AbstractOAuthAPI
from .api.errors import InvalidURLError
from .api.types import APIInterface


class NoSpotify(helpers.PlatformAPICog):
    def __init__(self, module_id: str):
        super().__init__(module_id)

        self.ctx_menu = app_commands.ContextMenu(
            name='Convert music/video URLs',
            callback=self.url_convert_ctx_menu,
        )
        self.bot.tree.add_command(self.ctx_menu)

    # noinspection PyUnusedLocal
    async def platform_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> list[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=platform, value=platform)
            for platform in breadcord.helpers.search_for(
                current,
                tuple(self.api_interfaces.keys())
            )
        ]

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
            The platform to convert from
        to_platform: str
            The platform to convert to
        url: str
            The url to the track to convert
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

        tracks = await to_platform.search(query)
        await ctx.reply(tracks[0].url)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if urls := await self.convert_message_urls(message):
            await message.reply(urls, mention_author=False)

    async def url_convert_ctx_menu(self, interaction: discord.Interaction, message: discord.Message) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)
        await interaction.followup.send(await self.convert_message_urls(message) or "Nothing to convert")

    async def convert_message_urls(self, message: discord.Message) -> str | None:
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
                tracks = await preferred_platform_interface.search(query)
                return tracks[0].url

        converted_urls = tuple(filter(bool, await asyncio.gather(*map(convert_url, urls))))
        return " ".join(converted_urls) or None

    # noinspection PyIncorrectDocstring
    @commands.hybrid_command()
    @app_commands.autocomplete(platform=platform_autocomplete) # type: ignore
    async def search(self, ctx: commands.Context, platform: helpers.PlatformConverter, *, query: str):
        """Search for music/videos across several platforms

        Parameters
        -----------
        platform: APIInterface
            The platform to search on
        query: str
            Your search query
        """
        platform: APIInterface | None
        if platform is None:
            await ctx.reply("Invalid platform! Available platforms are: " + ", ".join(map(
                lambda x: f"`{x}`",
                self.api_interfaces
            )))
            return

        results = await platform.search(query)
        await ctx.reply(" \n".join(result.url for result in results[:5]))


async def setup(bot: breadcord.Bot):
    await bot.add_cog(NoSpotify("no_spotify"))
