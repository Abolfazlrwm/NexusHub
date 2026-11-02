"""Tests for agent configuration validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexusagent.config import AgentConfig


def test_defaults() -> None:
    config = AgentConfig()
    assert config.model == "gpt-4o-mini"
    assert config.system_prompt is None
    assert config.temperature == 0.7
    assert config.max_iterations == 8
    assert config.max_tokens is None
    assert config.parallel_tool_calls is True
    assert config.request_timeout == 120.0
    assert config.extra_headers == {}


def test_config_is_immutable() -> None:
    config = AgentConfig()
    with pytest.raises(ValidationError):
        config.temperature = 0.1


def test_temperature_bounds() -> None:
    with pytest.raises(ValidationError):
        AgentConfig(temperature=2.5)
    with pytest.raises(ValidationError):
        AgentConfig(temperature=-0.1)
    AgentConfig(temperature=0.0)
    AgentConfig(temperature=2.0)


def test_max_iterations_bounds() -> None:
    with pytest.raises(ValidationError):
        AgentConfig(max_iterations=0)
    with pytest.raises(ValidationError):
        AgentConfig(max_iterations=65)
    assert AgentConfig(max_iterations=1).max_iterations == 1


def test_max_tokens_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        AgentConfig(max_tokens=0)
    assert AgentConfig(max_tokens=512).max_tokens == 512


def test_request_timeout_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        AgentConfig(request_timeout=0)
