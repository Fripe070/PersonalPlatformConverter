from abc import abstractmethod, ABC
from datetime import datetime, timedelta

import aiohttp

from .errors import InvalidURLError


class UniversalAlbum:
    def __init__(
        self,
        *,
        title: str,
        artist_names: list[str],
        url: str,
        release_date: datetime | None = None,
        cover_url: str | None = None,
    ):
        self.title = title
        self.artist_names = artist_names
        self.url = url
        self.cover_url = cover_url
        self.release_date = release_date

    def __str__(self):
        return f"{self.title} by {', '.join(self.artist_names)}"

    def __repr__(self):
        return (
            f"<UniversalAlbum"
            f" title={self.title!r}"
            f" artist_names={self.artist_names!r}"
            f" url={self.url!r}"
            f" cover_url={self.cover_url!r}"
            f" release_date={self.release_date!r}"
            f">"
        )


class UniversalTrack:
    def __init__(
        self,
        *,
        title: str,
        artist_names: list[str],
        url: str,
        cover_url: str | None = None,
        album: UniversalAlbum | None = None,
    ):
        self.title = title
        self.artist_names = artist_names
        self.url = url
        self.album = album
        self.cover_url = cover_url

    def __str__(self):
        return f"{self.title} by {', '.join(self.artist_names)}"

    def __repr__(self):
        return (
            f"<UniversalTrack"
            f" title={self.title!r}"
            f" artists={self.artist_names!r}"
            f" url={self.url!r}"
            f" album={self.album!r}"
            f" cover_url={self.cover_url!r}"
            f">"
        )


class UniversalPlaylist:
    def __init__(
        self,
        *,
        name: str,
        description: str | None,
        owner_names: list[str] | None,
        url: str,
        tracks: list[UniversalTrack],
        cover_url: str | None = None,
    ):
        self.name = name
        self.description = description
        self.owner_names = owner_names
        self.url = url
        self.tracks = tracks
        self.cover_url = cover_url

    def __str__(self):
        return f"Playlist {self.name} by {', '.join(self.owner_names)}"

    def __repr__(self):
        return (
            f"<UniversalPlaylist"
            f" name={self.name!r}"
            f" owner_names={self.owner_names!r}"
            f" url={self.url!r}"
            f" tracks={self.tracks!r}"
            f" cover_url={self.cover_url!r}"
            f">"
        )


class AbstractAPI(ABC):
    def __init__(self, *, session: aiohttp.ClientSession):
        self.session = session

    def is_valid_track_url(self, track_url: str, /) -> bool:
        try:
            self.get_track_id(track_url)
        except InvalidURLError:
            return False
        else:
            return True

    @abstractmethod
    def get_track_id(self, track_url: str) -> str:
        raise NotImplementedError

    @abstractmethod
    async def track_from_id(self, track_id: str) -> UniversalTrack | None:
        raise NotImplementedError

    @abstractmethod
    async def search_tracks(self, query: str) -> list[UniversalTrack] | None:
        raise NotImplementedError


class AbstractOAuthAPI(AbstractAPI, ABC):
    def __init__(self, *, client_id: str, client_secret: str, session: aiohttp.ClientSession):
        super().__init__(session=session)
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: str | None = None
        self._token_expires_at: datetime | None = None

    @property
    def should_update_token(self) -> bool:
        leniency = timedelta(minutes=15)
        return self._token_expires_at is None or self._token_expires_at < datetime.now() + leniency

    @abstractmethod
    async def refresh_access_token(self):
        raise NotImplementedError


class AbstractPlaylistAPI(ABC):
    async def is_valid_playlist_url(self, playlist_url: str, /) -> bool:
        try:
            self.get_playlist_id(playlist_url)
        except InvalidURLError:
            return False
        else:
            return True

    @abstractmethod
    def get_playlist_id(self, playlist_url: str) -> str:
        raise NotImplementedError

    @abstractmethod
    async def get_playlist_content(self, playlist_id: str) -> UniversalPlaylist | None:
        raise NotImplementedError
