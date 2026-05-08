"""
VEXIS — Ultra Premium Vehicle Health Report Generator
Industry-leading design: Advanced score ring, depth, gradients, shadows, luxury tech aesthetic.
"""

import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors as rc
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame,
    Flowable, Spacer, Paragraph, Table, TableStyle
)

# ── Palette ─────────────────────────────────────────────────────────────
def H(h): return rc.HexColor(h)

NAVY     = H('#0f172a')
SLATE    = H('#1e293b')
CYAN     = H('#22d3ee')
GREEN    = H('#22c55e')
LIME     = H('#a3e635')
AMBER    = H('#fbbf24')
ORANGE   = H('#fb923c')
RED      = H('#f87171')
LGRAY    = H('#f8fafc')
WHITE    = rc.white
BORDER   = H('#e2e8f0')
TEXT     = H('#0f172a')
MUTED    = H('#64748b')
SUBTLE   = H('#94a3b8')
ACCENT   = H('#67e8f9')

PAGE_W, PAGE_H = A4
MX = 20 * mm  # margin

def score_info(s):
    if s >= 90: return ('EXCELLENT', GREEN, '#22c55e')
    if s >= 75: return ('GOOD',      LIME,  '#a3e635')
    if s >= 60: return ('FAIR',      AMBER, '#fbbf24')
    if s >= 40: return ('POOR',      ORANGE,'#fb923c')
    return              ('CRITICAL', RED,   '#f87171')


def ps(name='custom', **kw):
    return ParagraphStyle(name, **kw)


# ── Custom Flowables ─────────────────────────────────────────────────────

class PremiumScoreRing(Flowable):
    """Ultra-premium glowing score ring"""
    def __init__(self, score, color, size=118):
        Flowable.__init__(self)
        self.score = min(max(float(score), 0), 100)
        self.color = color
        self.size = size

    def wrap(self, *a): return (self.size, self.size)

    def draw(self):
        c = self.canv
        sz = self.size
        cx = cy = sz / 2
        outer_r = sz/2 - 6
        ring_w = 14

        # Soft outer glow
        c.setStrokeColor(H('#bae6fd'))
        c.setLineWidth(ring_w + 8)
        c.setLineCap(1)
        p = c.beginPath()
        p.arc(cx-outer_r, cy-outer_r, cx+outer_r, cy+outer_r, 90, -360)
        c.drawPath(p, stroke=1, fill=0)

        # Background ring
        c.setStrokeColor(H('#e2e8f0'))
        c.setLineWidth(ring_w)
        p = c.beginPath()
        p.arc(cx-outer_r, cy-outer_r, cx+outer_r, cy+outer_r, 90, -360)
        c.drawPath(p, stroke=1, fill=0)

        # Progress ring
        if self.score > 0:
            c.setStrokeColor(self.color)
            c.setLineWidth(ring_w)
            extent = -(self.score / 100) * 360
            p = c.beginPath()
            p.arc(cx-outer_r, cy-outer_r, cx+outer_r, cy+outer_r, 90, extent)
            c.drawPath(p, stroke=1, fill=0)

        # Inner white circle
        c.setFillColor(WHITE)
        c.circle(cx, cy, outer_r - ring_w/2 - 2, fill=1, stroke=0)

        # Score
        s = str(int(self.score))
        c.setFillColor(TEXT)
        c.setFont('Helvetica-Bold', 34)
        tw = c.stringWidth(s, 'Helvetica-Bold', 34)
        c.drawString(cx - tw/2, cy + 6, s)

        c.setFillColor(MUTED)
        c.setFont('Helvetica', 10)
        tw2 = c.stringWidth('/100', 'Helvetica', 10)
        c.drawString(cx - tw2/2, cy - 14, '/100')


