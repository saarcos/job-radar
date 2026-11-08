import socket

import pytest

_LOOPBACK = {"127.0.0.1", "::1"}


# Fails the test through pytest.fail, which is a BaseException: an
# `except Exception` around the call, like the one in the sync pipeline, cannot
# swallow it and let the test pass.
@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    real_connect = socket.socket.connect

    def guarded_connect(self, address):
        # Only internet addresses are tuples. asyncio needs loopback on Windows,
        # where FastAPI's TestClient builds its event loop's socketpair over it.
        if isinstance(address, tuple) and address[0] not in _LOOPBACK:
            pytest.fail(f"unit test tried to reach the network: {address}")
        return real_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
