import re

# noinspection PyFromFutureImport
from youtubesearchpython.__future__ import VideosSearch, Video

from data.modules.no_spotify.api.abc import AbstractAPI, UniversalTrack
from data.modules.no_spotify.api.errors import InvalidURLError


class YoutubeAPI(AbstractAPI):
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
            raise InvalidURLError("Invalid Youtube video url")

    async def is_valid_url(self, url: str, /) -> bool:
        try:
            self.extract_video_id(url)
        except InvalidURLError:
            return False
        else:
            return True

    async def url_to_query(self, video_url: str, /) -> str:
        video = await Video.getInfo(self.extract_video_id(video_url))
        return f"{video['title']} {video['channel']['name']}"

    async def search(self, query: str, /) -> list[UniversalTrack] | None:
        videos = filter(
            lambda vid: vid["type"] == "video",
            (await VideosSearch(query).next())["result"],
        )
        return [
            UniversalTrack(
                title=video["title"],
                artist_names=[video["channel"]["name"]],
                url=video["link"],
                cover_url=max(
                    video["thumbnails"],
                    key=lambda image: image.get("width", 0) * image.get("height", 0)
                )["url"]
            )
            for video in videos
        ]

