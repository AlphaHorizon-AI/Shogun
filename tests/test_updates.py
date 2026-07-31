from shogun.api.updates import _frontend_install_failure_detail


def test_frontend_install_failure_explains_locked_windows_file():
    detail = _frontend_install_failure_detail(
        "npm error code EPERM\nnpm error syscall stat\nnpm error operation not permitted"
    )

    assert "Windows file permissions" in detail
    assert "retry" in detail


def test_frontend_install_failure_explains_network_problem():
    detail = _frontend_install_failure_detail("npm error code ECONNRESET\nnetwork socket disconnected")

    assert "network connection" in detail


def test_frontend_install_failure_keeps_unknown_errors_safe():
    detail = _frontend_install_failure_detail("unexpected package manager failure")

    assert detail == "Frontend dependency installation failed. Check the Shogun server log for npm details."
