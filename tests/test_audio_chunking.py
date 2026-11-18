import numpy as np

from app.services.audio.chunking import SR, compute_chunks, snap_boundary


def test_snap_boundary_selects_low_energy_frame_near_target():
    audio = np.ones(SR * 12, dtype=np.float32)
    audio[int(5.8 * SR):int(6.2 * SR)] = 0

    boundary = snap_boundary(audio, target_sec=6.0, search=1.0)

    assert 5.8 <= boundary <= 6.2


def test_compute_chunks_splits_audio_at_low_energy_boundary():
    audio = np.ones(SR * 125, dtype=np.float32)
    audio[int(59.8 * SR):int(60.2 * SR)] = 0

    chunks = compute_chunks(audio, chunk_minutes=1)

    assert len(chunks) == 2
    assert chunks[0][0] == 0.0
    assert 59.8 <= chunks[0][1] <= 60.2
    assert chunks[1][0] == chunks[0][1]
    assert chunks[1][1] == 125.0
