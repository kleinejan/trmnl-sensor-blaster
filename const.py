"""Constants for the TRMNL Entity Push integration."""
DOMAIN = "trmnl_sensor_push"
CONF_URL = "url"
CONF_SENSOR_GROUPS = "sensor_groups"
DEFAULT_URL = "https://usetrmnl.com/api/custom_plugins/XXXX-XXXX-XXXX-XXXX"  # Example URL
MIN_TIME_BETWEEN_UPDATES = 1800  # 30 minutes in seconds
MAX_PAYLOAD_SIZE = 2048  # 2KB limit for TRMNL API
DEFAULT_SENSOR_GROUPS = ["TRMNL"]  # Backward compatibility
