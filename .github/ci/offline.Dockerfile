# The whole test suite in a Linux container started with `--network none` (R1).
# Dependencies are installed at build time; the tests run with no network at all.
FROM ubuntu:24.04@sha256:a853f94d226358a79c740cfc7bce0c289748f3fe3488d921d038ccd752c61b60
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg libimage-exiftool-perl ca-certificates \
    libegl1 libgl1 libxkbcommon0 libfontconfig1 libdbus-1-3 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.12.22@sha256:f513a91fc62fe7c17567eee97230dd198e43edb8a9fbecca843714a4358fe1bc /uv /usr/local/bin/uv
ENV UV_PYTHON_INSTALL_DIR=/opt/python UV_LINK_MODE=copy BLURRY_REQUIRE_TOOLS=1 \
    QT_QPA_PLATFORM=offscreen
WORKDIR /src
COPY . .
RUN uv sync --frozen --all-extras
CMD ["uv", "run", "--frozen", "--offline", "pytest", "-q"]
