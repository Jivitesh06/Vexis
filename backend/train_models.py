"""
Vexis ML Training Script
Generates synthetic OBD data and trains 5 Isolation Forest models
with calibrated scoring bounds for accurate health prediction.

Run from: d:\Website\vexis\backend\
    python train_models.py
"""

import numpy as np
import pandas as pd
import pickle
import json
import os
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

SEED = 42
np.random.seed(SEED)

MODELS_PATH = os.path.join(os.path.dirname(__file__), 'models_pkl')
os.makedirs(MODELS_PATH, exist_ok=True)

# ──────────────────────────────────────────────────────────────────
# 1. Synthetic Data Generator
# ──────────────────────────────────────────────────────────────────

def generate_healthy_data(n=8000):
    """
    Realistic OBD readings for a healthy, well-maintained vehicle.
    Mix of city, highway, and idle conditions.
    """
    samples = []
    for _ in range(n):
        # Random driving mode
        mode = np.random.choice(['idle', 'city', 'highway', 'sport'], p=[0.15, 0.45, 0.30, 0.10])

        if mode == 'idle':
            rpm   = np.random.normal(800,  80);   rpm   = np.clip(rpm, 600, 1100)
            speed = np.random.normal(0,    5);    speed = np.clip(speed, 0, 10)
            load  = np.random.normal(25,   5);    load  = np.clip(load, 15, 35)
            maf   = np.random.normal(2.5,  0.5);  maf   = np.clip(maf, 1.0, 4.5)
            coolant_temp = np.random.normal(87, 3)

        elif mode == 'city':
            rpm   = np.random.normal(1600, 300);  rpm   = np.clip(rpm, 800, 2800)
            speed = np.random.normal(35,   15);   speed = np.clip(speed, 5, 70)
            load  = np.random.normal(40,   10);   load  = np.clip(load, 20, 65)
            maf   = np.random.normal(8.0,  2.5);  maf   = np.clip(maf, 2.0, 15.0)
            coolant_temp = np.random.normal(89, 3)

        elif mode == 'highway':
            rpm   = np.random.normal(2200, 300);  rpm   = np.clip(rpm, 1500, 3000)
            speed = np.random.normal(90,   15);   speed = np.clip(speed, 60, 130)
            load  = np.random.normal(55,   10);   load  = np.clip(load, 30, 75)
            maf   = np.random.normal(14.0, 3.0);  maf   = np.clip(maf, 6.0, 22.0)
            coolant_temp = np.random.normal(91, 3)

        else:  # sport
            rpm   = np.random.normal(3000, 400);  rpm   = np.clip(rpm, 2000, 4000)
            speed = np.random.normal(100,  20);   speed = np.clip(speed, 60, 150)
            load  = np.random.normal(75,   10);   load  = np.clip(load, 55, 90)
            maf   = np.random.normal(20.0, 4.0);  maf   = np.clip(maf, 10.0, 30.0)
            coolant_temp = np.random.normal(93, 3)

        # Healthy fuel trims: within ±5%
        stft = np.random.normal(0.5,  2.0); stft = np.clip(stft, -5.0, 5.0)
        ltft = np.random.normal(-0.5, 1.5); ltft = np.clip(ltft, -5.0, 5.0)
        intake_temp   = np.random.normal(35, 5); intake_temp = np.clip(intake_temp, 20, 55)
        throttle_pos  = load * 0.6 + np.random.normal(0, 3)

        samples.append({
            'rpm': rpm, 'speed': speed, 'load': load, 'coolant_temp': coolant_temp,
            'throttle_pos': throttle_pos, 'intake_temp': intake_temp,
            'maf': maf, 'stft': stft, 'ltft': ltft
        })

    return pd.DataFrame(samples)


