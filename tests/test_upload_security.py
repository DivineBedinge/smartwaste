import io

import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image

from app.services.uploads import read_validated_image


@pytest.fixture
def anyio_backend():
    return "asyncio"


def image_bytes(image_format="PNG", size=(2, 2)):
    output = io.BytesIO()
    Image.new("RGB", size, "green").save(output, format=image_format)
    return output.getvalue()


@pytest.mark.anyio
async def test_valid_png_is_accepted():
    upload = UploadFile(io.BytesIO(image_bytes()), filename="safe.png", headers={"content-type": "image/png"})
    assert await read_validated_image(upload)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("filename", "mime", "payload", "status"),
    [
        ("active.svg", "image/svg+xml", b"<svg onload=alert(1)></svg>", 415),
        ("fake.png", "image/png", b"<script>alert(1)</script>", 400),
        ("wrong.jpg", "image/jpeg", image_bytes("PNG"), 415),
        ("path/../../evil.exe", "image/png", image_bytes("PNG"), 415),
    ],
)
async def test_malicious_or_mismatched_images_are_rejected(filename, mime, payload, status):
    upload = UploadFile(io.BytesIO(payload), filename=filename, headers={"content-type": mime})
    with pytest.raises(HTTPException) as error:
        await read_validated_image(upload)
    assert error.value.status_code == status


@pytest.mark.anyio
async def test_image_dimensions_are_limited(monkeypatch):
    monkeypatch.setenv("MAX_IMAGE_WIDTH", "1")
    upload = UploadFile(io.BytesIO(image_bytes()), filename="large.png", headers={"content-type": "image/png"})
    with pytest.raises(HTTPException) as error:
        await read_validated_image(upload)
    assert error.value.status_code == 413
