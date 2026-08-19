from gensui.services.network_scanner import _build_probe_ips


def test_probe_list_always_includes_same_pc_loopback() -> None:
    assert _build_probe_ips([]) == ["127.0.0.1"]


def test_probe_list_includes_lan_and_deduplicates_loopback() -> None:
    ips = _build_probe_ips(["192.168.10.", "127.0.0."])

    assert "127.0.0.1" in ips
    assert "192.168.10.1" in ips
    assert "192.168.10.254" in ips
    assert ips.count("127.0.0.1") == 1
