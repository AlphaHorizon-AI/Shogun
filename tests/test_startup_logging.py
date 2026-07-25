"""Regression coverage for startup error reporting."""

import inspect

from shogun.app import lifespan


def test_lifespan_does_not_shadow_module_logger() -> None:
    """Local imports must not make early migration logging unbound."""
    lifespan_body = inspect.unwrap(lifespan)

    assert "logging" not in lifespan_body.__code__.co_varnames
