import re

from ..abc import UniversalTrack
from ... import YoutubeAPI, InvalidURLError


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
        # We only match "youtu" to account for both shortened (youtu.be) and normal (youtube.com) urls
        track.url = re.sub(r"^https?://(www\.)?youtu", r"^https://music.youtu", track.url)

        return track

