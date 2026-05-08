"""
Vexis Email Templates
Professional HTML email builder for vehicle health notifications.
"""
from datetime import datetime


def _tier_color(tier: str) -> str:
    return {
        'CRITICAL':  '#ef4444',
        'POOR':      '#f97316',
        'FAIR':      '#fbbf24',
        'GOOD':      '#22c55e',
        'EXCELLENT': '#22d3ee',
    }.get(tier, '#94a3b8')


def _trend_arrow(direction: str) -> str:
    return {
        'improving': '↑ Improving',
        'declining': '↓ Declining',
        'stable':    '→ Stable',
    }.get(direction, '→ Stable')


def _trend_color(direction: str) -> str:
    return {
        'improving': '#22c55e',
        'declining': '#ef4444',
        'stable':    '#fbbf24',
    }.get(direction, '#94a3b8')


def build_health_email(
    user_name: str,
    user_email: str,
    vehicle_name: str,
    vehicle_model: str,
    timeline: dict,
) -> dict:
    """
    Build a complete professional HTML email.
    Returns {'subject': str, 'html': str}
    """
    tier      = timeline.get('tier', 'GOOD')
    tier_lbl  = timeline.get('tier_label', 'ROUTINE CHECK')
    score     = timeline.get('overall_score', 0)
    trend     = timeline.get('trend', {'direction': 'stable', 'delta': 0})
    faults    = timeline.get('fault_timelines', [])
    comps     = timeline.get('component_risks', [])
    t_color   = _tier_color(tier)
    tr_arrow  = _trend_arrow(trend['direction'])
    tr_color  = _trend_color(trend['direction'])
    date_str  = datetime.utcnow().strftime('%d %b %Y')
    name      = user_name or user_email.split('@')[0].title()

    # Subject line
    subjects = {
        'CRITICAL':  f'🚨 CRITICAL ALERT — {vehicle_name} Requires Immediate Attention',
        'POOR':      f'⚠️ Urgent Service Needed — {vehicle_name} Health Report',
        'FAIR':      f'🔔 Service Reminder — {vehicle_name} Health Update',
        'GOOD':      f'✅ Vehicle Health Summary — {vehicle_name}',
        'EXCELLENT': f'🌟 Monthly Health Digest — {vehicle_name} is in great shape!',
    }
    subject = subjects.get(tier, f'Vehicle Health Update — {vehicle_name}')

    # Fault rows
    fault_rows = ''
    for f in faults[:5]:  # Show max 5
        pc = f['color']
        fault_rows += f"""
        <tr>
            <td style="padding:10px 16px;border-bottom:1px solid #e2e8f0;font-size:13px;color:#1e293b;">
                {f['issue']}
            </td>
            <td style="padding:10px 16px;border-bottom:1px solid #e2e8f0;text-align:center;">
                <span style="background:{pc}22;color:{pc};font-weight:700;font-size:12px;
                             padding:3px 10px;border-radius:999px;border:1px solid {pc};">
                    {f['priority_label']}
                </span>
            </td>
            <td style="padding:10px 16px;border-bottom:1px solid #e2e8f0;text-align:center;
                       font-size:13px;color:#ef4444;font-weight:700;">
                {f['repair_by']}
            </td>
        </tr>"""

    fault_section = ''
    if faults:
        fault_section = f"""
        <div style="margin-bottom:24px;">
            <h3 style="margin:0 0 12px;font-size:15px;font-weight:700;color:#0f172a;
                       text-transform:uppercase;letter-spacing:0.05em;">
                ⚡ Detected Issues &amp; Repair Deadlines
            </h3>
            <table width="100%" cellpadding="0" cellspacing="0"
                   style="border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;border-collapse:collapse;">
                <thead>
                    <tr style="background:#0f172a;">
                        <th style="padding:10px 16px;text-align:left;color:#e2e8f0;font-size:12px;font-weight:700;">ISSUE</th>
                        <th style="padding:10px 16px;text-align:center;color:#e2e8f0;font-size:12px;font-weight:700;">PRIORITY</th>
                        <th style="padding:10px 16px;text-align:center;color:#e2e8f0;font-size:12px;font-weight:700;">REPAIR BY</th>
                    </tr>
                </thead>
                <tbody>{fault_rows}</tbody>
            </table>
        </div>"""

    # Component risk section
    comp_section = ''
    if comps:
        comp_items = ''.join([
            f"""<li style="padding:8px 0;border-bottom:1px solid #f1f5f9;
                            font-size:13px;color:#1e293b;">
                    <b style="color:#ef4444;">{c['component']}</b>
                    &nbsp;—&nbsp; {c['action']}
                </li>"""
            for c in comps
        ])
        comp_section = f"""
        <div style="margin-bottom:24px;">
            <h3 style="margin:0 0 12px;font-size:15px;font-weight:700;color:#0f172a;
                       text-transform:uppercase;letter-spacing:0.05em;">
                🔧 Component Alerts
            </h3>
            <ul style="margin:0;padding:0;list-style:none;border:1px solid #fecaca;
                       border-radius:8px;padding:0 16px;background:#fff5f5;">
                {comp_items}
            </ul>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{subject}</title>
</head>
<body style="margin:0;padding:0;background:#f8fafc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">

<!-- Wrapper -->
<table width="100%" cellpadding="0" cellspacing="0">
<tr><td align="center" style="padding:32px 16px;">
<table width="600" cellpadding="0" cellspacing="0"
       style="background:#ffffff;border-radius:16px;overflow:hidden;
              box-shadow:0 4px 24px rgba(0,0,0,0.08);max-width:600px;width:100%;">

    <!-- HEADER -->
    <tr>
        <td style="background:#0f172a;padding:28px 32px;">
            <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
                <td>
                    <span style="font-size:28px;font-weight:900;color:#22d3ee;
                                 letter-spacing:-0.5px;">VEXIS</span>
                    <br/>
                    <span style="font-size:10px;color:#94a3b8;letter-spacing:0.1em;
                                 font-weight:600;">AI VEHICLE INTELLIGENCE PLATFORM</span>
                </td>
                <td align="right">
                    <span style="background:{t_color}22;color:{t_color};
                                 font-size:11px;font-weight:800;padding:5px 14px;
                                 border-radius:999px;border:1.5px solid {t_color};
                                 letter-spacing:0.08em;">
                        {tier}
                    </span>
                </td>
            </tr>
            </table>
        </td>
    </tr>

    <!-- VEHICLE BAR -->
    <tr>
        <td style="background:#1e293b;padding:14px 32px;">
            <span style="color:#ffffff;font-weight:700;font-size:15px;">
                {vehicle_name.upper()}
            </span>
            {f'<span style="color:#94a3b8;font-size:12px;"> &nbsp;//&nbsp; {vehicle_model}</span>' if vehicle_model else ''}
            <span style="float:right;color:#94a3b8;font-size:12px;">{date_str}</span>
        </td>
    </tr>

    <!-- BODY -->
    <tr>
        <td style="padding:32px;">

            <!-- Greeting -->
            <p style="margin:0 0 20px;font-size:15px;color:#1e293b;">
                Hi <b>{name}</b>, here is your latest vehicle health update from Vexis AI.
            </p>

            <!-- Score Card -->
            <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;
                        padding:24px;margin-bottom:24px;text-align:center;">
                <p style="margin:0 0 4px;font-size:11px;font-weight:700;color:#64748b;
                           letter-spacing:0.1em;text-transform:uppercase;">OVERALL HEALTH SCORE</p>
                <p style="margin:0;font-size:60px;font-weight:900;color:{t_color};
                           line-height:1.1;">{int(score)}<span style="font-size:22px;color:#94a3b8;">/100</span></p>
                <p style="margin:8px 0 0;font-size:14px;font-weight:700;color:{t_color};">
                    {tier_lbl}
                </p>
                <p style="margin:6px 0 0;font-size:13px;font-weight:600;color:{tr_color};">
                    Trend: {tr_arrow}
                    {f'({trend["delta"]:+.1f} pts)' if trend["delta"] != 0 else ''}
                </p>
            </div>

            {fault_section}
            {comp_section}

            <!-- Next Check -->
            <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;
                        padding:16px 20px;margin-bottom:24px;">
                <p style="margin:0;font-size:13px;color:#1e40af;font-weight:600;">
                    📅 &nbsp;Next scheduled health check:
                    <b>{timeline.get('next_notification', 'Coming soon')[:10]}</b>
                </p>
            </div>

            <!-- CTA Button -->
            <div style="text-align:center;margin-bottom:28px;">
                <a href="https://vexis-527f2.web.app"
                   style="display:inline-block;background:#22d3ee;color:#0f172a;
                          text-decoration:none;font-weight:800;font-size:14px;
                          padding:14px 36px;border-radius:8px;letter-spacing:0.03em;">
                    VIEW FULL REPORT →
                </a>
            </div>

            <!-- Disclaimer -->
            <p style="margin:0;font-size:11px;color:#94a3b8;text-align:center;
                       border-top:1px solid #e2e8f0;padding-top:20px;">
                This report is generated by Vexis AI using machine learning analysis.
                Always consult a certified mechanic for an official vehicle diagnosis.
                <br/><br/>
                <a href="#" style="color:#94a3b8;">Unsubscribe</a> from vehicle health alerts.
            </p>

        </td>
    </tr>

    <!-- FOOTER -->
    <tr>
        <td style="background:#0f172a;padding:16px 32px;text-align:center;">
            <span style="font-size:11px;color:#475569;">
                © {datetime.utcnow().year} Vexis AI Vehicle Intelligence &nbsp;•&nbsp;
                Powered by ML Engine v1.0
            </span>
        </td>
    </tr>

</table>
</td></tr>
</table>

</body>
</html>"""

    return {'subject': subject, 'html': html}
