import re

from .youtube import YoutubeAPI
from ..abc import UniversalTrack
from ..errors import InvalidURLError


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

    async def search(self, query: str, /) -> UniversalTrack | None:
        track = await super().search(query)
        track.url = re.sub(r"^https?://(www\.)?(youtu\.be|youtube.[a-z]+)", r"^https://music.youtube.com", track.url)
        return track
