"""
Entity package for daichi_cloud_integration.

Architecture:
    All platform entities inherit from (PlatformEntity, DaichiCloudClimateEntity).
    MRO order matters — platform-specific class first, then the integration base.
    Entities read data from coordinator.data and NEVER call the API client directly.
    Unique IDs follow the pattern: {entry_id}_{description.key}

See entity/base.py for the DaichiCloudClimateEntity base class.
"""

from .base import DaichiCloudClimateEntity

__all__ = ["DaichiCloudClimateEntity"]
