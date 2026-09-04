from __future__ import annotations

import hashlib
import io
import os
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from PIL import Image, ImageOps

from app.services.uploads import ALLOWED_IMAGE_FORMATS, ALLOWED_MIME_TYPES


@dataclass(frozen=True)
class StoredMedia:
    storage_key: str
    mime_type: str
    extension: str
    size_bytes: int
    width: int
    height: int
    sha256: str


class MediaStorage(ABC):
    @abstractmethod
    def save(self, content: bytes, declared_mime: str) -> StoredMedia: ...

    @abstractmethod
    def open(self, storage_key: str) -> BinaryIO: ...

    @abstractmethod
    def delete(self, storage_key: str) -> None: ...

    @abstractmethod
    def exists(self, storage_key: str) -> bool: ...


def validated_storage_root(value: str | None = None) -> Path:
    raw = (value if value is not None else os.getenv("MEDIA_STORAGE_PATH", "./var/private_media")).strip()
    if not raw:
        raise RuntimeError("MEDIA_STORAGE_PATH ne doit pas être vide")
    root = Path(raw).expanduser().resolve()
    project = Path(__file__).resolve().parents[2]
    forbidden = {Path(root.anchor).resolve(), project, (project / "static").resolve(), (project / ".git").resolve()}
    if root in forbidden or any(parent in {(project / "static").resolve(), (project / ".git").resolve()} for parent in (root, *root.parents)):
        raise RuntimeError("MEDIA_STORAGE_PATH pointe vers un emplacement interdit")
    return root


def _safe_key(storage_key: str) -> str:
    candidate = Path(storage_key)
    if candidate.is_absolute() or len(candidate.parts) != 1 or candidate.name != storage_key or ".." in candidate.parts:
        raise ValueError("Clé de stockage invalide")
    return storage_key


class LocalPrivateMediaStorage(MediaStorage):
    def __init__(self, root: str | Path | None = None):
        self.root = validated_storage_root(str(root) if root is not None else None)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, storage_key: str) -> Path:
        return self.root / _safe_key(storage_key)

    def save(self, content: bytes, declared_mime: str) -> StoredMedia:
        maximum = int(os.getenv("MAX_UPLOAD_BYTES", "10485760"))
        if not content or len(content) > maximum or declared_mime not in ALLOWED_MIME_TYPES:
            raise ValueError("Média vide, trop volumineux ou MIME interdit")
        with Image.open(io.BytesIO(content)) as source:
            source.load()
            detected = source.format
            if detected != ALLOWED_MIME_TYPES[declared_mime] or detected not in ALLOWED_IMAGE_FORMATS:
                raise ValueError("Le contenu ne correspond pas au MIME déclaré")
            if source.width > int(os.getenv("MAX_IMAGE_WIDTH", "8192")) or source.height > int(os.getenv("MAX_IMAGE_HEIGHT", "8192")):
                raise ValueError("Dimensions excessives")
            clean = ImageOps.exif_transpose(source)
            if detected == "JPEG" and clean.mode not in {"RGB", "L"}:
                clean = clean.convert("RGB")
            output = io.BytesIO()
            clean.save(output, format=detected, exif=b"")
            normalized = output.getvalue()
            width, height = clean.size
        extension = ALLOWED_IMAGE_FORMATS[detected]
        key = f"{uuid4().hex}{extension}"
        target = self._path(key)
        descriptor, temporary = tempfile.mkstemp(prefix=".upload-", dir=str(self.root))
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(normalized)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        except Exception:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise
        return StoredMedia(key, declared_mime, extension, len(normalized), width, height, hashlib.sha256(normalized).hexdigest())

    def open(self, storage_key: str) -> BinaryIO:
        return self._path(storage_key).open("rb")

    def delete(self, storage_key: str) -> None:
        try:
            self._path(storage_key).unlink()
        except FileNotFoundError:
            pass

    def exists(self, storage_key: str) -> bool:
        return self._path(storage_key).is_file()


def get_media_storage() -> MediaStorage:
    return LocalPrivateMediaStorage()
