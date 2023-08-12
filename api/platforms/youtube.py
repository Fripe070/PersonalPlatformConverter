import re

# noinspection PyFromFutureImport
from youtubesearchpython.__future__ import VideosSearch, Video, Playlist

from ..abc import AbstractAPI, UniversalTrack, AbstractPlaylistAPI, UniversalPlaylist
from ..errors import InvalidURLError


def get_best_thumbnail(thumbnails: list[dict]) -> dict:
    return max(
        thumbnails,
        key=lambda thumbnail: thumbnail.get("width", 0) * thumbnail.get("height", 0)
    )


def youtube_video_to_universal(video: dict) -> UniversalTrack:
    return UniversalTrack(
        title=video["title"],
        artist_names=[video["channel"]["name"]],
        url=video["link"],
        cover_url=get_best_thumbnail(video["thumbnails"])["url"],
    )


class YoutubeAPI(AbstractAPI, AbstractPlaylistAPI):
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

    def get_playlist_id(self, playlist_url: str) -> str:
        if matches := re.match(
            r"""
            ^(?:https?://)?         # optionaly matches "http://" or "https://"
            (?:(?:www|music)\.)?    # optionaly the subdomains "www." or "music."
            youtube\.com/               
            playlist\?list=
            ([a-zA-Z0-9_\-]+)       # matches the playlist id
            """,
            playlist_url,
            flags=re.ASCII | re.VERBOSE,
        ):
            return matches[1]
        else:
            raise InvalidURLError("Invalid Youtube playlist url")

    async def get_playlist_content(self, playlist_id: str) -> UniversalPlaylist | None:
        # Only accepts a url so we fake it
        # https://github.com/alexmercerind/youtube-search-python/blob/fc12c05747f1f7bd89d71699403762b86b523da5/youtubesearchpython/core/playlist.py#L88
        playlist: dict = await Playlist.get(f"list={playlist_id}")
        playlist_info = playlist["info"]

        return UniversalPlaylist(
            name=playlist_info["title"],
            # There actually is no description, but if there was then this is where it'd be at
            description=playlist_info.get("description"),
            owner_names=[channel_name] if (channel_name := playlist_info.get("channel", {}).get("name")) else None,
            url=playlist_info["link"],
            cover_url=get_best_thumbnail(playlist_info["thumbnails"])["url"],
            tracks=[
                youtube_video_to_universal(video)
                for video in playlist["videos"]
            ]
        )