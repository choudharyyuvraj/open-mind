"""
Configuration utilities for OpenMind local mode.

This module provides a lightweight configuration object that reads values from
environment variables with sensible defaults. It is intentionally minimal and
fits the standalone gateway runtime.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class OpenMindConfig:
    """
    Small wrapper around environment-based configuration.

    All fields are optional overrides for local runtime configuration.
    """

    log_level: str = "INFO"
    storage_dir: str = ".openmind_storage"
    metrics_sample_interval_sec: int = 60


def load_config() -> OpenMindConfig:
    """
    Load OpenMind-specific configuration from environment variables.

    - OPENMIND_LOG_LEVEL
    - OPENMIND_STORAGE_DIR
    - OPENMIND_METRICS_SAMPLE_INTERVAL_SEC
    """
    log_level = os.getenv("OPENMIND_LOG_LEVEL", "INFO")
    storage_dir = os.getenv("OPENMIND_STORAGE_DIR", ".openmind_storage")
    interval_raw = os.getenv("OPENMIND_METRICS_SAMPLE_INTERVAL_SEC", "60")
    try:
        interval = int(interval_raw)
    except ValueError:
        interval = 60

    return OpenMindConfig(
        log_level=log_level,
        storage_dir=storage_dir,
        metrics_sample_interval_sec=interval,
    )

