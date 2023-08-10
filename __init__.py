import asyncio
import io
import re
import sqlite3

import discord
from discord import app_commands
from discord.ext import commands

import breadcord
from .api import helpers
from .api.abc import AbstractAPI, AbstractOAuthAPI, UniversalTrack, AbstractPlaylistAPI
from .api.errors import InvalidURLError
from .api.helpers import track_embed
from .api.platforms import SpotifyAPI
from .api.types import APIInterface


class PlatformConverter(helpers.PlatformAPICog):
    def __init__(self, module_id: str):
        super().__init__(module_id)

        self.logger.debug("Creating database")
        self.db_connection = sqlite3.connect(self.module.storage_path / "platform_converter.db")
        self.db_cursor = self.db_connection.cursor()
        self.db_cursor.execute(
            "CREATE TABLE IF NOT EXISTS community_playlist ("
            "    track_url TEXT UNIQUE,"
            "    addition_author_id INTEGER,"
            "    rejected INT,"
            "    PRIMARY KEY (track_url)"
            ")"
        )
        self.db_connection.commit()
        self.logger.debug("Database created")

        self.ctx_menu = app_commands.ContextMenu(
            name="Convert music/video URLs",
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
        if not all((from_platform, to_platform)):
            await ctx.reply("Unknown platform")
            return

        try:
            query = await from_platform.url_to_query(url)
        except InvalidURLError:
            await ctx.reply("Invalid url")
            return

        tracks = await to_platform.search_tracks(query)
        if not tracks:
            await ctx.reply("No results found")
            return
        await ctx.reply(tracks[0].url)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not self.settings.disliked_platforms.value:
            return
        if urls := await self.convert_message_urls(message):
            await message.reply(urls, mention_author=False)

    async def url_convert_ctx_menu(self, interaction: discord.Interaction, message: discord.Message) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)
        await interaction.followup.send(await self.convert_message_urls(message) or "Nothing to convert")

    async def convert_message_urls(self, message: discord.Message) -> str | None:
        preferred_platform_interface = self.api_interfaces.get(self.settings.preferred_platform.value)
        if preferred_platform_interface is None:
            raise ValueError("No valid preferred platform is set")

        urls = re.findall("<?(?:https:|http:)\S+>?", message.content)
        urls = tuple(filter(
            lambda found_url: not found_url.startswith("<") and not found_url.endswith(">"),
            urls
        ))
        if not urls:
            return

        async def convert_url(url: str) -> str:
            for platform_name, api_interface in self.api_interfaces.items():
                if api_interface == preferred_platform_interface or not await api_interface.is_valid_track_url(url):
                    continue
                query = await api_interface.url_to_query(url)
                tracks = await preferred_platform_interface.search(query)
                return tracks[0].url

        converted_urls = tuple(filter(bool, await asyncio.gather(*map(convert_url, urls))))
        return " ".join(converted_urls) or None

    # noinspection PyIncorrectDocstring
    @commands.hybrid_command()
    @app_commands.autocomplete(platform=platform_autocomplete) # type: ignore
    async def search(
        self,
        ctx: commands.Context,
        platform: helpers.PlatformConverter,
        *,
        query: str,
        count: int = 1,
        compact_embeds: bool = False
    ):
        """Search for music/videos across several platforms¤

        Parameters
        -----------
        platform: APIInterface
            The platform to search on
        query: str
            Your search query
        count: int
            The maximum amount of urls to return
        """
        platform: APIInterface | None
        if platform is None:
            await ctx.reply("Invalid platform! Available platforms are: " + ", ".join(map(
                lambda x: f"`{x}`",
                self.api_interfaces
            )))
            return

        results = await platform.search_tracks(query)
        if compact_embeds:
            await ctx.reply(embeds=[
                track_embed(result, random_colour=True)
                for result in results[:min(10, max(1, count))]  # Limited to 10 due to embed limits
            ])
        else:
            await ctx.reply(" ".join(result.url for result in results[:max(1, count)]))

    # noinspection PyUnusedLocal
    async def playlist_platform_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> list[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=platform, value=platform)
            for platform in breadcord.helpers.search_for(
                current,
                [
                    platform
                    for platform, api_interface in self.api_interfaces.items()
                    if isinstance(api_interface, AbstractPlaylistAPI)
                ]
            )
        ]

    @commands.hybrid_command()
    @app_commands.autocomplete(platform=playlist_platform_autocomplete) # type: ignore
    async def playlist(
        self,
        ctx: commands.Context,
        platform: helpers.PlatformConverter,
        playlist_url: str,
        max_tracks: int = 15
    ):
        platform: APIInterface | None
        if not isinstance(platform, AbstractPlaylistAPI):
            await ctx.reply("Invalid platform! Available platforms with playlist support are: " + ", ".join([
                f"`{platform}`"
                for platform in self.api_interfaces
                if isinstance(self.api_interfaces[platform], AbstractPlaylistAPI)
            ]))
            return

        playlist = await platform.get_playlist_content(playlist_url)
        if playlist is None:
            await ctx.reply("Could not find that playlist. Ensure that it exists and is public.")
            return

        async with self.session.get(playlist.cover_url) as response:
            cover = discord.File(
                io.BytesIO(await response.read()),
                filename="cover.png"
            )

        description = (discord.utils.escape_markdown(playlist.description.strip()) or "") + "\n\n**Tracks**"
        for i, track in enumerate(playlist.tracks):
            title = discord.utils.escape_markdown(track.title)
            artists = ", ".join(map(discord.utils.escape_markdown, track.artist_names))

            fallback_text = f"\n\nAnd {len(playlist.tracks) - i} more..." if i != len(playlist.tracks) - 1 else ""
            addition = f"[{title}]({track.url}) - {artists}"
            if len(description) + len(addition) + len(fallback_text) >= 4096 or i >= max_tracks:
                description += fallback_text
                break
            description += f"\n{addition}"

        await ctx.reply(
            embed=discord.Embed(
                title=playlist.name,
                description=description,
                url=playlist.url,
                colour=discord.Colour.random(seed=playlist.url),
            ).set_thumbnail(
                url="attachment://cover.png"
            ).set_footer(
                text=f"By {', '.join(playlist.owner_names)}" if playlist.owner_names else None,
            ),
            file=cover
        )

    @commands.hybrid_command(aliases=["pl_add", "pladd"])
    async def add_to_playlist(self, ctx: commands.Context, track_url_to_add: str):
        community_playlist_channel = self.bot.get_channel(int(self.settings.community_playlist_channel_id.value))
        if not community_playlist_channel or ctx.guild != community_playlist_channel.guild:
            await ctx.reply("This command is usable here.")
            return

        async def get_standardised_track(url: str) -> UniversalTrack | None:
            preferred_platform_interface = self.api_interfaces[self.settings.preferred_platform.value]
            for api_interface in self.api_interfaces.values():
                if not await api_interface.is_valid_track_url(url):
                    continue
                query = await api_interface.url_to_query(url)
                tracks = await preferred_platform_interface.search_tracks(query)
                return tracks[0]
            return None

        track = await get_standardised_track(track_url_to_add)
        del track_url_to_add

        if track is None:
            await ctx.reply("Invalid track URL.")
            return

        result = self.db_cursor.execute(
            # langauge=SQLite
            "SELECT track_url, rejected FROM community_playlist WHERE track_url = ?",
            (track.url,)
        ).fetchone()
        if result is not None:
            if result[1]:
                await ctx.reply("That track has already been rejected.")
                return
            await ctx.reply("That track is already in the community playlist.")
            return

        self.db_cursor.execute(
            # language=SQLite
            (
                "INSERT INTO community_playlist (track_url, addition_author_id, rejected)"
                "VALUES (?, ?, ?)"
            ),
            (
                track.url,
                ctx.author.id,
                0 # false
            )
        )
        self.db_connection.commit()

        await ctx.reply("Added to the community playlist!")
        msg = await community_playlist_channel.send(
            "New track added to the community playlist!",
            embed=discord.Embed(
                title=track.title.strip(),
                url=track.url,
                description=f"**Artist{'s' if len(track.artist_names) > 1 else ''}:** {', '.join(track.artist_names)}",
                colour=discord.Colour.green()
            ).set_thumbnail(
                url=track.cover_url
            ).set_footer(
                text=f"Added by {ctx.author.display_name}",
            )
        )
        await msg.add_reaction("\N{WHITE HEAVY CHECK MARK}")
        await msg.add_reaction("\N{NEGATIVE SQUARED CROSS MARK}")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        await self.handle_reactions(payload, True)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        await self.handle_reactions(payload, False)

    async def handle_reactions(self, payload: discord.RawReactionActionEvent, add: bool):
        if payload.channel_id != int(self.settings.community_playlist_channel_id.value):
            return
        if not (channel := self.bot.get_channel(payload.channel_id)):
            return
        if not (message := await channel.fetch_message(payload.message_id)):
            return
        if payload.emoji.name not in ["\N{WHITE HEAVY CHECK MARK}", "\N{NEGATIVE SQUARED CROSS MARK}"]:
            return

        score = 0
        for reaction in message.reactions:
            if reaction.emoji == "\N{WHITE HEAVY CHECK MARK}":
                score += reaction.count
            elif reaction.emoji == "\N{NEGATIVE SQUARED CROSS MARK}":
                score -= reaction.count
            else:
                print(reaction.emoji)

        message_embed = message.embeds[0]
        def reconstruct_embed_with_colour(colour: discord.Colour) -> discord.Embed:
            return discord.Embed(
                title=message_embed.title,
                url=message_embed.url,
                description=message_embed.description,
                colour=colour
            ).set_thumbnail(
                url=message_embed.thumbnail.url
            ).set_footer(
                text=message_embed.footer.text,
                icon_url=message_embed.footer.icon_url
            )

        gets_denied_at_score = -1

        if message_embed.colour != discord.Colour.red() and score <= gets_denied_at_score:
            self.db_cursor.execute(
                # language=SQLite
                "UPDATE community_playlist SET rejected = 1 WHERE track_url = ?",
                (message.embeds[0].url,)
            )
            self.db_connection.commit()
            await message.edit(
                content="This track has been rejected.",
                embed=reconstruct_embed_with_colour(discord.Colour.red())
            )
            return
        elif message_embed.colour == discord.Colour.red() and score > gets_denied_at_score:
            self.db_cursor.execute(
                # language=SQLite
                "UPDATE community_playlist SET rejected = 0 WHERE track_url = ?",
                (message.embeds[0].url,)
            )
            self.db_connection.commit()
            await message.edit(
                content="This track has been re-accepted.",
                embed=reconstruct_embed_with_colour(discord.Colour.green())
            )
            return


    async def cog_command_error(self, ctx: commands.Context, error: Exception) -> None:
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply(str(error), ephemeral=True)
            return
        raise


async def setup(bot: breadcord.Bot):
    await bot.add_cog(PlatformConverter("platform_converter_fripe_fork"))
