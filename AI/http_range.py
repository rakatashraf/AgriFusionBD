"""Seekable file-like object over HTTP range requests.

Lets h5py / rasterio-style readers pull only the bytes they need from a large
remote granule. Used for SMAP L3 HDF5, which is ~650 MB per day - far too much
to download in full for a handful of points.
"""

from __future__ import annotations

import io
import threading


class HTTPRangeFile(io.RawIOBase):
    """Minimal read-only random-access file backed by HTTP Range requests."""

    def __init__(self, session, url: str, block_size: int = 1 << 20):
        self._session = session
        self._url = url
        self._block = block_size
        self._pos = 0
        self._lock = threading.Lock()
        self._cache: dict[int, bytes] = {}
        self._cache_order: list[int] = []

        r = session.get(url, headers={"Range": "bytes=0-0"}, timeout=120)
        r.raise_for_status()
        content_range = r.headers.get("Content-Range")
        if content_range and "/" in content_range:
            self._size = int(content_range.rsplit("/", 1)[1])
        elif r.headers.get("Content-Length"):
            self._size = int(r.headers["Content-Length"])
        else:
            raise ValueError(f"cannot determine size of {url}")

    # -- io plumbing -------------------------------------------------
    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if whence == io.SEEK_SET:
            self._pos = offset
        elif whence == io.SEEK_CUR:
            self._pos += offset
        elif whence == io.SEEK_END:
            self._pos = self._size + offset
        else:
            raise ValueError(f"bad whence {whence}")
        return self._pos

    def tell(self) -> int:
        return self._pos

    @property
    def size(self) -> int:
        return self._size

    # -- data --------------------------------------------------------
    def _fetch_block(self, index: int) -> bytes:
        with self._lock:
            cached = self._cache.get(index)
            if cached is not None:
                return cached
        start = index * self._block
        end = min(start + self._block - 1, self._size - 1)
        r = self._session.get(
            self._url, headers={"Range": f"bytes={start}-{end}"}, timeout=180
        )
        if r.status_code not in (200, 206):
            r.raise_for_status()
        data = r.content
        with self._lock:
            self._cache[index] = data
            self._cache_order.append(index)
            # Keep the cache bounded; drop the oldest block.
            while len(self._cache_order) > 24:
                self._cache.pop(self._cache_order.pop(0), None)
        return data

    def read(self, size: int = -1) -> bytes:
        if self._pos >= self._size:
            return b""
        if size is None or size < 0:
            size = self._size - self._pos
        remaining = min(size, self._size - self._pos)
        chunks = []
        while remaining > 0:
            index = self._pos // self._block
            offset = self._pos % self._block
            block = self._fetch_block(index)
            take = min(remaining, len(block) - offset)
            if take <= 0:
                break
            chunks.append(block[offset : offset + take])
            self._pos += take
            remaining -= take
        return b"".join(chunks)

    def readinto(self, buffer) -> int:
        data = self.read(len(buffer))
        buffer[: len(data)] = data
        return len(data)

    def close(self) -> None:
        self._cache.clear()
        super().close()
