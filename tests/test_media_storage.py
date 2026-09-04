import hashlib
import io
from pathlib import Path

import pytest
from PIL import Image

from app.services.media_assets import store_media_with_compensation
from app.services.media_storage import LocalPrivateMediaStorage, validated_storage_root


def image_bytes(fmt="PNG", size=(2, 3)):
    output = io.BytesIO()
    Image.new("RGB", size, "red").save(output, format=fmt)
    return output.getvalue()


def test_local_storage_saves_normalized_uuid_media(tmp_path, monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "100000")
    storage = LocalPrivateMediaStorage(tmp_path / "private")
    saved = storage.save(image_bytes(), "image/png")
    assert len(Path(saved.storage_key).stem) == 32
    assert saved.extension == ".png" and saved.width == 2 and saved.height == 3
    with storage.open(saved.storage_key) as stream:
        content = stream.read()
    assert hashlib.sha256(content).hexdigest() == saved.sha256
    assert storage.exists(saved.storage_key)
    storage.delete(saved.storage_key)
    assert not storage.exists(saved.storage_key)
    assert not list(storage.root.glob(".upload-*"))


@pytest.mark.parametrize("key", ["../secret.png", "folder/file.png", "/absolute.png"])
def test_storage_rejects_path_traversal(tmp_path, key):
    storage = LocalPrivateMediaStorage(tmp_path / "private")
    with pytest.raises(ValueError):
        storage.open(key)


def test_storage_rejects_mime_size_dimensions_and_corruption(tmp_path, monkeypatch):
    storage = LocalPrivateMediaStorage(tmp_path / "private")
    with pytest.raises(ValueError): storage.save(image_bytes(), "image/jpeg")
    with pytest.raises(Exception): storage.save(b"<svg/>", "image/png")
    with pytest.raises(Exception): storage.save(b"broken", "image/png")
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "5")
    with pytest.raises(ValueError): storage.save(image_bytes(), "image/png")
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "100000")
    monkeypatch.setenv("MAX_IMAGE_WIDTH", "1")
    with pytest.raises(ValueError): storage.save(image_bytes(), "image/png")
    assert not list(storage.root.glob(".upload-*"))


def test_storage_root_refuses_public_repository_and_system_paths():
    project = Path(__file__).resolve().parents[1]
    for value in (project, project / "static", project / ".git", Path(project.anchor)):
        with pytest.raises(RuntimeError): validated_storage_root(str(value))


class BrokenCursor:
    def execute(self, *_): raise RuntimeError("sql failed")
    def close(self): pass


class BrokenConnection:
    def cursor(self): return BrokenCursor()


def test_sql_failure_compensates_saved_file(tmp_path):
    storage = LocalPrivateMediaStorage(tmp_path / "private")
    with pytest.raises(RuntimeError):
        store_media_with_compensation(BrokenConnection(),1,"report_initial",image_bytes(),"image/png",storage=storage)
    assert list(storage.root.iterdir()) == []