def generate_unhealthy_data(n=2000):
    """
    OBD readings for a vehicle with various faults (used ONLY for calibration,
    NOT for training Isolation Forest since IF is unsupervised).
    """
    samples = []
    faults  = ['fuel_trim', 'overheating', 'maf_issue', 'engine_rough', 'aggressive']

    for _ in range(n):
        fault = np.random.choice(faults)

        if fault == 'fuel_trim':
            rpm   = np.random.normal(1500, 400)
            speed = np.random.normal(40,   20)
            load  = np.random.normal(45,   15)
            maf   = np.random.normal(9.0,  3.0)
            coolant_temp = np.random.normal(88, 5)
            stft  = np.random.choice([-1, 1]) * np.random.uniform(12, 25)  # extreme trim
            ltft  = np.random.choice([-1, 1]) * np.random.uniform(10, 20)

        elif fault == 'overheating':
            rpm   = np.random.normal(2000, 500)
            speed = np.random.normal(60,   25)
            load  = np.random.normal(70,   15)
            maf   = np.random.normal(14.0, 4.0)
            coolant_temp = np.random.uniform(105, 125)  # overheating
            stft  = np.random.normal(1,   3)
            ltft  = np.random.normal(-1,  3)

        elif fault == 'maf_issue':
            rpm   = np.random.normal(1800, 400)
            speed = np.random.normal(50,   20)
            load  = np.random.normal(60,   10)
            maf   = np.random.uniform(0.1, 1.5)  # very low MAF (clogged sensor/filter)
            coolant_temp = np.random.normal(89, 5)
            stft  = np.random.normal(15,  5)     # compensating fuel trim
            ltft  = np.random.normal(12,  4)

        elif fault == 'engine_rough':
            rpm   = np.random.uniform(400, 700)  # rough idle
            speed = np.random.normal(5,   10)
            load  = np.random.normal(35,   8)
            maf   = np.random.normal(3.5,  2.0)
            coolant_temp = np.random.normal(86, 5)
            stft  = np.random.normal(8,   5)
            ltft  = np.random.normal(-8,  5)

        else:  # aggressive
            rpm   = np.random.uniform(4000, 6000)
            speed = np.random.uniform(140, 220)   # severe overspeeding
            load  = np.random.uniform(85, 100)
            maf   = np.random.uniform(25, 45)
            coolant_temp = np.random.normal(97, 5)
            stft  = np.random.normal(-3,  3)
            ltft  = np.random.normal(-5,  3)

        rpm   = max(100, rpm)
        speed = max(0, speed)
        load  = np.clip(load, 5, 100)
        intake_temp  = np.random.normal(38, 8)
        throttle_pos = load * 0.6

        samples.append({
            'rpm': rpm, 'speed': speed, 'load': load, 'coolant_temp': coolant_temp,
            'throttle_pos': throttle_pos, 'intake_temp': intake_temp,
            'maf': maf, 'stft': stft, 'ltft': ltft
        })

    return pd.DataFrame(samples)


# ──────────────────────────────────────────────────────────────────
# 2. Feature Engineering
# ──────────────────────────────────────────────────────────────────

def compute_features(df):
    df = df.copy()
    df['rpm']   = df['rpm'].clip(lower=1)
    df['speed'] = df['speed'].clip(lower=0)
    df['load']  = df['load'].clip(lower=1)

    # Use coolant_temp as oat proxy
    df['oat']         = df.get('oat', df['coolant_temp'])
    df['speed_limit'] = 60.0

    df['maf_per_rpm']           = df['maf'] / df['rpm']
    df['rpm_load_ratio']        = df['rpm'] / df['load']
    df['maf_per_speed']         = df['maf'] / df['speed'].replace(0, np.nan).fillna(1)
    df['load_per_speed']        = df['load'] / df['speed'].replace(0, np.nan).fillna(1)
    df['maf_speed_deviation']   = (df['maf_per_speed'] - df['maf_per_rpm']).abs()
    df['fuel_trim_combined']    = df['stft'] + df['ltft']
    df['fuel_trim_abs']         = df['stft'].abs() + df['ltft'].abs()
    df['speed_excess']          = (df['speed'] - df['speed_limit']).clip(lower=0)
    df['is_overspeeding']       = (df['speed'] > df['speed_limit']).astype(int)
    df['thermal_stress']        = df['oat'] * (df['load'] / 100.0)
    df['maf_temp_adjusted']     = df['maf'] * (1 + df['oat'] / 100.0)
    df['gradient_speed_stress'] = (df['rpm'] / 1000.0) * (df['speed'] / 100.0)

    return df.fillna(0).replace([np.inf, -np.inf], 0)