class EnhancedProgressBar(Flowable):
    def __init__(self, score, color, width=168, height=11):
        Flowable.__init__(self)
        self.score = min(max(float(score), 0), 100)
        self.color = color
        self.width = width
        self.height = height

    def wrap(self, *a): return (self.width, self.height)

    def draw(self):
        c = self.canv
        h = self.height
        # Background
        c.setFillColor(H('#f1f5f9'))
        c.roundRect(0, 0, self.width, h, h/2, fill=1, stroke=0)
        # Progress
        fw = max((self.score/100)*self.width, h)
        c.setFillColor(self.color)
        c.roundRect(0, 0, fw, h, h/2, fill=1, stroke=0)
        # Gloss
        if fw > 20:
            c.setFillColor(WHITE)
            c.setFillAlpha(0.35)
            c.roundRect(2, h*0.55, fw-6, h*0.35, h*0.2, fill=1, stroke=0)


class SectionHeader(Flowable):
    def __init__(self, text, accent=ACCENT):
        Flowable.__init__(self)
        self.text = text.upper()
        self.accent = accent

    def wrap(self, aw, ah): 
        self._w = aw
        return (aw, 32)

    def draw(self):
        c = self.canv
        c.setFillColor(LGRAY)
        c.roundRect(0, 4, self._w, 24, 6, fill=1, stroke=0)
        c.setFillColor(self.accent)
        c.roundRect(0, 4, 6, 24, 3, fill=1, stroke=0)
        c.setFillColor(TEXT)
        c.setFont('Helvetica-Bold', 12.5)
        c.drawString(18, 12, self.text)


