import re

# noinspection PyFromFutureImport
from youtubesearchpython.__future__ import VideosSearch, Video

from ..abc import AbstractAPI, UniversalTrack
from ..errors import InvalidURLError


def youtube_video_to_universal(video: dict) -> UniversalTrack:
    return UniversalTrack(
        title=video["title"],
        artist_names=[video["channel"]["name"]],
        url=video["link"],
        cover_url=max(
            video["thumbnails"],
            key=lambda image: image.get("width", 0) * image.get("height", 0)
        )["url"]
    )


class YoutubeAPI(AbstractAPI):
    def get_track_id(self, track_url: str) -> str:
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
            track_url,
            flags=re.ASCII | re.VERBOSE,
        ):
            return matches[0]
        else:
            raise InvalidURLError("Invalid Youtube video url")

    async def track_from_id(self, track_id: str) -> UniversalTrack | None:
        video = await Video.getInfo(track_id)
        return youtube_video_to_universal(video)

    async def search_tracks(self, query: str) -> list[UniversalTrack] | None:
        videos = filter(
            lambda vid: vid["type"] == "video",
            (await VideosSearch(query).next())["result"],
        )
        return [youtube_video_to_universal(video) for video in videos]

