"""Block network access inside the current process.

Blurry never needs the network. This module is installed before anything else
in every process (CLI, app, worker) so that a dependency, a bug or a crafted
file cannot open an IPv4/IPv6 connection or resolve a host name through
Python's socket module.

FFmpeg has its own network stack, which does not go through Python: video_io
closes that path separately with protocol and format whitelists.
"""

from __future__ import annotations

import socket

_BLOCKED_FAMILIES = {socket.AF_INET, socket.AF_INET6}
_installed = False


class NetworkBlockedError(OSError):
    """Raised on any attempt to use the network."""

    def __init__(self, what: str) -> None:
        super().__init__(f"network access is disabled in Blurry (attempted: {what})")


def _refuse(what: str):
    def blocked(*_args, **_kwargs):
        raise NetworkBlockedError(what)

    return blocked


class _GuardedSocket(socket.socket):
    def __init__(self, family=-1, type=-1, proto=-1, fileno=None):  # noqa: A002
        # socket.socket() defaults to AF_INET when family is not given.
        resolved = socket.AF_INET if family == -1 and fileno is None else family
        if resolved in _BLOCKED_FAMILIES:
            raise NetworkBlockedError(f"socket({socket.AddressFamily(resolved).name})")
        super().__init__(family, type, proto, fileno)


def install() -> None:
    """Patch the socket module. Idempotent."""
    global _installed
    if _installed:
        return
    socket.socket = _GuardedSocket  # type: ignore[misc]
    socket.SocketType = _GuardedSocket  # type: ignore[misc]
    socket.create_connection = _refuse("create_connection")
    socket.create_server = _refuse("create_server")
    socket.getaddrinfo = _refuse("getaddrinfo")
    socket.gethostbyname = _refuse("gethostbyname")
    socket.gethostbyname_ex = _refuse("gethostbyname_ex")
    socket.gethostbyaddr = _refuse("gethostbyaddr")
    socket.getnameinfo = _refuse("getnameinfo")
    _installed = True


def is_installed() -> bool:
    return _installed
