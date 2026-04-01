"""
obd_simulator.py — Realistic OBD-II data simulator using sine waves.
Used when no real ELM327 USB scanner is detected.
All output keys match exactly what the real obd_reader produces.
"""
import random
import time
import math


def simulate_obd_data(t=None):
    """
    Generate one frame of realistic OBD sensor readings using sine-wave
    variation so values change smoothly over time (like a real vehicle).

    Returns a dict with all raw sensor values + derived ML features.
    """
    if t is None:
        t = time.time()

    # ── Core sensor values (sine-wave driven) ─────────────────────
    rpm          = round(800  + 1200 * abs(math.sin(t * 0.10)), 1)
    speed        = round(40   + 30   * abs(math.sin(t * 0.05)), 1)
    load         = round(30   + 25   * abs(math.sin(t * 0.08)), 1)
    maf          = round(5    + 8    * abs(math.sin(t * 0.10)), 2)
    stft         = round(2    *       math.sin(t * 0.30),       2)
    ltft         = round(1.5  *       math.sin(t * 0.20),       2)
    oat          = round(75   + 10   * math.sin(t * 0.02),      1)
    coolant_temp = oat   # use same as ambient for simulation
    throttle_pos = round(10   + (load / 100) * 60,              1)
    intake_temp  = round(30   + 5    * math.sin(t * 0.04),      1)
    fuel_level   = round(max(0, 60   + 5 * math.sin(t * 0.001)), 1)
    o2_voltage   = round(0.45 + 0.4  * abs(math.sin(t * 0.25)), 3)
    speed_limit  = 60

    # ── Derived features (mirrors compute_derived_features) ────────
    maf_per_rpm           = round(maf / rpm   if rpm   > 0 else 0, 4)
    rpm_load_ratio        = round(rpm / load  if load  > 0 else 0, 2)
    maf_per_speed         = round(maf / speed if speed > 0 else 0, 4)
    load_per_speed        = round(load / speed if speed > 0 else 0, 4)
    maf_speed_deviation   = round(abs(maf_per_speed - maf_per_rpm),  4)
    fuel_trim_combined    = round(stft + ltft,              2)
    fuel_trim_abs         = round(abs(stft) + abs(ltft),   2)
    speed_excess          = round(max(0.0, speed - speed_limit), 1)
    is_overspeeding       = 1 if speed > speed_limit else 0
    thermal_stress        = round(oat * (load / 100.0),    2)
    maf_temp_adjusted     = round(maf * (1 + oat / 100.0), 3)
    gradient_speed_stress = round((rpm / 1000.0) * (speed / 100.0), 3)

    return {
        # Raw OBD readings
        'rpm':                  rpm,
        'speed':                speed,
        'load':                 load,
        'maf':                  maf,
        'stft':                 stft,
        'ltft':                 ltft,
        'oat':                  oat,
        'coolant_temp':         coolant_temp,
        'throttle_pos':         throttle_pos,
        'intake_temp':          intake_temp,
        'fuel_level':           fuel_level,
        'o2_voltage':           o2_voltage,
        'speed_limit':          speed_limit,
        # Derived ML features
        'maf_per_rpm':          maf_per_rpm,
        'rpm_load_ratio':       rpm_load_ratio,
        'maf_per_speed':        maf_per_speed,
        'load_per_speed':       load_per_speed,
        'maf_speed_deviation':  maf_speed_deviation,
        'fuel_trim_combined':   fuel_trim_combined,
        'fuel_trim_abs':        fuel_trim_abs,
        'speed_excess':         speed_excess,
        'is_overspeeding':      is_overspeeding,
        'thermal_stress':       thermal_stress,
        'maf_temp_adjusted':    maf_temp_adjusted,
        'gradient_speed_stress': gradient_speed_stress,
    }
