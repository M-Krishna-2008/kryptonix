"""
Base interface and dataclasses for forensic engines.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import numpy as np


@dataclass
class EngineOutput:
    """Output produced by a forensic detection engine."""
    anomaly_map: np.ndarray  # float32 HxW array in [0.0, 1.0], scaled to ORIGINAL image size
    global_score: Optional[float] = None  # Scalar score in [0.0, 1.0] or None
    score_is_native: bool = False  # True if model outputs a native image-level score, False if derived
    confidence_map: Optional[np.ndarray] = None  # Optional reliability/confidence map float32 HxW
    extras: Dict[str, Any] = field(default_factory=dict)
    runtime_sec: float = 0.0
    device: str = "cpu"
    scale_factor: float = 1.0


class BaseEngine(ABC):
    """Abstract base class for all detection engines."""

    name: str = "base"

    @abstractmethod
    def check_available(self) -> Tuple[bool, str]:
        """
        Check if the engine can be executed (weights present, dependencies met).
        Returns (available: bool, reason: str).
        """
        pass

    @abstractmethod
    def applicable(self, image_info: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Check if engine applies to this image format and characteristics.
        Returns (applicable: bool, reason: str).
        """
        pass

    @abstractmethod
    def run(self, image_path: Path, work_dir: Path, opts: Dict[str, Any]) -> EngineOutput:
        """
        Execute engine on image_path and return EngineOutput.
        Must run in isolated subprocess or safe context.
        """
        pass
