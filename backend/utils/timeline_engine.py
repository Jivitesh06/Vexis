"""
Vexis Smart Timeline Engine
Industry-grade logic to compute repair urgency, fault deadlines,
trend direction, and adaptive email schedule per vehicle.
"""
from datetime import datetime, timedelta


# ── Tier Definitions ──────────────────────────────────────────────────────
TIERS = {
    'CRITICAL':  {'freq_days': 1,  'repair_days': 2,  'label': 'CRITICAL ALERT'},
    'POOR':      {'freq_days': 3,  'repair_days': 7,  'label': 'URGENT SERVICE'},
    'FAIR':      {'freq_days': 7,  'repair_days': 21, 'label': 'SERVICE REQUIRED'},
    'GOOD':      {'freq_days': 14, 'repair_days': 45, 'label': 'SCHEDULED MAINTENANCE'},
    'EXCELLENT': {'freq_days': 30, 'repair_days': 90, 'label': 'ROUTINE CHECK'},
}

FAULT_PRIORITY = {
    'URGENT':  {'min_pct': 70, 'repair_days': 7,  'label': 'URGENT',  'color': '#ef4444'},
    'HIGH':    {'min_pct': 40, 'repair_days': 14, 'label': 'HIGH',    'color': '#f97316'},
    'MONITOR': {'min_pct': 10, 'repair_days': 30, 'label': 'MONITOR', 'color': '#fbbf24'},
    'LOW':     {'min_pct': 0,  'repair_days': 90, 'label': 'LOW',     'color': '#22c55e'},
}


def get_tier(score: float) -> str:
    if score < 40:  return 'CRITICAL'
    if score < 60:  return 'POOR'
    if score < 75:  return 'FAIR'
    if score < 90:  return 'GOOD'
    return 'EXCELLENT'


def get_fault_priority(pct: float) -> dict:
    """Return priority meta for a fault based on its occurrence frequency."""
    for name, meta in FAULT_PRIORITY.items():
        if pct >= meta['min_pct']:
            return {'name': name, **meta}
    return {'name': 'LOW', **FAULT_PRIORITY['LOW']}


def compute_trend(report_history: list) -> dict:
    """
    Given a list of past overall_scores (oldest→newest),
    determine if health is improving, stable, or declining.
    Returns: {'direction': 'declining'|'stable'|'improving', 'delta': float}
    """
    if not report_history or len(report_history) < 2:
        return {'direction': 'stable', 'delta': 0.0}

    scores = [r.get('overall_score', 50) for r in report_history]
    # Use last 3 max
    recent = scores[-3:]
    first, last = recent[0], recent[-1]
    delta = round(last - first, 1)

    if delta <= -5:
        direction = 'declining'
    elif delta >= 5:
        direction = 'improving'
    else:
        direction = 'stable'

    return {'direction': direction, 'delta': delta}


def generate_timeline(
    overall_score: float,
    engine_score: float,
    fuel_score: float,
    efficiency_score: float,
    driving_score: float,
    thermal_score: float,
    persist_issues: list,
    issue_counts: dict,
    n_results: int,
    report_history: list = None,
) -> dict:
    """
    Master timeline generator.
    Returns a full timeline dict to be stored in Firestore
    and used for email scheduling.
    """
    now = datetime.utcnow()
    tier_name = get_tier(overall_score)
    tier = TIERS[tier_name]

    # Escalate tier if score is declining over last 2 reports
    trend = compute_trend(report_history or [])
    effective_tier = tier_name
    if trend['direction'] == 'declining':
        tier_order = ['EXCELLENT', 'GOOD', 'FAIR', 'POOR', 'CRITICAL']
        idx = tier_order.index(tier_name)
        if idx < len(tier_order) - 1:
            effective_tier = tier_order[idx + 1]  # Escalate by 1 level
            tier = TIERS[effective_tier]

    # Next notification date
    next_notification = now + timedelta(days=tier['freq_days'])

    # Per-fault deadlines
    fault_timelines = []
    for issue in persist_issues:
        cnt = issue_counts.get(issue, 0)
        pct = round(cnt / n_results * 100) if n_results else 0
        priority = get_fault_priority(pct)
        deadline = now + timedelta(days=priority['repair_days'])
        fault_timelines.append({
            'issue':        issue,
            'frequency_pct': pct,
            'priority':     priority['name'],
            'priority_label': priority['label'],
            'color':        priority['color'],
            'repair_by':    deadline.strftime('%d %b %Y'),
            'repair_by_ts': deadline.isoformat(),
            'days_remaining': priority['repair_days'],
        })

    # Sort: most urgent first
    fault_timelines.sort(key=lambda x: x['frequency_pct'], reverse=True)

    # Component risk flags
    component_risks = []
    components = {
        'Engine':     engine_score,
        'Fuel System': fuel_score,
        'Efficiency': efficiency_score,
        'Driving':    driving_score,
        'Thermal':    thermal_score,
    }
    for comp, score in components.items():
        comp_tier = get_tier(score)
        if comp_tier in ('CRITICAL', 'POOR'):
            component_risks.append({
                'component': comp,
                'score': score,
                'tier': comp_tier,
                'action': f'Immediate inspection required for {comp}.'
                          if comp_tier == 'CRITICAL'
                          else f'Service {comp} within 7 days.',
            })

    return {
        'generated_at':       now.isoformat(),
        'overall_score':      overall_score,
        'tier':               effective_tier,
        'tier_label':         TIERS[effective_tier]['label'],
        'trend':              trend,
        'next_notification':  next_notification.isoformat(),
        'email_freq_days':    tier['freq_days'],
        'fault_timelines':    fault_timelines,
        'component_risks':    component_risks,
        'active':             True,
    }
