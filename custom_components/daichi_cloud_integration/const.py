"""Constants for daichi_cloud_integration."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

# Integration metadata
DOMAIN = "daichi_cloud_integration"
ATTRIBUTION = "Data provided by Daichi Cloud."
DEFAULT_API_URL = "https://web.daichicloud.ru/api/v4"
DEFAULT_CLIENT_ID = "sOJO7B6SqgaKudTfCzqLAy540cCuDzpI"

# Platform parallel updates - applied to all platforms
PARALLEL_UPDATES = 1

# Default configuration values
DEFAULT_UPDATE_INTERVAL_HOURS = 1
DEFAULT_ENABLE_DEBUGGING = False
