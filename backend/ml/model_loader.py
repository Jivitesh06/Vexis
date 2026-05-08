import pickle
import json
import numpy as np
import pandas as pd
import os
from config import Config

# ──────────────────────────────────────────────────────────────────
# Feature sets — exact column names used during training
# ──────────────────────────────────────────────────────────────────
COMPONENT_FEATURES = {
    'engine':     ['rpm', 'load', 'maf_per_rpm', 'rpm_load_ratio', 'maf'],
    'fuel':       ['stft', 'ltft', 'fuel_trim_combined', 'fuel_trim_abs'],
    'efficiency': ['maf_per_rpm', 'maf_per_speed', 'load_per_speed',
                   'maf_speed_deviation'],
    'driving':    ['speed', 'speed_limit', 'speed_excess', 'is_overspeeding',
                   'rpm', 'gradient_speed_stress'],
    'thermal':    ['oat', 'thermal_stress', 'maf_temp_adjusted', 'load']
}

# Component weights (must sum to 1.0)
COMPONENT_WEIGHTS = {
    'engine':     0.30,
    'fuel':       0.25,
    'efficiency': 0.20,
    'driving':    0.15,
    'thermal':    0.10
}

# Module-level registry — populated once at startup
MODELS = {}
CALIBRATION = {}   # {comp: {lower: float, upper: float}}


# ──────────────────────────────────────────────────────────────────
# FUNCTION 1 — load_models()
# ──────────────────────────────────────────────────────────────────
def load_models():
    """
    Load all 5 Isolation Forest models, scalers, and calibration bounds
    from models_pkl/. Called once at app startup.
    """
    components  = list(COMPONENT_FEATURES.keys())
    models_path = Config.ML_MODELS_PATH
    loaded      = 0

    for comp in components:
        model_path  = os.path.join(models_path, f'if_{comp}.pkl')
        scaler_path = os.path.join(models_path, f'scaler_{comp}.pkl')
        try:
            with open(model_path,  'rb') as f: MODELS[comp] = pickle.load(f)
            with open(scaler_path, 'rb') as f: MODELS[f'scaler_{comp}'] = pickle.load(f)
            print(f"  Loaded: if_{comp}.pkl + scaler_{comp}.pkl")
            loaded += 1
        except FileNotFoundError:
            print(f"  [WARNING] Model files not found for '{comp}' — skipping.")
        except Exception as e:
            print(f"  [WARNING] Failed to load '{comp}' models: {e}")

    # Load calibration bounds
    bounds_path = os.path.join(models_path, 'calibration_bounds.json')
    if os.path.exists(bounds_path):
        with open(bounds_path, 'r') as f:
            CALIBRATION.update(json.load(f))
        print(f"  Loaded calibration bounds for {len(CALIBRATION)} components.")
    else:
        print("  [WARNING] calibration_bounds.json not found — using fallback bounds.")
        # Fallback bounds (safe defaults based on typical IF ranges)
        for comp in components:
            CALIBRATION[comp] = {'lower': -0.15, 'upper': 0.20}

    print(f"\nVexis ML: {loaded}/{len(components)} component models loaded.")


# ──────────────────────────────────────────────────────────────────
# FUNCTION 2 — calibrated_score(raw, comp) → 0-100
# ──────────────────────────────────────────────────────────────────
def calibrated_score(raw_decision: float, comp: str) -> float:
    """
    Map a single Isolation Forest decision_function score to 0–100
    using pre-computed calibration bounds from training.

    Higher decision_function → more normal → higher health score.
    """
    bounds = CALIBRATION.get(comp, {'lower': -0.15, 'upper': 0.20})
    lo, hi = bounds['lower'], bounds['upper']
    span   = hi - lo
    if span < 1e-6:
        return 50.0
    score = (raw_decision - lo) / span * 100.0
    return float(np.clip(score, 0.0, 100.0))


