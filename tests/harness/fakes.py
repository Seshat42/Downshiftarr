from __future__ import annotations

from types import SimpleNamespace
from typing import Any


def attr(**kwargs: Any) -> SimpleNamespace:
    return SimpleNamespace(**kwargs)


def media(media_id: str, height: int | None, dynamic_range: str = "SDR", selected: bool = False) -> SimpleNamespace:
    stream = attr(streamType=1, height=height, colorSpace=dynamic_range)
    return attr(
        id=media_id,
        height=height,
        videoHeight=height,
        videoDynamicRange=dynamic_range,
        selected=selected,
        parts=[attr(streams=[stream])],
    )


class FakeClient:
    def __init__(self, machine_identifier: str, fail_play: bool = False, fail_seek_attempts: int = 0):
        self.machineIdentifier = machine_identifier
        self.clientIdentifier = machine_identifier
        self.title = f"client:{machine_identifier}"
        self.fail_play = fail_play
        self.fail_seek_attempts = fail_seek_attempts
        self.play_calls: list[dict[str, Any]] = []
        self.seek_calls: list[int] = []

    def playMedia(self, item: Any, offset: int, mediaIndex: int, partIndex: int) -> None:
        if self.fail_play:
            raise RuntimeError("play failed")
        self.play_calls.append({"item": item, "offset": offset, "mediaIndex": mediaIndex, "partIndex": partIndex})

    def seekTo(self, offset: int) -> None:
        self.seek_calls.append(offset)
        if len(self.seek_calls) <= self.fail_seek_attempts:
            raise RuntimeError("seek failed")


class FakePlexServer:
    def __init__(self, sessions: list[Any] | None = None, clients: list[Any] | None = None, named_clients: dict[str, Any] | None = None):
        self._sessions = sessions or []
        self._clients = clients or []
        self._named_clients = named_clients or {}
        self.fetch_calls: list[Any] = []

    def sessions(self) -> list[Any]:
        return list(self._sessions)

    def clients(self) -> list[Any]:
        return list(self._clients)

    def client(self, title: str) -> Any:
        if title not in self._named_clients:
            raise KeyError(title)
        return self._named_clients[title]

    def fetchItem(self, key: Any) -> Any:
        self.fetch_calls.append(key)
        rating_key = str(key).removeprefix("/library/metadata/")
        for item in self._sessions:
            if str(getattr(item, "ratingKey", "")) == rating_key:
                return item
        raise KeyError(key)
