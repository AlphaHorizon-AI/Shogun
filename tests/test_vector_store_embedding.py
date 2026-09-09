"""Memory embeddings stay available when Apple's GPU cannot load the model."""

import sys
from types import SimpleNamespace
from unittest.mock import Mock, call

import numpy as np
import pytest

from shogun.engine.vector_store import EMBEDDING_MODEL, VectorStore


def embedding_factory(monkeypatch, *results):
    factory = Mock(side_effect=list(results))
    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=factory))
    return factory


def test_automatic_device_embeds_and_reuses_loaded_model(monkeypatch):
    model = Mock()
    model.encode.return_value = np.array([0.25, 0.75])
    factory = embedding_factory(monkeypatch, model)
    store = VectorStore()

    assert store.embed("first memory") == [0.25, 0.75]
    assert store.embed("second memory") == [0.25, 0.75]
    factory.assert_called_once_with(EMBEDDING_MODEL)


def test_mps_allocation_failure_retries_on_cpu_and_embeds(monkeypatch, caplog):
    model = Mock()
    model.encode.return_value = np.array([0.25, 0.75])
    factory = embedding_factory(monkeypatch, RuntimeError("MPS backend out of memory"), model)
    store = VectorStore()

    assert store.embed("memory on a Mac") == [0.25, 0.75]
    assert store.embed("another memory") == [0.25, 0.75]
    assert factory.call_args_list == [call(EMBEDDING_MODEL), call(EMBEDDING_MODEL, device="cpu")]
    assert "retrying on CPU" in caplog.text


def test_unrelated_model_error_is_not_hidden(monkeypatch):
    failure = RuntimeError("Invalid model weights")
    factory = embedding_factory(monkeypatch, failure)

    with pytest.raises(RuntimeError, match="Invalid model weights") as caught:
        VectorStore().embed("memory")

    assert caught.value is failure
    factory.assert_called_once_with(EMBEDDING_MODEL)


def test_cpu_retry_failure_is_propagated(monkeypatch):
    failure = RuntimeError("CPU allocation failed")
    embedding_factory(monkeypatch, RuntimeError("MPS backend out of memory"), failure)

    with pytest.raises(RuntimeError, match="CPU allocation failed") as caught:
        VectorStore().embed("memory")

    assert caught.value is failure
