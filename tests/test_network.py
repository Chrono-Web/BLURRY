"""R1: no network, from Python or from FFmpeg."""

import subprocess
import sys

import pytest
from conftest import run_blurry

from blurry_opsec import video_io
from blurry_opsec.files import InputError

GUARD_PROBE = r"""
import socket
from blurry_opsec import netguard
netguard.install()
results = []
for name, call in [
    ("connect", lambda: socket.create_connection(("1.1.1.1", 443), timeout=1)),
    ("socket4", lambda: socket.socket()),
    ("socket6", lambda: socket.socket(socket.AF_INET6, socket.SOCK_STREAM)),
    ("dns", lambda: socket.getaddrinfo("example.com", 443)),
    ("gethostbyname", lambda: socket.gethostbyname("example.com")),
    ("server", lambda: socket.create_server(("127.0.0.1", 0))),
]:
    try:
        call()
        results.append(f"{name}:ALLOWED")
    except netguard.NetworkBlockedError:
        results.append(f"{name}:blocked")
if hasattr(socket, "AF_UNIX"):
    socket.socket(socket.AF_UNIX).close()
    results.append("unix:ok")
print(" ".join(results))
"""


def test_guard_blocks_python_networking():
    out = subprocess.run(
        [sys.executable, "-c", GUARD_PROBE], capture_output=True, text=True, check=True
    ).stdout
    assert "ALLOWED" not in out, out
    assert out.count("blocked") == 6


def test_guard_is_installed_by_the_entry_point():
    probe = (
        "import blurry_opsec.__main__, socket\n"
        "from blurry_opsec import netguard\n"
        "assert netguard.is_installed()\n"
        "try:\n    socket.create_connection(('1.1.1.1', 443))\n"
        "except netguard.NetworkBlockedError:\n    print('blocked')\n"
    )
    out = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True).stdout
    assert out.strip() == "blocked"


@pytest.mark.parametrize(
    "url", ["https://example.com/a.mp4", "http://127.0.0.1:9/x.jpg", "rtsp://127.0.0.1/stream.mp4"]
)
def test_urls_are_refused(url, outdir):
    res = run_blurry(url, "-o", outdir, "--json")
    assert res.returncode == 1
    assert '"status": "error"' in res.stdout
    assert not list(outdir.iterdir())


HLS = "#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:10\n#EXTINF:10.0,\nhttp://127.0.0.1:9/segment.ts\n#EXT-X-ENDLIST\n"


def test_hls_playlist_is_refused(tmp_path, outdir):
    playlist = tmp_path / "list.m3u8"
    playlist.write_text(HLS)
    res = run_blurry(playlist, "-o", outdir)
    assert res.returncode == 1
    assert not list(outdir.iterdir())


@pytest.mark.parametrize("ext", [".avi", ".mp4", ".mkv"])
def test_hls_hidden_in_a_video_is_refused(tmp_path, outdir, ext):
    fake = tmp_path / f"holiday{ext}"
    fake.write_text(HLS)
    with pytest.raises(InputError), video_io.open_input(fake):
        pass
    res = run_blurry(fake, "-o", outdir)
    assert res.returncode == 1
    assert not list(outdir.iterdir())


def test_ffmpeg_inputs_are_whitelisted():
    assert set(video_io.FORMAT_WHITELIST.split(",")) == {"mov", "mp4", "matroska", "webm", "avi"}


def test_fifo_and_directories_are_refused(tmp_path, outdir):
    res = run_blurry(tmp_path, "-o", outdir)
    assert res.returncode == 1
