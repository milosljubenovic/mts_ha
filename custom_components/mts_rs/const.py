"""Constants for the MTS RS integration."""

DOMAIN = "mts_rs"

CONF_MSISDNS = "msisdns"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = 3600

PLATFORMS = ["sensor"]

ATTR_MSISDN = "msisdn"
ATTR_MSISDN_FORMATTED = "msisdn_formatted"
ATTR_BALANCE = "balance"
ATTR_CREDIT_EXPIRES = "credit_expires"
ATTR_SIM_EXPIRES = "sim_expires"
ATTR_PACKAGE_NAME = "package_name"
ATTR_PACKAGE_START = "package_start"
ATTR_PACKAGE_END = "package_end"
ATTR_PACKAGE_AUTO_RENEW = "package_auto_renew"
ATTR_QUOTA_EXPIRES = "quota_expires"
ATTR_QUOTA_UNIT = "quota_unit"
