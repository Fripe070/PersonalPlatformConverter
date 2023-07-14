import re
from datetime import timedelta, datetime

from data.modules.no_spotify.api.abc import AbstractOAuthAPI, UniversalTrack, UniversalAlbum
from data.modules.no_spotify.api.errors import InvalidURLError


class SpotifyAPI(AbstractOAuthAPI):
    api_base = "https://api.spotify.com/v1"

    async def refresh_access_token(self):
        if not self.should_update_token:
            return
        async with self.session.post(
            "https://accounts.spotify.com/api/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret
            }
        ) as response:
            data = await response.json()
            if data.get("error") == "invalid_client":
                raise ValueError("Invalid spotify client id or secret")
            self._token = data["access_token"]
            self._token_expires_at = datetime.now() + timedelta(seconds=data["expires_in"])

    @staticmethod
    def extract_track_id(track_url: str, /) -> str:
        if matches := re.match(r"https?://open\.spotify\.com/track/(\w+)", track_url, flags=re.ASCII):
            return matches[1]
        else:
            raise InvalidURLError("Invalid Spotify track url")

    async def is_valid_url(self, url: str, /) -> bool:
        try:
            self.extract_track_id(url)
        except InvalidURLError:
            return False
        else:
            return True

    async def url_to_query(self, track_url: str, /) -> str | None:
        async with self.session.get(
            f"{self.api_base}/tracks/{self.extract_track_id(track_url)}",
            headers={"Authorization": f"Bearer {self._token}"}
        ) as response:
            if response.status == 401:
                raise RuntimeError("Invalid spotify token")
            elif response.status != 200:
                print(response.status, response.content)
                return None
            track_data = await response.json()

        track_artists = [artist["name"] for artist in track_data["artists"]]
        return f"{track_data['name']} {' '.join(track_artists)}"

    async def search(self, query: str, /) -> list[UniversalTrack] | None:
        async with self.session.get(
            f"{self.api_base}/search",
            headers={"Authorization": f"Bearer {self._token}"},
            params={"q": query, "type": "track"}
        ) as response:
            if response.status == 401:
                raise RuntimeError("Invalid spotify token")
            elif response.status != 200:
                return None
            tracks = (await response.json())["tracks"]["items"]

        return [
            UniversalTrack(
                title=track["name"],
                artist_names=[artist["name"] for artist in track["artists"]],
                album=UniversalAlbum(
                    title=album["name"],
                    artist_names=[artist["name"] for artist in album["artists"]],
                    url=album["external_urls"].get("spotify"),
                    cover_url=max(
                        album["images"],
                        key=lambda image: image.get("width", 0) * image.get("height", 0)
                    )["url"],
                    release_date=album["release_date"],
                ) if (album := track.get("album", {})).get("album_type") == "album" else None,
                url=track["external_urls"].get("spotify"),
                cover_url=max(
                    track["album"]["images"],
                    key=lambda image: image.get("width", 0) * image.get("height", 0)
                )["url"]
            )
            for track in tracks
        ]

