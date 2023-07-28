import re

from .youtube import YoutubeAPI
from ..abc import UniversalTrack
from ..errors import InvalidURLError


class YoutubeMusicAPI(YoutubeAPI):
    def extract_track_id(self, video_url: str, /) -> str:
        if matches := re.match(
            r"^(?:https?://)?music\.youtube\.com/watch\?v=([a-zA-Z0-9_\-]+)",
            video_url,
            flags=re.ASCII,
        ):
            return matches[0]
        else:
            raise InvalidURLError("Invalid Youtube Music url")

    async def search_tracks(self, query: str, /) -> list[UniversalTrack] | None:
        tracks = await super().search_tracks(query)
        for track in tracks:
            track.url = re.sub(r"^https?://(www\.)?(youtu\.be|youtube.[a-z]+)", "^https://music.youtube.com", track.url)
        return tracks
