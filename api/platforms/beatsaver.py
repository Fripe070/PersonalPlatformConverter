import re
import urllib.parse

from ..abc import AbstractAPI, UniversalTrack
from ..errors import InvalidURLError


class BeatSaverAPI(AbstractAPI):
    api_base = "https://api.beatsaver.com"
    @staticmethod
    def extract_map_id(video_url: str, /) -> str:
        if matches := re.match(r"^(?:https?://)?beatsaver.com/maps([a-z0-9]+)", video_url):
            return matches[0]
        else:
            raise InvalidURLError("Invalid beatsaver map url")

    async def is_valid_url(self, url: str, /) -> bool:
        try:
            self.extract_map_id(url)
        except InvalidURLError:
            return False
        else:
            return True

    async def url_to_query(self, map_url: str, /) -> str:
        async with self.session.get(f"{self.api_base}/maps/id/{self.extract_map_id(map_url)}") as response:
            map_metadata = (await response.json())["metadata"]

        return f"{map_metadata['songName']} {map_metadata['songAuthorName']}"

    async def search(self, query: str, /) -> list[UniversalTrack] | None:
        async with self.session.get(
            f"{self.api_base}/search/text/0?sortOrder=Rating&q={urllib.parse.quote(query)}",
        ) as response:
            maps = (await response.json())["docs"]

        return [
            UniversalTrack(
                title=custom_map["metadata"]["songName"],
                artist_names=[custom_map["metadata"]["songAuthorName"]],
                url=f"https://beatsaver.com/maps/{custom_map['id']}",
                cover_url=custom_map["versions"][0]["coverURL"],
            )
            for custom_map in maps
        ]

