"""R2: nothing left on disk except the chosen output."""

import os
import shutil

import pytest
from conftest import PUBLIC, need, run_blurry
from media import frames_from, write_video

from blurry_opsec import tempfiles


def snapshot(*dirs):
    return {d: sorted(p.relative_to(d) for p in d.rglob("*")) for d in dirs}


def test_no_traces_besides_the_output(tmp_path):
    need("ffmpeg")
    tmp, inbox, out = (tmp_path / n for n in ("tmp", "in", "out"))
    for d in (tmp, inbox, out):
        d.mkdir()
    shutil.copy(PUBLIC / "sts125_gps.heic", inbox / "photo.heic")
    write_video(inbox / "clip.mp4", frames_from("challenger_51l_crew.jpg", 320, 240, 10))
    before = snapshot(inbox)
    env = {"TMPDIR": str(tmp), "TEMP": str(tmp), "TMP": str(tmp)}
    res = run_blurry(inbox / "photo.heic", inbox / "clip.mp4", "-o", out, env=env)
    assert res.returncode == 0, res.stderr
    assert snapshot(inbox) == before
    assert sorted(p.name for p in out.iterdir()) == ["clip.blurry.mp4", "photo.blurry.jpg"]
    assert not list(tmp.iterdir())


def test_failed_run_leaves_no_partial(tmp_path):
    bad = tmp_path / "broken.mp4"
    bad.write_bytes(b"\x00\x00\x00\x18ftypmp42" + os.urandom(4096))
    out = tmp_path / "out"
    out.mkdir()
    res = run_blurry(bad, "-o", out)
    assert res.returncode == 1
    assert not list(out.iterdir())


@pytest.mark.skipif(os.name != "posix", reason="pid check is POSIX only")
def test_stale_temp_dirs_removed_on_start(tmp_path, monkeypatch):
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", None)
    dead = tmp_path / "blurry-crashed"
    dead.mkdir()
    (dead / ".pid").write_text("999999")
    (dead / "frame.png").write_bytes(b"x")
    alive = tmp_path / "blurry-running"
    alive.mkdir()
    (alive / ".pid").write_text(str(os.getppid()))
    other = tmp_path / "someone-else"
    other.mkdir()
    assert tempfiles.cleanup_stale() == 1
    assert not dead.exists() and alive.exists() and other.exists()


def test_private_dir_mode(monkeypatch, tmp_path):
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", None)
    d = tempfiles.make_private_dir()
    assert d.name.startswith("blurry-")
    if os.name == "posix":
        assert (d.stat().st_mode & 0o777) == 0o700
