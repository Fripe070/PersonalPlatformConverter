import re
from datetime import timedelta, datetime

from ..abc import AbstractOAuthAPI, UniversalTrack, UniversalAlbum, AbstractPlaylistAPI, UniversalPlaylist
from ..errors import InvalidURLError


class SpotifyAPI(AbstractOAuthAPI, AbstractPlaylistAPI):
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
    def track_object_to_universal(track: dict) -> UniversalTrack:
        return UniversalTrack(
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


    def extract_track_id(self, track_url: str, /) -> str:
        if matches := re.match(r"https?://open\.spotify\.com/track/(\w+)", track_url, flags=re.ASCII):
            return matches[1]
        else:
            raise InvalidURLError("Invalid Spotify track url")

    async def url_to_query(self, track_url: str, /) -> str:
        async with self.session.get(
            f"{self.api_base}/tracks/{self.extract_track_id(track_url)}",
            headers={"Authorization": f"Bearer {self._token}"}
        ) as response:
            if response.status == 401:
                raise RuntimeError("Invalid spotify token")
            elif response.status != 200:
                raise RuntimeError("Could not get track data")
            track_data = await response.json()

        track_artists = [artist["name"] for artist in track_data["artists"]]
        return f"{track_data['name']} {' '.join(track_artists)}"

    async def search_tracks(self, query: str, /) -> list[UniversalTrack] | None:
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

        return [self.track_object_to_universal(track) for track in tracks]

    def extract_playlist_id(self, playlist_url: str, /) -> str:
        if matches := re.match(r"https?://open\.spotify\.com/playlist/(\w+)", playlist_url, flags=re.ASCII):
            return matches[1]
        else:
            raise InvalidURLError("Invalid Spotify track url")

    async def get_playlist_content(self, playlist_url: str, /) -> UniversalPlaylist | None:
        async with self.session.get(
            f"{self.api_base}/playlists/{self.extract_playlist_id(playlist_url)}",
            headers={"Authorization": f"Bearer {self._token}"}
        ) as response:
            if response.status == 401:
                raise RuntimeError("Invalid spotify token")
            elif response.status != 200:
                return None
            playlist = await response.json()

        return UniversalPlaylist(
            name=playlist["name"],
            description=playlist.get("description"),
            owner_names=[owner] if (owner := playlist["owner"].get("display_name")) else None,
            url=playlist["external_urls"]["spotify"],
            cover_url=playlist["images"][0]["url"],
            tracks=[
                self.track_object_to_universal(track["track"])
                for track in playlist["tracks"]["items"]
                if not track["is_local"] and track["track"].get("type") == "track"
            ]
        )




