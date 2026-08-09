"""Deterministic Mapping / RPA engine for AgentFlows."""

from shogun.mapping.engine import MappingEngine, execute_mapping
from shogun.mapping.errors import (
    MappingError,
    MappingFieldMissing,
    MappingInputError,
    MappingOutputError,
    MappingSchemaError,
    MappingTargetError,
    MappingTransformationError,
    MappingTypeError,
)
from shogun.mapping.schema import MappingConfig, MappingRule

__all__ = [
    "MappingConfig",
    "MappingEngine",
    "MappingError",
    "MappingFieldMissing",
    "MappingInputError",
    "MappingOutputError",
    "MappingRule",
    "MappingSchemaError",
    "MappingTargetError",
    "MappingTransformationError",
    "MappingTypeError",
    "execute_mapping",
]
