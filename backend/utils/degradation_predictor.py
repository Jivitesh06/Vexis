"""
Vexis Degradation Predictor
Uses score-velocity regression (rate of change over time) to predict EXACTLY
when a vehicle's health will hit POOR (60) and CRITICAL (40) thresholds.

No training required — works from first report, gets smarter with each scan.
"""
from datetime import datetime, timedelta
from typing import Optional


# ── Thresholds ──────────────────────────────────────────────────────────────
POOR_THRESHOLD     = 60.0
CRITICAL_THRESHOLD = 40.0
MAX_FORECAST_DAYS  = 365  # Don't predict more than 1 year out


def _parse_ts(ts: str) -> Optional[datetime]:
    """Safely parse ISO timestamp string."""
    try:
        return datetime.fromisoformat(ts.replace('Z', '+00:00').replace('+00:00', ''))
    except Exception:
        return None


def predict_degradation(report_history: list) -> dict:
    """
    Given a list of report dicts (from Firestore, newest first),
    compute the score velocity and predict when score hits POOR / CRITICAL.

    Each report dict must have:
      - 'overall_score' (float)
      - 'timestamp' (ISO string)

    Returns a dict with:
      - days_until_poor      (int | None)
      - days_until_critical  (int | None)
      - predicted_poor_date  (str | None)  — 'DD Mon YYYY'
      - predicted_critical_date (str | None)
      - velocity             (float)  — points per day (negative = declining)
      - confidence           (str)    — 'HIGH' | 'MEDIUM' | 'LOW' | 'INSUFFICIENT'
      - current_score        (float)
      - trend                (str)    — 'declining' | 'stable' | 'improving'
    """
    now = datetime.utcnow()

    # Filter to valid reports with timestamps
    valid = []
    for r in report_history:
        score = r.get('overall_score')
        ts    = r.get('timestamp')
        if score is not None and ts:
            parsed = _parse_ts(ts)
            if parsed:
                valid.append((parsed, float(score)))

    # Sort oldest → newest
    valid.sort(key=lambda x: x[0])

    current_score = valid[-1][1] if valid else 75.0

    if len(valid) < 2:
        return {
            'current_score':          current_score,
            'velocity':               0.0,
            'days_until_poor':        None,
            'days_until_critical':    None,
            'predicted_poor_date':    None,
            'predicted_critical_date': None,
            'confidence':             'INSUFFICIENT',
            'trend':                  'stable',
            'needs_service_now':      current_score < POOR_THRESHOLD,
        }

    # ── Weighted Linear Regression (recent reports matter more) ──────────────
    # Use up to last 10 reports for regression
    window = valid[-10:]
    n      = len(window)

    # Convert timestamps to float (days since oldest point in window)
    t0     = window[0][0]
    xs     = [(r[0] - t0).total_seconds() / 86400.0 for r in window]
    ys     = [r[1] for r in window]

    # Weights: more recent = higher weight (exponential)
    weights = [1.5 ** i for i in range(n)]
    W       = sum(weights)

    # Weighted means
    x_bar = sum(w * x for w, x in zip(weights, xs)) / W
    y_bar = sum(w * y for w, y in zip(weights, ys)) / W

    # Weighted slope (velocity: score points per day)
    num   = sum(weights[i] * (xs[i] - x_bar) * (ys[i] - y_bar) for i in range(n))
    denom = sum(weights[i] * (xs[i] - x_bar) ** 2 for i in range(n))

    velocity = num / denom if denom != 0 else 0.0

    # ── Determine trend ──────────────────────────────────────────────────────
    if velocity <= -0.3:
        trend = 'declining'
    elif velocity >= 0.3:
        trend = 'improving'
    else:
        trend = 'stable'

    # ── Confidence level ─────────────────────────────────────────────────────
    span_days = (window[-1][0] - window[0][0]).total_seconds() / 86400.0
    if n >= 5 and span_days >= 14:
        confidence = 'HIGH'
    elif n >= 3 and span_days >= 3:
        confidence = 'MEDIUM'
    else:
        confidence = 'LOW'

    # ── Predict threshold crossing dates ────────────────────────────────────
    def _days_to_threshold(threshold: float) -> Optional[int]:
        if velocity >= 0:          # Not declining — won't hit threshold
            if current_score >= threshold:
                return None        # Already above, trending up
            # Score is below threshold but improving — already in danger
            return 0
        days = (current_score - threshold) / abs(velocity)
        if days < 0:               # Already past threshold
            return 0
        if days > MAX_FORECAST_DAYS:
            return None            # Too far out — not meaningful
        return int(round(days))

    def _date_str(days: Optional[int]) -> Optional[str]:
        if days is None:
            return None
        if days == 0:
            return 'Already reached'
        return (now + timedelta(days=days)).strftime('%d %b %Y')

    days_poor     = _days_to_threshold(POOR_THRESHOLD)
    days_critical = _days_to_threshold(CRITICAL_THRESHOLD)

    return {
        'current_score':           round(current_score, 1),
        'velocity':                round(velocity, 3),
        'days_until_poor':         days_poor,
        'days_until_critical':     days_critical,
        'predicted_poor_date':     _date_str(days_poor),
        'predicted_critical_date': _date_str(days_critical),
        'confidence':              confidence,
        'trend':                   trend,
        'needs_service_now':       current_score < POOR_THRESHOLD,
        'report_count':            len(valid),
    }


def service_recommendations(timeline: dict, prediction: dict) -> list:
    """
    Generate human-readable service action items combining fault timelines
    and degradation prediction.
    Returns list of dicts: {service, urgency, due_by, days_remaining, color}
    """
    recs  = []
    urgency_order = {'CRITICAL': 0, 'URGENT': 1, 'HIGH': 2, 'MEDIUM': 3, 'LOW': 4}

    # From fault timelines
    for fault in timeline.get('fault_timelines', []):
        recs.append({
            'service':       fault['issue'],
            'urgency':       fault['priority'],
            'due_by':        fault['repair_by'],
            'days_remaining': fault['days_remaining'],
            'color':         fault['color'],
            'source':        'diagnostic',
        })

    # From component risks
    for comp in timeline.get('component_risks', []):
        tier  = comp['tier']
        color = '#ef4444' if tier == 'CRITICAL' else '#f97316'
        days  = 2 if tier == 'CRITICAL' else 7
        recs.append({
            'service':       f"{comp['component']} Inspection",
            'urgency':       tier,
            'due_by':        (datetime.utcnow() + timedelta(days=days)).strftime('%d %b %Y'),
            'days_remaining': days,
            'color':         color,
            'source':        'component',
        })

    # From degradation prediction
    if prediction.get('trend') == 'declining' and prediction.get('days_until_poor') is not None:
        d = prediction['days_until_poor']
        if d <= 30:
            recs.append({
                'service':       'Full Vehicle Service (Predicted)',
                'urgency':       'URGENT' if d <= 7 else 'HIGH',
                'due_by':        prediction['predicted_poor_date'],
                'days_remaining': d,
                'color':         '#f97316',
                'source':        'prediction',
            })

    # Sort by urgency then days remaining
    recs.sort(key=lambda x: (urgency_order.get(x['urgency'], 9), x.get('days_remaining', 999)))

    # Deduplicate similar service items
    seen  = set()
    dedup = []
    for r in recs:
        key = r['service'][:30].lower()
        if key not in seen:
            seen.add(key)
            dedup.append(r)

    return dedup[:8]  # Max 8 recommendations
