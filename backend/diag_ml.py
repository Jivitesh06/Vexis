import sys
sys.path.insert(0, '.')
import pandas as pd, statistics
from ml.model_loader import load_models, predict_health

print("Loading models...")
load_models()

df = pd.read_csv('../outputs/vexis_obd.csv').fillna(0)
rows = df.to_dict(orient='records')

print('\n=== First 5 predictions ===')
for i, row in enumerate(rows[:5]):
    r = predict_health(row)
    ov = r.get('overall_score')
    en = r.get('engine_score')
    fu = r.get('fuel_score')
    dr = r.get('driving_score')
    th = r.get('thermal_score')
    cat = r.get('health_category')
    iss = r.get('issues', [])
    print(f'Row {i+1}: overall={ov} engine={en} fuel={fu} driving={dr} thermal={th} cat={cat}')
    print(f'         issues={iss}')

results = [predict_health(r) for r in rows]
valid = [r for r in results if 'error' not in r]
overall_scores = [r['overall_score'] for r in valid]
print(f'\n=== AGGREGATE ({len(valid)} rows) ===')
print(f'Median: {statistics.median(overall_scores):.1f}')
print(f'Min:    {min(overall_scores):.1f}')
print(f'Max:    {max(overall_scores):.1f}')
print(f'Unique score count: {len(set(overall_scores))}')

from collections import Counter
cats = Counter(r['health_category'] for r in valid)
print(f'\nHealth distribution: {dict(cats)}')
