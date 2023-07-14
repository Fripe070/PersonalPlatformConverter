import re

from data.modules.no_spotify.api.abc import UniversalTrack
from data.modules.no_spotify.api.errors import InvalidURLError
from .youtube import YoutubeAPI


class YoutubeMusicAPI(YoutubeAPI):
    @staticmethod
    def extract_video_id(video_url: str, /) -> str:
        if matches := re.match(
            r"^(?:https?://)?music\.youtube\.com/watch\?v=([a-zA-Z0-9_\-]+)",
            video_url,
            flags=re.ASCII,
        ):
            return matches[0]
        else:
            raise InvalidURLError("Invalid Youtube Music url")

    async def search(self, query: str, /) -> list[UniversalTrack] | None:
        tracks = await super().search(query)
        for track in tracks:
            track.url = re.sub(r"^https?://(www\.)?(youtu\.be|youtube.[a-z]+)", "^https://music.youtube.com", track.url)
        return tracks
