"""Constants for the Furbulous integration."""

DOMAIN = "furbulous"

# Config entry keys
CONF_REGION = "region"
CONF_ACCOUNT_TYPE = "account_type"
CONF_TOKEN = "token"
# One-shot: weight unit overrides cleared after upgrade (sticky g/kg/lb)
CONF_DISPLAY_RESET_DONE = "display_reset_done"
# One-shot: clear sticky registry units after switch to calculated lb/kg (1.2.2+)
CONF_WEIGHT_CALC_UNIT_RESET_DONE = "weight_calc_unit_reset_done"
# One-shot: purge entity registry so cat-parent unique_id scheme recreates cleanly (1.3.7)
CONF_CAT_UID_SCHEME_V1_DONE = "cat_uid_scheme_v1_done"
# One-shot: enable all previously disabled-by-default entities (1.3.8)
CONF_ENABLE_ALL_ENTITIES_DONE = "enable_all_entities_done"

# Config entry version (v2 adds region)
CONFIG_VERSION = 2

# API path constants (host comes from regions.py)
API_AUTH_ENDPOINT = "/app/v1/auth/login"
API_DEVICE_LIST_ENDPOINT = "/app/v1/device/list"
API_DEVICE_PROPERTIES_ENDPOINT = "/app/v1/device/properties/get"

# API client identity (from decompiled app / reverse engineering)
API_APPID = "a0baae0630f444b0811ea3c2eb212179"
API_VERSION = "1.0.0"
API_PLATFORM = "ios"
API_USER_AGENT = (
    "Furbulous/2.0.1 (com.furbulous.pet; build:202507031750; iOS 26.0.1) "
    "Alamofire/4.9.1"
)

DEFAULT_ACCOUNT_TYPE = 1

# Device types
PRODUCT_FURBULOUS_BOX = 1

# Work status codes (raw values; entity names use translations)
WORK_STATUS = {
    0: "Idle",
    1: "Working",
    2: "Cleaning",
    3: "Paused",
    4: "Error",
}

LITTER_TYPE = {
    0: "Bentonite",
    1: "Tofu",
    2: "Mixed",
}

# errorReportEvent values (shown as state/attributes; English baseline)
ERROR_CODES = {
    0: "No error",
    1: "Sensor error - Weight sensor",
    2: "Sensor error - IR sensor",
    4: "Motor error - Rotation blocked",
    8: "Motor error - Overload",
    16: "Bag full - seal bag",
    32: "Bag full - seal bag",
    # 64 alone was never seen live; describe_error labels it "Error 64"
    128: "Remove Sealed Bag",
    256: "Temperature error",
    512: "Cover / lid off",
    4096: "Litter pour",
    524288: "Trash door blocked",
}

ERROR_SEVERITY = {
    0: "info",
    1: "warning",
    2: "warning",
    4: "error",
    8: "error",
    16: "warning",
    32: "warning",
    64: "warning",
    128: "warning",
    256: "error",
    512: "warning",
    4096: "info",
    524288: "error",
}

# Polling
UPDATE_INTERVAL_NORMAL_MINUTES = 5
UPDATE_INTERVAL_FAST_SECONDS = 30
# Pet roster (account-scoped): slower than presence; properties stay at 30s
PET_LIST_MIN_INTERVAL_SECONDS = 60
