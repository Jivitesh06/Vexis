import re

# -------------------------------------------------------------------
# OBD-II feature valid ranges  (min, max)
# -------------------------------------------------------------------
OBD_RANGES = {
    "engine_rpm":       (0,    8000),
    "vehicle_speed":    (0,    250),
    "coolant_temp":     (-40,  130),
    "engine_load_pct":  (0,    100),
    "throttle_pos":     (0,    100),
    "short_fuel_trim":  (-25,  25),
    "long_fuel_trim":   (-25,  25),
    "intake_air_temp":  (-40,  120),
    "maf":              (0,    655),
    "fuel_level":       (0,    100),
    "o2_voltage":       (0,    1.275),
}


def validate_signup(data):
    """
    Validate user signup payload.
    Returns (True, None) on success or (False, "error message") on failure.
    """
    name = data.get("name", "")
    if not name or not str(name).strip():
        return False, "Name is required"

    email = data.get("email", "")
    if not re.match(r'^[^@]+@[^@]+\.[^@]+$', str(email)):
        return False, "Invalid email format"

    password = data.get("password", "")
    if len(str(password)) < 8:
        return False, "Password must be at least 8 characters"

    confirm_password = data.get("confirm_password", "")
    if str(password) != str(confirm_password):
        return False, "Passwords do not match"

    return True, None


def validate_obd_input(data):
    """
    Validate OBD-II sensor input payload.
    Returns (True, None) on success or (False, "error message") on failure.
    """
    for field in OBD_RANGES:
        # 1. Check presence
        if field not in data:
            return False, f"Missing field: {field}"

        value = data[field]

        # 2. Check numeric type
        if not isinstance(value, (int, float)):
            return False, f"{field} must be a number"

        # 3. Check range
        min_val, max_val = OBD_RANGES[field]
        if not (min_val <= value <= max_val):
            return False, f"{field} value out of valid range"

    return True, None
