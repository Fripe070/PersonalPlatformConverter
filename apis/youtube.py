import re

from youtubesearchpython.__future__ import VideosSearch, Video

from .abc import AbstractAPI, UniversalTrack
from .errors import InvalidURLError


class YoutubeAPI(AbstractAPI):
    platform_name = "spotify"
    api_base = "https://api.spotify.com/v1"

    @staticmethod
    def extract_video_id(video_url: str, /) -> str:
        if matches := re.match(
            r"""
            ^(?:https?://)?             # optionaly matches "http://" or "https://"
            (?:
                (?:(?:www|music)\.)?    # optionaly the subdomains "www." or "music."
                youtube\.com/watch\?v=  # matches "youtube.com/watch?v="
                |
                youtu\.be/              # matches "youtu.be/", but NOT with a subdomain
            )([a-zA-Z0-9_\-]+)          # matches the video id
            """,
            video_url,
            flags=re.ASCII | re.VERBOSE,
        ):
            return matches[0]
        else:
            raise InvalidURLError("Invalid youtube video url")

    async def url_to_query(self, video_url: str, /) -> str:
        video = await Video.getInfo(self.extract_video_id(video_url))
        return f"{video['title']} {video['channel']['name']}"

    async def search(self, query: str, /) -> UniversalTrack | None:
        video = next(filter(
            lambda vid: vid["type"] == "video",
            (await VideosSearch(query, limit=1).next())["result"],
        ))

        return UniversalTrack(
            title=video["title"],
            artist_names=[video["channel"]["name"]],
            url=video["link"],
            cover_url=max(
                video["thumbnails"],
                key=lambda image: image.get("width", 0) * image.get("height", 0)
            )["url"]
        )