# ──────────────────────────────────────────────────────────────────
# FUNCTION 3 — compute_derived_features(raw_input) → dict
# ──────────────────────────────────────────────────────────────────
def compute_derived_features(raw_input: dict) -> dict:
    """
    Compute all engineered features the models were trained on.

    Raw input keys expected:
        rpm, speed, load, maf, stft, ltft,
        oat (or coolant_temp), speed_limit
    """
    rpm         = float(raw_input.get('rpm',         0))
    speed       = float(raw_input.get('speed',       0))
    load        = float(raw_input.get('load',        0))
    maf         = float(raw_input.get('maf',         0))
    stft        = float(raw_input.get('stft',        0))
    ltft        = float(raw_input.get('ltft',        0))
    # Support both 'oat' and 'coolant_temp'
    oat         = float(raw_input.get('oat') or raw_input.get('coolant_temp') or 87)
    speed_limit = float(raw_input.get('speed_limit', 60))

    # Guard against division by zero
    rpm_safe   = max(rpm,   1.0)
    speed_safe = max(speed, 1.0)
    load_safe  = max(load,  1.0)

    maf_per_rpm           = maf / rpm_safe
    rpm_load_ratio        = rpm / load_safe
    maf_per_speed         = maf / speed_safe if speed > 0 else 0.0
    load_per_speed        = load / speed_safe if speed > 0 else 0.0
    maf_speed_deviation   = abs(maf_per_speed - maf_per_rpm)
    fuel_trim_combined    = stft + ltft
    fuel_trim_abs         = abs(stft) + abs(ltft)
    speed_excess          = max(0.0, speed - speed_limit)
    is_overspeeding       = 1 if speed > speed_limit else 0
    thermal_stress        = oat * (load / 100.0)
    maf_temp_adjusted     = maf * (1 + oat / 100.0)
    gradient_speed_stress = (rpm / 1000.0) * (speed / 100.0)

    return {
        'rpm':                  rpm,
        'speed':                speed,
        'load':                 load,
        'maf':                  maf,
        'stft':                 stft,
        'ltft':                 ltft,
        'oat':                  oat,
        'speed_limit':          speed_limit,
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


# ──────────────────────────────────────────────────────────────────
# FUNCTION 4 — predict_health(raw_input) → dict
# ──────────────────────────────────────────────────────────────────
def predict_health(raw_input: dict) -> dict:
    """
    Run all 5 Isolation Forest models on a single OBD reading.

    Uses calibrated bounds (not min/max normalization) so every
    single-row prediction is meaningful without batch context.

    Returns a dict with component scores, overall score, health
    category, and detected issues — or {"error": str} on failure.
    """
    try:
        full_features = compute_derived_features(raw_input)

        component_scores = {}

        for comp, feature_cols in COMPONENT_FEATURES.items():
            if comp not in MODELS or f'scaler_{comp}' not in MODELS:
                component_scores[comp] = 50.0   # model not loaded — neutral
                continue

            # Build 1-row DataFrame with exact feature order
            row = {col: full_features.get(col, 0.0) for col in feature_cols}
            df  = pd.DataFrame([row], columns=feature_cols).fillna(0.0)

            # Scale → predict (use .values to avoid sklearn feature-name warning)
            scaled    = MODELS[f'scaler_{comp}'].transform(df.values)
            raw_score = float(MODELS[comp].decision_function(scaled)[0])

            # Map to 0-100 using calibrated bounds (fixes the 50.0 bug)
            component_scores[comp] = calibrated_score(raw_score, comp)

        # Weighted overall score
        overall_score = sum(
            COMPONENT_WEIGHTS[c] * component_scores[c]
            for c in COMPONENT_WEIGHTS
        )
        overall_score = round(float(np.clip(overall_score, 0, 100)), 2)

        # Health category
        if overall_score >= 90:   health_category = "Excellent"
        elif overall_score >= 75: health_category = "Good"
        elif overall_score >= 60: health_category = "Fair"
        elif overall_score >= 40: health_category = "Poor"
        else:                     health_category = "Critical"

        # Issue detection (rule-based on component scores)
        issues = []
        if component_scores.get('engine',     100) < 60: issues.append("Engine anomaly detected")
        if component_scores.get('fuel',       100) < 60: issues.append("Fuel system irregularity")
        if component_scores.get('efficiency', 100) < 60: issues.append("Efficiency degradation")
        if component_scores.get('driving',    100) < 60: issues.append("Aggressive driving patterns")
        if component_scores.get('thermal',    100) < 60: issues.append("Thermal stress detected")

        stft = float(raw_input.get('stft', 0))
        ltft = float(raw_input.get('ltft', 0))
        if not (-10 <= stft <= 10) or not (-10 <= ltft <= 10):
            issues.append("Fuel trim imbalance")

        oat = float(raw_input.get('oat') or raw_input.get('coolant_temp') or 0)
        if oat > 100:
            issues.append("High coolant temperature")

        return {
            "engine_score":      round(component_scores.get('engine',     50.0), 2),
            "fuel_score":        round(component_scores.get('fuel',       50.0), 2),
            "efficiency_score":  round(component_scores.get('efficiency', 50.0), 2),
            "driving_score":     round(component_scores.get('driving',    50.0), 2),
            "thermal_score":     round(component_scores.get('thermal',    50.0), 2),
            "overall_score":     overall_score,
            "health_category":   health_category,
            "issues":            issues,
            "component_weights": COMPONENT_WEIGHTS
        }

    except Exception as e:
        return {"error": str(e)}
