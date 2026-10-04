# Runtime-only verification: no Python, source checkout or development environment.
FROM ubuntu:24.04@sha256:a853f94d226358a79c740cfc7bce0c289748f3fe3488d921d038ccd752c61b60
RUN apt-get update && apt-get install -y --no-install-recommends \
    libegl1 libgl1 libxkbcommon0 libfontconfig1 libdbus-1-3 libglib2.0-0 \
    libxcb-cursor0 libxkbcommon-x11-0 libxcb-icccm4 libxcb-keysyms1 \
    libxcb-shape0 libxcb-xinerama0 fonts-dejavu-core xvfb xauth \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home smoke
COPY build/desktop-packages/Blurry-*-linux-x86_64.tar.gz /tmp/package.tar.gz
COPY tests/fixtures/public/dental_squadron.jpg /tmp/fixture.jpg
COPY packaging/linux/test-installed.sh /tmp/test-installed.sh
USER smoke
ENV HOME=/home/smoke
CMD ["sh", "/tmp/test-installed.sh"]
