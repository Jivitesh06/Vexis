import pickle
import numpy as np
import pandas as pd
import os
from config import Config

# ──────────────────────────────────────────────────────────────────
# Feature sets — exact column names used during training
# ──────────────────────────────────────────────────────────────────
COMPONENT_FEATURES = {
    'engine': [
        'rpm', 'load', 'maf_per_rpm', 'rpm_load_ratio', 'maf'
    ],
    'fuel': [
        'stft', 'ltft', 'fuel_trim_combined', 'fuel_trim_abs'
    ],
    'efficiency': [
        'maf_per_rpm', 'maf_per_speed', 'load_per_speed',
        'maf_speed_deviation'
    ],
    'driving': [
        'speed', 'speed_limit', 'speed_excess', 'is_overspeeding',
        'rpm', 'gradient_speed_stress'
    ],
    'thermal': [
        'oat', 'thermal_stress', 'maf_temp_adjusted', 'load'
    ]
}

# Component weights (must sum to 1.0)
COMPONENT_WEIGHTS = {
    'engine':     0.30,
    'fuel':       0.25,
    'efficiency': 0.20,
    'driving':    0.15,
    'thermal':    0.10
}

# Module-level model registry — loaded once at startup
MODELS = {}


# ──────────────────────────────────────────────────────────────────
# FUNCTION 1 — load_models()
# ──────────────────────────────────────────────────────────────────
def load_models():
    """
    Load all 5 Isolation Forest models and their paired scalers from
    the models_pkl/ directory.  Called once at app startup.
    """
    components = ['engine', 'fuel', 'efficiency', 'driving', 'thermal']
    models_path = Config.ML_MODELS_PATH
    loaded_count = 0

    for comp in components:
        model_path  = os.path.join(models_path, f'if_{comp}.pkl')
        scaler_path = os.path.join(models_path, f'scaler_{comp}.pkl')

        try:
            with open(model_path, 'rb') as f:
                MODELS[comp] = pickle.load(f)

            with open(scaler_path, 'rb') as f:
                MODELS[f'scaler_{comp}'] = pickle.load(f)

            print(f"  Loaded: if_{comp}.pkl + scaler_{comp}.pkl")
            loaded_count += 1

        except FileNotFoundError:
            print(f"  [WARNING] Model files not found for '{comp}' — skipping.")
        except Exception as e:
            print(f"  [WARNING] Failed to load '{comp}' models: {e} — skipping.")

    print(f"\nVexis ML: {loaded_count}/{len(components)} component models loaded successfully.")


# ──────────────────────────────────────────────────────────────────
# FUNCTION 2 — if_score_to_health(raw_scores)
# ──────────────────────────────────────────────────────────────────
def if_score_to_health(raw_scores):
    """
    Convert Isolation Forest decision_function output (array of 1 value)
    into a 0–100 health score using the same normalisation as training.

    Higher decision_function → more normal → higher health score.
    """
    min_s = raw_scores.min()
    max_s = raw_scores.max()

    if max_s == min_s:
        return 50.0  # flat / degenerate — return neutral score

    normalized = (raw_scores - min_s) / (max_s - min_s)
    return float(np.clip(normalized * 100, 0, 100)[0])


