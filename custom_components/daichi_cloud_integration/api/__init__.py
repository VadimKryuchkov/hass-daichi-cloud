"""
API package for daichi_cloud_integration.

Architecture:
    Three-layer data flow: Entities → Coordinator → API Client.
    Only the coordinator should call the API client. Entities must never
    import or call the API client directly.

Exception hierarchy:
    DaichiCloudClimateApiClientError (base)
    ├── DaichiCloudClimateApiClientCommunicationError (network/timeout)
    └── DaichiCloudClimateApiClientAuthenticationError (401/403)

Coordinator exception mapping:
    ApiClientAuthenticationError → ConfigEntryAuthFailed (triggers reauth)
    ApiClientCommunicationError → UpdateFailed (auto-retry)
    ApiClientError             → UpdateFailed (auto-retry)
"""

from .client import (
    DaichiCloudClimateApiClient,
    DaichiCloudClimateApiClientAuthenticationError,
    DaichiCloudClimateApiClientCommunicationError,
    DaichiCloudClimateApiClientError,
)

__all__ = [
    "DaichiCloudClimateApiClient",
    "DaichiCloudClimateApiClientAuthenticationError",
    "DaichiCloudClimateApiClientCommunicationError",
    "DaichiCloudClimateApiClientError",
]
