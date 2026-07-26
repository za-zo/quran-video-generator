"""Unit tests for the high-level :class:`PipelineLogger`.

These tests capture the rendered output of each ``pipeline_log.*`` call
and assert on key substrings. They do NOT validate the exact format —
that's intentionally flexible so we can tweak spacing / wording without
churning the tests.
"""

from __future__ import annotations

import logging

import pytest

from src.utils.logger import (
    PipelineLogger,
    pipeline_log,
    reset_logging,
)


@pytest.fixture(autouse=True)
def _isolate_root_logger(caplog):
    """Force the root logger to capture INFO records from any handler.

    caplog sets propagate=True on the root logger and adds a
    LogCaptureHandler at level 0 by default. We just need to make sure
    the level is INFO so our messages aren't filtered out.
    """
    caplog.set_level(logging.INFO, logger="pipeline")
    # Also reset module-level configured state so each test starts clean.
    reset_logging()
    yield
    reset_logging()


def _records_text(caplog) -> str:
    """Concatenate every captured log record's message."""
    return "\n".join(r.getMessage() for r in caplog.records)


def test_batch_start_emits_batch_keyword_and_demarrage(caplog):
    p = PipelineLogger()
    p.batch_start(audio_count=1, clips_per_audio=5, clip_duration=60)
    text = _records_text(caplog)
    assert "BATCH" in text
    assert "Démarrage" in text
    assert "1 audio" in text
    assert "5 clips" in text
    assert "60s chacun" in text


def test_clip_success_contains_checkmark(caplog):
    p = PipelineLogger()
    p.clip_success(index=1, total=5)
    text = _records_text(caplog)
    assert "✓" in text
    assert "CLIP 1/5" in text
    assert "réussi" in text


def test_clip_failed_contains_cross_and_error(caplog):
    p = PipelineLogger()
    p.clip_failed(index=2, total=5, error="boom")
    text = _records_text(caplog)
    assert "✗" in text
    assert "CLIP 2/5" in text
    assert "boom" in text


def test_batch_summary_counts_succeeded_and_failed(caplog):
    p = PipelineLogger()
    p.batch_summary(succeeded=5, failed=0, total_elapsed_s=192.0)
    text = _records_text(caplog)
    assert "RÉSUMÉ" in text
    assert "5 réussis" in text
    assert "0 échoués" in text
    # 192s ≈ 3m 12s
    assert "3m 12s" in text


def test_audio_selected_emits_audio_label_and_name(caplog):
    p = PipelineLogger()
    p.audio_selected(index=1, total=1, name="Al-Fatiha",
                     usage_count=2, duration_s=252.0)
    text = _records_text(caplog)
    assert "[AUDIO 1/1]" in text
    assert "Al-Fatiha" in text
    assert "usage: 2" in text


def test_download_ok_emits_size_and_elapsed(caplog):
    p = PipelineLogger()
    # 1_258_291 bytes = 1.2 MB (1.2 * 1024 * 1024 = 1_258_291.2)
    p.download_ok(label="audio", size_bytes=1_258_291, elapsed_s=0.8)
    text = _records_text(caplog)
    assert "Téléchargement audio" in text
    assert "✓" in text
    assert "1.2 MB" in text
    assert "0.8s" in text


def test_encode_ok_emits_elapsed(caplog):
    p = PipelineLogger()
    p.encode_ok(elapsed_s=22.0)
    text = _records_text(caplog)
    assert "Encodage FFmpeg" in text
    assert "✓" in text
    assert "22s" in text


def test_upload_ok_emits_truncated_url(caplog):
    p = PipelineLogger()
    long_url = "https://res.cloudinary.com/demo/video/upload/quran-video-generator/executions/abc123def456.mp4"
    p.upload_ok(url=long_url, elapsed_s=4.2)
    text = _records_text(caplog)
    assert "Upload Cloudinary" in text
    assert "✓" in text
    # URL is truncated to 60 chars max.
    assert "..." in text


def test_category_selected_emits_name(caplog):
    p = PipelineLogger()
    p.category_selected(name="sea", usage_count=1)
    text = _records_text(caplog)
    assert "Catégorie" in text
    assert "sea" in text


def test_videos_selected_emits_count_and_total(caplog):
    p = PipelineLogger()
    p.videos_selected(count=3, total_duration_s=90.1)
    text = _records_text(caplog)
    assert "Vidéos" in text
    assert "3 fichiers" in text
    assert "1m 30s" in text


def test_module_singleton_is_pipeline_logger():
    assert isinstance(pipeline_log, PipelineLogger)
