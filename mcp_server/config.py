"""MCP Server configuration."""

HOST = "0.0.0.0"
PORT = 8002

# UAE property tax rates by emirate (approximate annual %)
# Source: DLD, Abu Dhabi Municipality, various emirate regulations
TAX_RATES = {
    "dubai": {
        "housing_fee": 5.0,        # 5% of annual rent (DEWA housing fee)
        "municipality_fee": 0.0,    # Included in housing fee for tenants
        "registration_fee": 4.0,    # 4% of property value (one-time, buyer)
    },
    "abu dhabi": {
        "housing_fee": 3.0,        # 3% of annual rent
        "municipality_fee": 0.0,
        "registration_fee": 2.0,    # 2% of property value (one-time, buyer)
    },
    "sharjah": {
        "housing_fee": 2.0,        # 2% of annual rent
        "municipality_fee": 0.0,
        "registration_fee": 2.0,
    },
    "ajman": {
        "housing_fee": 2.0,
        "municipality_fee": 0.0,
        "registration_fee": 2.0,
    },
    "ras al khaimah": {
        "housing_fee": 2.0,
        "municipality_fee": 0.0,
        "registration_fee": 2.0,
    },
}

# Default rates for emirates not in the lookup
DEFAULT_TAX_RATES = {
    "housing_fee": 2.0,
    "municipality_fee": 0.0,
    "registration_fee": 2.0,
}
