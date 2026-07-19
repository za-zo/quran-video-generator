"""Unit tests for :mod:`src.utils.media_downloader`.

Uses ``unittest.mock`` to fake ``requests.get`` so no real network access
is required. Verifies:
  * happy-path download writes bytes to the destination,
  * non-2xx responses raise :class:`CorruptedMediaError`,
  * network errors raise :class:`CorruptedMediaError`,
  * retry-once behaviour on transient failure,
  * ffprobe validation hook is invoked when ``expect_audio``/``expect_video``
    is set.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.exceptions import CorruptedMediaError
from src.utils import media_downloader


def _fake_response(*, status: int = 200, chunks: list[bytes] | None = None,
                   reason: str = "OK") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.reason = reason
    resp.iter_content = lambda chunk_size: iter(chunks or [])
    # ``with requests.get(...) as resp:`` requires __enter__/__exit__.
    resp.__enter__ = lambda self: self
    resp.__exit__ = lambda self, *args: None
    return resp


def test_download_happy_path(tmp_path):
    fake = _fake_response(chunks=[b"hello", b" world"])
    with patch("src.utils.media_downloader.requests.get", return_value=fake) as mock_get:
        out = media_downloader.download_to_temp(
            "https://example.com/file.mp4", tmp_path,
            expected_extension=".mp4",
        )
    assert out.read_bytes() == b"hello world"
    assert out.name == "file.mp4"
    mock_get.assert_called_once()


def test_download_non_2xx_raises_corrupted(tmp_path):
    fake = _fake_response(status=404, reason="Not Found")
    with patch("src.utils.media_downloader.requests.get", return_value=fake):
        with pytest.raises(CorruptedMediaError) as exc_info:
            media_downloader.download_to_temp(
                "https://example.com/missing.mp4", tmp_path,
                expected_extension=".mp4",
            )
    assert "404" in str(exc_info.value)


def test_download_network_error_raises_corrupted(tmp_path):
    err = requests.ConnectionError("DNS down")
    with patch("src.utils.media_downloader.requests.get", side_effect=err):
        with pytest.raises(CorruptedMediaError):
            media_downloader.download_to_temp(
                "https://example.com/file.mp4", tmp_path,
                expected_extension=".mp4",
            )


def test_download_retries_once_on_transient_failure(tmp_path):
    """A first failure followed by a success should yield a successful download."""
    success_resp = _fake_response(chunks=[b"data"])
    side_effects = [
        requests.ConnectionError("transient"),
        success_resp,
    ]
    with patch("src.utils.media_downloader.requests.get", side_effect=side_effects):
        out = media_downloader.download_to_temp(
            "https://example.com/file.mp4", tmp_path,
            expected_extension=".mp4",
            retries=1,
        )
    assert out.read_bytes() == b"data"


def test_download_empty_file_raises_corrupted(tmp_path):
    """A 200 response with no body is a corrupt download."""
    fake = _fake_response(chunks=[])
    with patch("src.utils.media_downloader.requests.get", return_value=fake):
        with pytest.raises(CorruptedMediaError) as exc_info:
            media_downloader.download_to_temp(
                "https://example.com/empty.mp4", tmp_path,
                expected_extension=".mp4",
            )
    assert "empty" in str(exc_info.value).lower()


def test_download_validates_with_ffprobe_when_expected(tmp_path):
    """When ``expect_video=True`` is set, ffprobe validation is invoked."""
    fake = _fake_response(chunks=[b"\x00\x00\x00\x18ftypmp42"])
    with patch("src.utils.media_downloader.requests.get", return_value=fake), \
         patch("src.utils.media_downloader.validate_media") as mock_validate:
        media_downloader.download_to_temp(
            "https://example.com/file.mp4", tmp_path,
            expected_extension=".mp4", expect_video=True,
        )
    mock_validate.assert_called_once()


def test_download_extension_inferred_from_url_when_not_given(tmp_path):
    fake = _fake_response(chunks=[b"x"])
    with patch("src.utils.media_downloader.requests.get", return_value=fake):
        out = media_downloader.download_to_temp(
            "https://example.com/audio.mp3", tmp_path,
        )
    assert out.suffix == ".mp3"


def test_download_empty_url_raises_immediately(tmp_path):
    with pytest.raises(CorruptedMediaError):
        media_downloader.download_to_temp("", tmp_path)