# ──────────────────────────────────────────────────────────────────
# FUNCTION 3 — compute_derived_features(raw_input) → dict
# ──────────────────────────────────────────────────────────────────
def compute_derived_features(raw_input: dict) -> dict:
    """
    Compute all engineered features the models were trained on.

    Raw input keys expected:
        rpm, speed, load, maf, stft, ltft, oat, speed_limit
    """
    rpm         = float(raw_input.get('rpm',         0))
    speed       = float(raw_input.get('speed',       0))
    load        = float(raw_input.get('load',        0))
    maf         = float(raw_input.get('maf',         0))
    stft        = float(raw_input.get('stft',        0))
    ltft        = float(raw_input.get('ltft',        0))
    oat         = float(raw_input.get('oat',         0))
    speed_limit = float(raw_input.get('speed_limit', 60))  # default 60 km/h

    # ── Derived features ──────────────────────────────────────────
    maf_per_rpm           = maf / rpm              if rpm   > 0 else 0.0
    rpm_load_ratio        = rpm / load             if load  > 0 else 0.0
    maf_per_speed         = maf / speed            if speed > 0 else 0.0
    load_per_speed        = load / speed           if speed > 0 else 0.0
    maf_speed_deviation   = abs(maf_per_speed - maf_per_rpm)
    fuel_trim_combined    = stft + ltft
    fuel_trim_abs         = abs(stft) + abs(ltft)
    speed_excess          = max(0.0, speed - speed_limit)
    is_overspeeding       = 1 if speed > speed_limit else 0
    thermal_stress        = oat * (load / 100.0)
    maf_temp_adjusted     = maf * (1 + oat / 100.0)
    gradient_speed_stress = (rpm / 1000.0) * (speed / 100.0)

    # ── Merge raw + derived ───────────────────────────────────────
    full = {
        # raw
        'rpm':                  rpm,
        'speed':                speed,
        'load':                 load,
        'maf':                  maf,
        'stft':                 stft,
        'ltft':                 ltft,
        'oat':                  oat,
        'speed_limit':          speed_limit,
        # derived
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
    return full


# ──────────────────────────────────────────────────────────────────
# FUNCTION 4 — predict_health(raw_input) → dict
# ──────────────────────────────────────────────────────────────────
def predict_health(raw_input: dict) -> dict:
    """
    Run all 5 Isolation Forest models on a single OBD reading and
    return component scores, overall score, health category, and issues.

    Args:
        raw_input: dict with keys rpm, speed, load, maf, stft, ltft,
                   oat, speed_limit

    Returns:
        dict with engine_score, fuel_score, efficiency_score,
        driving_score, thermal_score, overall_score, health_category,
        issues, component_weights  —  or {"error": str} on failure.
    """
    try:
        # ── Step 1: compute all features ─────────────────────────
        full_features = compute_derived_features(raw_input)

        # ── Step 2: score each component ─────────────────────────
        component_scores = {}

        for comp, feature_cols in COMPONENT_FEATURES.items():
            if comp not in MODELS or f'scaler_{comp}' not in MODELS:
                # Model not loaded — assign neutral score
                component_scores[comp] = 50.0
                continue

            # Extract only this component's columns into a 1-row DataFrame
            row = {col: full_features.get(col, 0.0) for col in feature_cols}
            df  = pd.DataFrame([row], columns=feature_cols)

            # Handle any NaN values
            df = df.fillna(0.0)

            # Scale
            scaled = MODELS[f'scaler_{comp}'].transform(df)

            # Isolation Forest anomaly score → health score
            raw_scores            = MODELS[comp].decision_function(scaled)
            component_scores[comp] = if_score_to_health(raw_scores)

        # ── Step 3: weighted overall score ───────────────────────
        overall_score = sum(
            COMPONENT_WEIGHTS[c] * component_scores[c]
            for c in COMPONENT_WEIGHTS
        )
        overall_score = round(float(np.clip(overall_score, 0, 100)), 2)

        # ── Step 4: health category ───────────────────────────────
        if overall_score >= 90:
            health_category = "Excellent"
        elif overall_score >= 75:
            health_category = "Good"
        elif overall_score >= 60:
            health_category = "Fair"
        elif overall_score >= 40:
            health_category = "Poor"
        else:
            health_category = "Critical"

        # ── Step 5: issue detection ───────────────────────────────
        issues = []

        if component_scores.get('engine', 100) < 60:
            issues.append("Engine anomaly detected")
        if component_scores.get('fuel', 100) < 60:
            issues.append("Fuel system irregularity")
        if component_scores.get('efficiency', 100) < 60:
            issues.append("Efficiency degradation")
        if component_scores.get('driving', 100) < 60:
            issues.append("Aggressive driving patterns")
        if component_scores.get('thermal', 100) < 60:
            issues.append("Thermal stress detected")

        stft = float(raw_input.get('stft', 0))
        ltft = float(raw_input.get('ltft', 0))
        if not (-10 <= stft <= 10) or not (-10 <= ltft <= 10):
            issues.append("Fuel trim imbalance")

        oat = float(raw_input.get('oat', 0))
        if oat > 90:
            issues.append("High coolant/ambient temperature")

        # ── Step 6: return result dict ────────────────────────────
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
