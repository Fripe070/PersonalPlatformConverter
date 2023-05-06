import asyncio
import re

import aiohttp
import discord
from discord import app_commands
# noinspection PyFromFutureImport
from youtubesearchpython.__future__ import VideosSearch

import breadcord


def extract_ids_from_url(url: str, /) -> list[str]:
    return re.findall(
        r"https://open\.spotify\.com/track/(\w+)",
        url,
        flags=re.ASCII
    )


class NoSpotify(breadcord.module.ModuleCog):
    def __init__(self, module_id: str, /):
        super().__init__(module_id)

        self.api_base = "https://api.spotify.com/v1"
        self.session: None | aiohttp.ClientSession = None

        self.bot.loop.create_task(self.refresh_api_key())


    async def cog_load(self) -> None:
        self.session = aiohttp.ClientSession()

    async def cog_unload(self) -> None:
        await self.session.close()

    async def refresh_api_key(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            async with self.session.post(
                "https://accounts.spotify.com/api/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.settings.client_id.value,
                    "client_secret": self.settings.client_secret.value
                }
            ) as response:
                data = await response.json()
                self.settings.api_key.value = data["access_token"]

                self.logger.debug(f"Fetched new spotify token expiring in {data['expires_in']}s.")
                await asyncio.sleep(data["expires_in"])

    async def get_spotify_track(self, track_id: str, /) -> dict:
        async with self.session.get(
            f"{self.api_base}/tracks/{track_id}",
            headers={"Authorization": f"Bearer {self.settings.api_key.value}"}
        ) as response:
            if response.status == 401:
                raise ValueError("Invalid spotify token")
            return await response.json()

    async def spotify_to_youtube(self, url: str, /) -> str:
        track_data = await self.get_spotify_track(url)
        track_artists = [artist["name"] for artist in track_data["artists"]]
        track_name = track_data["name"]

        video = (await VideosSearch(f"{track_name} {' '.join(track_artists)}", limit=1).next())["result"][0]
        return video["link"]

    @app_commands.command(description="Get youtube video from a spotify track url")
    async def spotify_to_yt(self, interaction: discord.Interaction, url: str) -> None:
        urls = extract_ids_from_url(url)
        if not urls:
            await interaction.response.send_message("Could not find track ID in the specified URL.", ephemeral=True)
        await interaction.response.send_message(await self.spotify_to_youtube(urls[0]), ephemeral=True)

    @breadcord.module.ModuleCog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not self.settings.search_messages.value:
            return
        if urls := [await self.spotify_to_youtube(track_id) for track_id in extract_ids_from_url(message.content)]:
            await message.reply(" ".join(urls), mention_author=False)


async def setup(bot: breadcord.Bot):
    await bot.add_cog(NoSpotify("no_spotify"))