# ── Page Header/Footer ───────────────────────────────────────────────────
def make_page_template(vehicle_name, vehicle_model, gen_date, n_rows, quality):
    def draw_page(canvas, doc):
        canvas.saveState()
        w, h = doc.pagesize
        HDR = 48 * mm

        # Header
        canvas.setFillColor(NAVY)
        canvas.rect(0, h - HDR, w, HDR, fill=1, stroke=0)

        # Subtle tech pattern
        canvas.setFillColor(H('#334155'))
        for i in range(40):
            canvas.circle(12 + (i%12)*18, h - HDR + 12 + (i//12)*18, 0.8, fill=1, stroke=0)

        # Branding
        canvas.setFillColor(CYAN)
        canvas.setFont('Helvetica-Bold', 32)
        canvas.drawString(MX, h - 21*mm, 'VEXIS')

        canvas.setFillColor(SUBTLE)
        canvas.setFont('Helvetica', 8.5)
        canvas.drawString(MX, h - 28*mm, 'AI VEHICLE INTELLIGENCE PLATFORM')

        canvas.setStrokeColor(ACCENT)
        canvas.setLineWidth(1)
        canvas.line(MX, h - 32*mm, w - MX, h - 32*mm)

        # Vehicle Info
        canvas.setFillColor(WHITE)
        canvas.setFont('Helvetica-Bold', 15)
        canvas.drawString(MX, h - 40*mm, vehicle_name.upper())
        if vehicle_model:
            canvas.setFillColor(SUBTLE)
            canvas.setFont('Helvetica', 9.5)
            canvas.drawString(MX, h - 45.5*mm, vehicle_model)

        # Right Meta
        rx = w - MX
        canvas.setFillColor(SUBTLE)
        canvas.setFont('Helvetica-Bold', 9)
        canvas.drawRightString(rx, h - 20*mm, 'VEHICLE HEALTH REPORT')
        canvas.setFont('Helvetica', 8)
        canvas.drawRightString(rx, h - 27*mm, f'Generated: {gen_date}')
        canvas.drawRightString(rx, h - 33*mm, f'Readings: {n_rows}   •   Quality: {quality}')
        canvas.drawRightString(rx, h - 39*mm, 'Powered by Vexis ML Engine')

        # Footer
        canvas.setFillColor(LGRAY)
        canvas.rect(0, 0, w, 12*mm, fill=1, stroke=0)
        canvas.setStrokeColor(BORDER)
        canvas.line(MX, 12*mm, w - MX, 12*mm)
        canvas.setFillColor(MUTED)
        canvas.setFont('Helvetica', 7.2)
        canvas.drawString(MX, 4*mm, 
            "This report is generated by Vexis AI using machine learning. "
            "Consult a certified mechanic for official diagnosis.")
        canvas.drawRightString(w - MX, 4*mm, f'Page {doc.page}')
        canvas.restoreState()
    return draw_page


# ── Main PDF Generator ───────────────────────────────────────────────────
def generate_report_pdf(
    vehicle_name, vehicle_model,
    overall_score, engine_score, fuel_score,
    efficiency_score, driving_score, thermal_score,
    status_label, failure_risk,
    persist_issues, issue_counts, n_results, quality
):
    gen_date = datetime.now().strftime('%d %b %Y • %H:%M')
    buf = io.BytesIO()

    TOP = 48*mm + 10*mm
    BOT = 12*mm + 8*mm
    frame = Frame(MX, BOT, PAGE_W - 2*MX, PAGE_H - TOP - BOT,
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)

    page_fn = make_page_template(vehicle_name, vehicle_model, gen_date, n_results, quality)
    tmpl = PageTemplate(id='main', frames=[frame], onPage=page_fn)
    doc = BaseDocTemplate(buf, pagesize=A4, pageTemplates=[tmpl])

    story = []

    # HERO SECTION
    ov_lbl, ov_clr, ov_hex = score_info(overall_score)
    ring = PremiumScoreRing(overall_score, ov_clr)

    risk_txt = "● AT RISK" if failure_risk else "● HEALTHY"
    risk_color = RED if failure_risk else GREEN

    hero_right = Table([
        [Paragraph('OVERALL HEALTH SCORE', ps(fontSize=8, textColor=SUBTLE, fontName='Helvetica-Bold'))],
        [Paragraph(f'<font color="{ov_hex}" size="38"><b>{int(overall_score)}</b></font>'
                   f'<font color="#94a3b8" size="13"> /100</font>', 
                   ps(fontSize=12, leading=38))],
        [Paragraph(ov_lbl, ps(fontSize=13.5, textColor=ov_clr, fontName='Helvetica-Bold'))],
        [Paragraph(risk_txt, ps(fontSize=9.5, textColor=risk_color, fontName='Helvetica-Bold'))],
    ], colWidths=[145])

    # Mini components
    mini_data = []
    for name, score in [('ENGINE', engine_score), ('FUEL', fuel_score), ('EFFICIENCY', efficiency_score),
                        ('DRIVING', driving_score), ('THERMAL', thermal_score)]:
        lbl, clr, hx = score_info(score)
        mini_data.append([
            Paragraph(name, ps(fontSize=7.5, textColor=SUBTLE)),
            Paragraph(f'<font color="{hx}"><b>{int(score)}</b></font>', 
                      ps(fontSize=11, fontName='Helvetica-Bold', alignment=TA_RIGHT)),
            EnhancedProgressBar(score, clr, width=72, height=5.5)
        ])

    mini_table = Table(mini_data, colWidths=[58, 28, 78])
    mini_table.setStyle(TableStyle([('BACKGROUND', (0,0),(-1,-1), SLATE),
                                    ('TOPPADDING', (0,0),(-1,-1), 6),
                                    ('BOTTOMPADDING', (0,0),(-1,-1), 6),
                                    ('VALIGN', (0,0),(-1,-1), 'MIDDLE')]))

    hero = Table([[ring, hero_right, mini_table]], colWidths=[130, 155, 170])
    hero.setStyle(TableStyle([
        ('BACKGROUND', (0,0),(0,0), WHITE),
        ('BACKGROUND', (1,0),(2,0), WHITE),
        ('BOX', (0,0),(-1,-1), 0.8, BORDER),
        ('ROUNDEDCORNERS', [10]),
        ('TOPPADDING', (0,0),(-1,-1), 16),
        ('BOTTOMPADDING', (0,0),(-1,-1), 16),
    ]))
    story.append(hero)
    story.append(Spacer(1, 18))

    # COMPONENT HEALTH SCORES
    story.append(SectionHeader('Component Health Scores', CYAN))
    story.append(Spacer(1, 10))

    comps = [
        ("Engine", engine_score),
        ("Fuel System", fuel_score),
        ("Efficiency", efficiency_score),
        ("Driving", driving_score),
        ("Thermal", thermal_score),
    ]

    def comp_card(name, score):
        lbl, clr, hx = score_info(score)
        bar = EnhancedProgressBar(score, clr)
        t = Table([
            [Paragraph(f'<b>{name}</b>', ps(fontSize=11, fontName='Helvetica-Bold', textColor=TEXT)),
             Paragraph(f'<font color="{hx}"><b>{int(score)}</b></font>', 
                       ps(fontSize=22, fontName='Helvetica-Bold', alignment=TA_RIGHT))],
            [Paragraph(lbl, ps(fontSize=8, textColor=clr, fontName='Helvetica-Bold')), None],
            [bar, None]
        ], colWidths=[118, 65])
        t.setStyle(TableStyle([('SPAN', (0,2),(1,2)), ('VALIGN', (0,0),(-1,-1),'MIDDLE')]))

        card = Table([[t]], colWidths=[200])
        card.setStyle(TableStyle([
            ('BACKGROUND', (0,0),(-1,-1), WHITE),
            ('BOX', (0,0),(-1,-1), 0.7, BORDER),
            ('ROUNDEDCORNERS', [8]),
            ('TOPPADDING', (0,0),(-1,-1), 14),
            ('BOTTOMPADDING', (0,0),(-1,-1), 14),
            ('LEFTPADDING', (0,0),(-1,-1), 16),
            ('RIGHTPADDING', (0,0),(-1,-1), 16),
        ]))
        return card

    left = [[comp_card(n, s)] for n, s in comps[:3]]
    right = [[comp_card(n, s)] for n, s in comps[3:]]
    grid = Table([[Table(left, colWidths=[200]), Table(right, colWidths=[200])]], 
                 colWidths=[210, 210], spaceAfter=16)
    story.append(grid)

    # ── ISSUES ────────────────────────────────────────────────────────
    story.append(SectionHeader('Diagnostic Fault Codes & Issues', RED if persist_issues else GREEN))
    story.append(Spacer(1, 10))

    if persist_issues:
        hdr_st = ps(fontSize=9, textColor=WHITE, fontName='Helvetica-Bold')
        rows = [[
            Paragraph('ID', hdr_st),
            Paragraph('ISSUE DESCRIPTION', hdr_st),
            Paragraph('FREQUENCY', hdr_st),
        ]]
        for i, iss in enumerate(persist_issues, 1):
            cnt = issue_counts[iss]
            pct = round(cnt / n_results * 100)
            is_high = pct >= 50
            tx_clr = '#ef4444' if is_high else '#0f172a'
            
            # Simple pill text for status
            pill_text = f"<font color='{'#ef4444' if is_high else '#fbbf24'}'><b>{pct}%</b></font>"
            
            rows.append([
                Paragraph(f'<b>{i:02d}</b>', ps(fontSize=9, textColor=MUTED)),
                Paragraph(f'<b>{iss}</b>' if is_high else iss, ps(fontSize=9, textColor=H(tx_clr))),
                Paragraph(pill_text, ps(fontSize=9, alignment=TA_CENTER))
            ])
            
        iss_tbl = Table(rows, colWidths=[35, 380, 75])
        iss_tbl.setStyle(TableStyle([
            ('BACKGROUND',    (0,0),(-1,0),  NAVY),
            ('ALIGN',         (0,0),(-1,-1), 'LEFT'),
            ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
            ('TOPPADDING',    (0,0),(-1,-1), 10),
            ('BOTTOMPADDING', (0,0),(-1,-1), 10),
            ('LEFTPADDING',   (0,0),(-1,-1), 12),
            ('ROWBACKGROUNDS',(0,1),(-1,-1), [H('#f8fafc'), WHITE]),
            ('BOX',           (0,0),(-1,-1), 1, BORDER),
            ('INNERGRID',     (0,0),(-1,-1), 0.5, BORDER),
            ('ROUNDEDCORNERS',[8]),
        ]))
        story.append(iss_tbl)
    else:
        ok = Table([[
            Paragraph('<b>NO PERSISTENT FAULTS DETECTED.</b> System operating within normal parameters.',
            ps(fontSize=10, textColor=GREEN, fontName='Helvetica-Bold'))
        ]], colWidths=[int(PAGE_W - 2*MX)])
        ok.setStyle(TableStyle([
            ('BACKGROUND',    (0,0),(-1,-1), H('#f0fdf4')),
            ('BOX',           (0,0),(-1,-1), 1, GREEN),
            ('TOPPADDING',    (0,0),(-1,-1), 12),
            ('BOTTOMPADDING', (0,0),(-1,-1), 12),
            ('LEFTPADDING',   (0,0),(-1,-1), 16),
            ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
            ('ROUNDEDCORNERS',[8]),
        ]))
        story.append(ok)

    story.append(Spacer(1, 20))

    # ── RECOMMENDATIONS ───────────────────────────────────────────────
    story.append(SectionHeader('Actionable Recommendations', AMBER))
    story.append(Spacer(1, 10))

    rec_map = [
        (engine_score,     'Engine health is below optimal. Schedule a full engine diagnostic immediately.'),
        (fuel_score,       'Fuel system efficiency is low. Inspect injectors and O2 sensors.'),
        (thermal_score,    'Thermal stress is elevated. Inspect the cooling system and coolant levels.'),
        (driving_score,    'Driving pattern shows aggressive inputs. Reduce hard acceleration and braking.'),
        (efficiency_score, 'Engine efficiency is poor. Check air filter and spark plugs.'),
    ]
    recs = [msg for sc, msg in rec_map if sc < 60]
    if not recs:
        recs = ['Vehicle is in excellent health. Maintain regular service intervals as recommended.']

    for i, r in enumerate(recs, 1):
        t = Table([[
            Paragraph(r, ps(fontSize=9.5, textColor=TEXT, fontName='Helvetica-Bold')),
        ]], colWidths=[int(PAGE_W - 2*MX)])
        t.setStyle(TableStyle([
            ('BACKGROUND',    (0,0),(-1,-1), H('#fffbeb')),
            ('BOX',           (0,0),(-1,-1), 1, H('#fde68a')),
            ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
            ('TOPPADDING',    (0,0),(-1,-1), 10),
            ('BOTTOMPADDING', (0,0),(-1,-1), 10),
            ('LEFTPADDING',   (0,0),(-1,-1), 14),
            ('ROUNDEDCORNERS',[6]),
        ]))
        story.append(t)
        story.append(Spacer(1, 6))

    story.append(Spacer(1, 14))

    # ── SCAN SUMMARY ──────────────────────────────────────────────────
    cw4 = (int(PAGE_W - 2*MX) - 30) // 4
    sum_data = [[
        Paragraph('READINGS ANALYSED', ps(fontSize=8, textColor=MUTED, fontName='Helvetica-Bold')),
        Paragraph('DATA QUALITY',      ps(fontSize=8, textColor=MUTED, fontName='Helvetica-Bold')),
        Paragraph('ANALYSIS ENGINE',   ps(fontSize=8, textColor=MUTED, fontName='Helvetica-Bold')),
        Paragraph('REPORT DATE',       ps(fontSize=8, textColor=MUTED, fontName='Helvetica-Bold')),
    ], [
        Paragraph(f'<b>{n_results}</b>', ps(fontSize=14, fontName='Helvetica-Bold', textColor=CYAN)),
        Paragraph(f'<b>{quality.upper()}</b>',   ps(fontSize=14, fontName='Helvetica-Bold', textColor=TEXT)),
        Paragraph('<b>VEXIS ML V1.0</b>',ps(fontSize=12, fontName='Helvetica-Bold', textColor=TEXT)),
        Paragraph(f'<b>{datetime.now().strftime("%d %b %Y")}</b>',  ps(fontSize=12,  fontName='Helvetica-Bold', textColor=TEXT)),
    ]]
    sum_tbl = Table(sum_data, colWidths=[cw4, cw4, cw4, cw4])
    sum_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,-1), WHITE),
        ('BOX',           (0,0),(-1,-1), 1, BORDER),
        ('TOPPADDING',    (0,0),(-1,-1), 12),
        ('BOTTOMPADDING', (0,0),(-1,-1), 12),
        ('LEFTPADDING',   (0,0),(-1,-1), 16),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ('ROUNDEDCORNERS',[10]),
    ]))
    story.append(sum_tbl)

    doc.build(story)
    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes# Deployment trigger refresh