# ──────────────────────────────────────────────────────────────────
# 3. Feature Subsets per Component
# ──────────────────────────────────────────────────────────────────

COMPONENT_FEATURES = {
    'engine':     ['rpm', 'load', 'maf_per_rpm', 'rpm_load_ratio', 'maf'],
    'fuel':       ['stft', 'ltft', 'fuel_trim_combined', 'fuel_trim_abs'],
    'efficiency': ['maf_per_rpm', 'maf_per_speed', 'load_per_speed', 'maf_speed_deviation'],
    'driving':    ['speed', 'speed_limit', 'speed_excess', 'is_overspeeding',
                   'rpm', 'gradient_speed_stress'],
    'thermal':    ['oat', 'thermal_stress', 'maf_temp_adjusted', 'load'],
}


# ──────────────────────────────────────────────────────────────────
# 4. Train + Calibrate
# ──────────────────────────────────────────────────────────────────

def train_and_calibrate():
    print("Generating training data...")
    healthy   = generate_healthy_data(n=8000)
    unhealthy = generate_unhealthy_data(n=2000)

    print("Computing features...")
    h_feat = compute_features(healthy)
    u_feat = compute_features(unhealthy)

    calibration_bounds = {}

    for comp, feature_cols in COMPONENT_FEATURES.items():
        print(f"\n--- Training {comp} model ---")

        # Training uses ONLY healthy data (unsupervised Isolation Forest)
        X_train = h_feat[feature_cols].values

        # Scale
        scaler  = StandardScaler()
        X_scaled = scaler.fit_transform(X_train)

        # Train Isolation Forest
        # contamination=0.05 means ~5% of training data is expected as anomalies
        clf = IsolationForest(
            n_estimators=200,
            max_samples='auto',
            contamination=0.05,
            max_features=1.0,
            random_state=SEED,
            n_jobs=-1
        )
        clf.fit(X_scaled)

        # ── Calibrate bounds using healthy + unhealthy ────────────
        X_h = scaler.transform(h_feat[feature_cols].values)
        X_u = scaler.transform(u_feat[feature_cols].values)

        scores_healthy   = clf.decision_function(X_h)
        scores_unhealthy = clf.decision_function(X_u)

        # Use 5th percentile of healthy as lower bound (near-normal but not worst)
        # Use 95th percentile of healthy as upper bound (most normal)
        # Use 5th percentile of unhealthy to set what "bad" looks like
        p5_healthy  = float(np.percentile(scores_healthy, 5))
        p95_healthy = float(np.percentile(scores_healthy, 95))
        p5_unhealthy = float(np.percentile(scores_unhealthy, 5))

        # lower_bound: where score maps to 0 (clearly anomalous)
        lower_bound = min(p5_unhealthy, p5_healthy - 0.05)
        # upper_bound: where score maps to 100 (peak health)
        upper_bound = p95_healthy

        # Ensure a minimum range to avoid division by zero
        if upper_bound - lower_bound < 0.01:
            lower_bound = upper_bound - 0.15

        calibration_bounds[comp] = {
            'lower': lower_bound,
            'upper': upper_bound
        }

        # Diagnostic
        h_mapped   = np.clip((scores_healthy   - lower_bound) / (upper_bound - lower_bound), 0, 1) * 100
        u_mapped   = np.clip((scores_unhealthy - lower_bound) / (upper_bound - lower_bound), 0, 1) * 100
        print(f"  Healthy scores:   mean={h_mapped.mean():.1f}  min={h_mapped.min():.1f}  max={h_mapped.max():.1f}")
        print(f"  Unhealthy scores: mean={u_mapped.mean():.1f}  min={u_mapped.min():.1f}  max={u_mapped.max():.1f}")
        print(f"  Calibration: lower={lower_bound:.4f}  upper={upper_bound:.4f}")

        # Save model and scaler
        model_path  = os.path.join(MODELS_PATH, f'if_{comp}.pkl')
        scaler_path = os.path.join(MODELS_PATH, f'scaler_{comp}.pkl')
        with open(model_path,  'wb') as f: pickle.dump(clf,    f)
        with open(scaler_path, 'wb') as f: pickle.dump(scaler, f)
        print(f"  Saved {model_path}")
        print(f"  Saved {scaler_path}")

    # Save calibration bounds
    bounds_path = os.path.join(MODELS_PATH, 'calibration_bounds.json')
    with open(bounds_path, 'w') as f:
        json.dump(calibration_bounds, f, indent=2)
    print(f"\nSaved calibration bounds: {bounds_path}")

    return calibration_bounds


