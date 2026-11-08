import socket

import pytest


def test_unit_tests_cannot_reach_the_network():
    with socket.socket() as sock:
        # 192.0.2.1 is reserved for documentation: nothing answers there, and
        # being a literal address, it needs no DNS lookup.
        with pytest.raises(pytest.fail.Exception, match="tried to reach the network"):
            sock.connect(("192.0.2.1", 80))
