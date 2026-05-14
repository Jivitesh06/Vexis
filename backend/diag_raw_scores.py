import sys, os
sys.path.insert(0, '.')
import pickle, numpy as np, pandas as pd
from config import Config

# Load models manually
models_path = Config.ML_MODELS_PATH
components = ['engine', 'fuel', 'efficiency', 'driving', 'thermal']
MODELS = {}
for comp in components:
    try:
        with open(os.path.join(models_path, f'if_{comp}.pkl'), 'rb') as f:
            MODELS[comp] = pickle.load(f)
        with open(os.path.join(models_path, f'scaler_{comp}.pkl'), 'rb') as f:
            MODELS[f'scaler_{comp}'] = pickle.load(f)
        print(f'Loaded {comp}')
    except Exception as e:
        print(f'FAILED {comp}: {e}')

# Feature sets
COMPONENT_FEATURES = {
    'engine':     ['rpm', 'load', 'maf_per_rpm', 'rpm_load_ratio', 'maf'],
    'fuel':       ['stft', 'ltft', 'fuel_trim_combined', 'fuel_trim_abs'],
    'efficiency': ['maf_per_rpm', 'maf_per_speed', 'load_per_speed', 'maf_speed_deviation'],
    'driving':    ['speed', 'speed_limit', 'speed_excess', 'is_overspeeding', 'rpm', 'gradient_speed_stress'],
    'thermal':    ['oat', 'thermal_stress', 'maf_temp_adjusted', 'load'],
}

# Run ONE row through the models and print RAW decision_function output
test_row = {
    'rpm': 1800, 'speed': 45, 'load': 42, 'maf': 8.5, 'stft': 1.2, 'ltft': -0.8,
    'oat': 87, 'speed_limit': 60,
    'maf_per_rpm': 8.5/1800, 'rpm_load_ratio': 1800/42, 'maf_per_speed': 8.5/45,
    'load_per_speed': 42/45, 'maf_speed_deviation': abs(8.5/45 - 8.5/1800),
    'fuel_trim_combined': 1.2-0.8, 'fuel_trim_abs': 1.2+0.8,
    'speed_excess': 0, 'is_overspeeding': 0,
    'thermal_stress': 87*0.42, 'maf_temp_adjusted': 8.5*(1+87/100),
    'gradient_speed_stress': (1800/1000)*(45/100)
}

print()
print('=== RAW decision_function output per component ===')
for comp, feats in COMPONENT_FEATURES.items():
    if comp not in MODELS:
        print(f'{comp}: MODEL NOT LOADED')
        continue
    row = {col: test_row.get(col, 0.0) for col in feats}
    df = pd.DataFrame([row], columns=feats).fillna(0.0)
    scaled = MODELS[f'scaler_{comp}'].transform(df)
    raw = MODELS[comp].decision_function(scaled)
    print(f'{comp:12s}: raw_score={raw[0]:.6f}  shape={raw.shape}')

# Now run ALL 200 rows to find the actual min/max range
print()
print('=== decision_function range across all 200 rows ===')
df_csv = pd.read_csv('../outputs/vexis_obd.csv').fillna(0)

for comp, feats in COMPONENT_FEATURES.items():
    if comp not in MODELS:
        continue
    all_raw = []
    for _, row_data in df_csv.iterrows():
        row_dict = row_data.to_dict()
        rpm = row_dict.get('rpm', 0) or 1
        speed = row_dict.get('speed', 0) or 1
        load = row_dict.get('load', 0) or 1
        maf = row_dict.get('maf', 0)
        stft = row_dict.get('stft', 0)
        ltft = row_dict.get('ltft', 0)
        oat = row_dict.get('coolant_temp', 87)

        features = {
            'rpm': rpm, 'speed': speed, 'load': load, 'maf': maf,
            'stft': stft, 'ltft': ltft, 'oat': oat, 'speed_limit': 60,
            'maf_per_rpm': maf/rpm, 'rpm_load_ratio': rpm/load,
            'maf_per_speed': maf/speed if speed > 0 else 0,
            'load_per_speed': load/speed if speed > 0 else 0,
            'maf_speed_deviation': abs(maf/speed - maf/rpm) if speed > 0 else 0,
            'fuel_trim_combined': stft+ltft, 'fuel_trim_abs': abs(stft)+abs(ltft),
            'speed_excess': max(0, speed-60), 'is_overspeeding': 1 if speed > 60 else 0,
            'thermal_stress': oat*(load/100), 'maf_temp_adjusted': maf*(1+oat/100),
            'gradient_speed_stress': (rpm/1000)*(speed/100)
        }
        row_feats = {col: features.get(col, 0.0) for col in feats}
        df_row = pd.DataFrame([row_feats], columns=feats).fillna(0.0)
        scaled = MODELS[f'scaler_{comp}'].transform(df_row)
        raw = MODELS[comp].decision_function(scaled)
        all_raw.append(raw[0])

    arr = np.array(all_raw)
    print(f'{comp:12s}: min={arr.min():.4f}  max={arr.max():.4f}  mean={arr.mean():.4f}  std={arr.std():.4f}')