# ──────────────────────────────────────────────────────────────────
# 5. Verify on the mock CSV
# ──────────────────────────────────────────────────────────────────

def verify_on_csv(calibration_bounds):
    print("\n" + "="*60)
    print("VERIFICATION on vexis_obd.csv (200 mock rows)")
    print("="*60)

    # Reload saved models
    MODELS = {}
    for comp in COMPONENT_FEATURES:
        with open(os.path.join(MODELS_PATH, f'if_{comp}.pkl'),     'rb') as f: MODELS[comp] = pickle.load(f)
        with open(os.path.join(MODELS_PATH, f'scaler_{comp}.pkl'), 'rb') as f: MODELS[f'scaler_{comp}'] = pickle.load(f)

    csv_path = os.path.join(os.path.dirname(__file__), '..', 'outputs', 'vexis_obd.csv')
    if not os.path.exists(csv_path):
        print("  CSV file not found, skipping verification.")
        return

    df = pd.read_csv(csv_path).fillna(0)
    feat_df = compute_features(df)

    COMPONENT_WEIGHTS = {'engine': 0.30, 'fuel': 0.25, 'efficiency': 0.20, 'driving': 0.15, 'thermal': 0.10}

    all_scores = []
    for idx in range(len(feat_df)):
        row = feat_df.iloc[idx]
        comp_scores = {}
        for comp, feature_cols in COMPONENT_FEATURES.items():
            vals   = row[feature_cols].values.reshape(1, -1)
            scaled = MODELS[f'scaler_{comp}'].transform(vals)
            raw    = MODELS[comp].decision_function(scaled)[0]
            lo, hi = calibration_bounds[comp]['lower'], calibration_bounds[comp]['upper']
            score  = float(np.clip((raw - lo) / (hi - lo) * 100, 0, 100))
            comp_scores[comp] = score

        overall = sum(COMPONENT_WEIGHTS[c] * comp_scores[c] for c in COMPONENT_WEIGHTS)
        all_scores.append({'overall': overall, **comp_scores})

    result_df = pd.DataFrame(all_scores)
    print(f"\n{'Component':<14} {'Mean':>8} {'Min':>8} {'Max':>8} {'Std':>8}")
    print("-" * 50)
    for col in ['engine', 'fuel', 'efficiency', 'driving', 'thermal', 'overall']:
        s = result_df[col]
        print(f"{col:<14} {s.mean():>8.1f} {s.min():>8.1f} {s.max():>8.1f} {s.std():>8.1f}")

    overall = result_df['overall']
    print(f"\nHealth Distribution:")
    print(f"  Excellent (>=90): {(overall>=90).sum()} rows")
    print(f"  Good      (>=75): {((overall>=75)&(overall<90)).sum()} rows")
    print(f"  Fair      (>=60): {((overall>=60)&(overall<75)).sum()} rows")
    print(f"  Poor      (>=40): {((overall>=40)&(overall<60)).sum()} rows")
    print(f"  Critical  ( <40): {(overall<40).sum()} rows")
    print(f"\nMedian overall score: {overall.median():.1f}")


if __name__ == '__main__':
    print("="*60)
    print("VEXIS ML TRAINING — Isolation Forest Models")
    print("="*60)
    bounds = train_and_calibrate()
    verify_on_csv(bounds)
    print("\n✅ Training complete! Models saved to models_pkl/")
