"""Unit tests for :mod:`src.utils.cloudinary_uploader`.

Mocks the Cloudinary SDK so no real API call is made. Verifies:
  * happy-path upload returns the expected dataclass fields,
  * SDK exceptions are translated into :class:`CloudinaryUploadError`,
  * missing credentials raise a clear ``RuntimeError``,
  * uploading a non-existent file raises :class:`CloudinaryUploadError`.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.config.settings import Settings
from src.utils.cloudinary_uploader import (
    CloudinaryUploadError,
    reset_config,
    upload_video,
)


def _settings() -> Settings:
    return Settings(
        mongodb_uri="mongodb://localhost/test",
        mongodb_db_name="qvg_test",
        cloudinary_cloud_name="test-cloud",
        cloudinary_api_key="test-key",
        cloudinary_api_secret="test-secret",
    )


@pytest.fixture(autouse=True)
def _reset_cloudinary_config():
    reset_config()
    yield
    reset_config()


def test_upload_video_happy_path(tmp_path):
    local = tmp_path / "out.mp4"
    local.write_bytes(b"fake mp4")

    fake_resp = {
        "secure_url": "https://res.cloudinary.com/test-cloud/video/upload/v1/quran-video-generator/executions/abc.mp4",
        "public_id": "quran-video-generator/executions/abc",
        "duration": 60.0,
        "width": 1080,
        "height": 1920,
    }
    with patch("src.utils.cloudinary_uploader.cloudinary.uploader.upload",
               return_value=fake_resp) as mock_upload, \
         patch("src.utils.cloudinary_uploader.cloudinary.config"):
        result = upload_video(local, "abc", _settings())

    assert result.secure_url == fake_resp["secure_url"]
    assert result.public_id == fake_resp["public_id"]
    assert result.duration_seconds == 60.0
    assert result.width == 1080
    assert result.height == 1920
    mock_upload.assert_called_once()
    # Verify the call used the right resource_type and public_id.
    args, kwargs = mock_upload.call_args
    assert kwargs.get("resource_type") == "video"
    assert kwargs.get("public_id") == "quran-video-generator/executions/abc"


def test_upload_video_translates_sdk_exception(tmp_path):
    local = tmp_path / "out.mp4"
    local.write_bytes(b"fake mp4")

    with patch("src.utils.cloudinary_uploader.cloudinary.uploader.upload",
               side_effect=Exception("API timeout")), \
         patch("src.utils.cloudinary_uploader.cloudinary.config"):
        with pytest.raises(CloudinaryUploadError) as exc_info:
            upload_video(local, "abc", _settings())
    assert "API timeout" in str(exc_info.value) or "Cloudinary upload failed" in str(exc_info.value)


def test_upload_video_rejects_missing_file(tmp_path):
    missing = tmp_path / "does_not_exist.mp4"
    with patch("src.utils.cloudinary_uploader.cloudinary.config"):
        with pytest.raises(CloudinaryUploadError) as exc_info:
            upload_video(missing, "abc", _settings())
    assert "does not exist" in str(exc_info.value)


def test_upload_video_raises_on_missing_credentials(tmp_path):
    local = tmp_path / "out.mp4"
    local.write_bytes(b"x")
    bad_settings = Settings(
        mongodb_uri="mongodb://localhost/test",
        cloudinary_cloud_name="",
        cloudinary_api_key="",
        cloudinary_api_secret="",
    )
    with pytest.raises(RuntimeError) as exc_info:
        upload_video(local, "abc", bad_settings)
    assert "Cloudinary" in str(exc_info.value) or "cloud" in str(exc_info.value).lower()


def test_upload_video_rejects_unexpected_response(tmp_path):
    """If Cloudinary returns a non-dict or no secure_url, raise."""
    local = tmp_path / "out.mp4"
    local.write_bytes(b"x")
    with patch("src.utils.cloudinary_uploader.cloudinary.uploader.upload",
               return_value={"unexpected": "shape"}), \
         patch("src.utils.cloudinary_uploader.cloudinary.config"):
        with pytest.raises(CloudinaryUploadError):
            upload_video(local, "abc", _settings())
