"""
Logging utilities for OpenMind local mode.

Provides a simple structured logging setup for gateway and memory runtime
components.
"""

from __future__ import annotations

import logging
import os
from typing import Optional


def setup_logging(level: Optional[str] = None) -> None:
    """
    Configure root logging with a simple structured format.

    If `level` is not provided, OPENMIND_LOG_LEVEL or INFO is used.
    """
    if level is None:
        level = os.getenv("OPENMIND_LOG_LEVEL", "INFO")

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

