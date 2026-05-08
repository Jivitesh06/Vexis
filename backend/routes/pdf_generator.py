"""
Vexis — Ultra-Premium Enterprise PDF Report Generator
Aesthetics: Dark tech-luxury, Tesla/Porsche/Bosch diagnostic level.
"""
import io
import math
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors as rc
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame,
    Flowable, Spacer, Paragraph, Table, TableStyle, KeepTogether
)

# ── Palette ──────────────────────────────────────────────────────────
def H(h, alpha=1.0):
    c = rc.HexColor(h)
    c.alpha = alpha
    return c

NAVY   = H('#0f172a')
SLATE  = H('#1e293b')
CYAN   = H('#22d3ee')
GREEN  = H('#22c55e')
AMBER  = H('#fb923c')
RED    = H('#f87171')
TEXT_L = H('#e2e8f0')
TEXT_D = H('#0f172a')
PAGE_BG= H('#f8fafc')
WHITE  = rc.white
BORDER = H('#e2e8f0')
MUTED  = H('#64748b')

PAGE_W, PAGE_H = A4
MX = 16 * mm

def score_info(s):
    if s >= 90: return ('EXCELLENT', GREEN,  '#22c55e')
    if s >= 75: return ('GOOD',      CYAN,   '#22d3ee')
    if s >= 60: return ('FAIR',      AMBER,  '#fb923c')
    if s >= 40: return ('POOR',      RED,    '#f87171')
    return              ('CRITICAL', RED,    '#f87171')

def ps(name, **kw):
    return ParagraphStyle(name, **kw)

# ── Custom Flowables ──────────────────────────────────────────────────

class ScoreRing(Flowable):
    """Ultra-modern glowing arc score ring."""
    def __init__(self, score, color, size=120):
        Flowable.__init__(self)
        self.score = min(max(float(score), 0), 100)
        self.color = color
        self.size  = size

    def wrap(self, *a): return (self.size, self.size)

    def draw(self):
        c = self.canv
        sz = self.size
        cx = cy = sz / 2
        ro = sz / 2 - 10
        lw = 14

        # Background Track
        c.setStrokeColor(H('#1e293b', 0.5))
        c.setLineWidth(lw)
        c.setLineCap(1) # Round caps
        c.arc(cx-ro, cy-ro, cx+ro, cy+ro, startAng=225, extent=-270)

        # Glow effect (simulated with faint larger rings)
        if self.score > 0:
            extent = -(self.score/100)*270
            c.setStrokeColor(H(self.color.hexval()[1:], 0.2))
            c.setLineWidth(lw + 6)
            c.arc(cx-ro, cy-ro, cx+ro, cy+ro, startAng=225, extent=extent)
            
            c.setStrokeColor(H(self.color.hexval()[1:], 0.4))
            c.setLineWidth(lw + 2)
            c.arc(cx-ro, cy-ro, cx+ro, cy+ro, startAng=225, extent=extent)

            # Main progress arc
            c.setStrokeColor(self.color)
            c.setLineWidth(lw)
            c.arc(cx-ro, cy-ro, cx+ro, cy+ro, startAng=225, extent=extent)

        # Inner shadow / depth
        c.setFillColor(H('#000000', 0.1))
        c.circle(cx, cy - 2, ro - lw/2 + 1, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.circle(cx, cy, ro - lw/2 + 2, fill=1, stroke=0)

        # Score Text
        s = str(int(self.score))
        c.setFillColor(TEXT_D)
        c.setFont('Helvetica-Bold', 36)
        tw = c.stringWidth(s, 'Helvetica-Bold', 36)
        c.drawString(cx - tw/2, cy - 4, s)
        
        c.setFillColor(MUTED)
        c.setFont('Helvetica-Bold', 10)
        tw2 = c.stringWidth('/100', 'Helvetica-Bold', 10)
        c.drawString(cx - tw2/2, cy - 18, '/100')


class PremiumProgressBar(Flowable):
    """Wide, elegant rounded progress bar with fake gradient."""
    def __init__(self, score, color, width=160, height=12):
        Flowable.__init__(self)
        self.score  = min(max(float(score), 0), 100)
        self.color  = color
        self.width  = width
        self.height = height

    def wrap(self, *a): return (self.width, self.height)

    def draw(self):
        h = self.height
        w = self.width
        c = self.canv
        
        # Track
        c.setFillColor(H('#f1f5f9'))
        c.roundRect(0, 0, w, h, h/2, fill=1, stroke=0)
        
        # Inner shadow
        c.setStrokeColor(H('#e2e8f0'))
        c.setLineWidth(0.5)
        c.roundRect(0, 0, w, h, h/2, fill=0, stroke=1)

        fw = max((self.score/100)*w, h)
        if fw > 0:
            # Main fill
            c.setFillColor(self.color)
            c.roundRect(0, 0, fw, h, h/2, fill=1, stroke=0)
            
            # Top highlight (glass effect)
            if fw > h * 2:
                c.setFillColor(WHITE)
                c.setFillAlpha(0.2)
                c.roundRect(h/2, h*0.5, fw - h, h*0.4, h*0.15, fill=1, stroke=0)
                c.setFillAlpha(1.0)


class StatusPill(Flowable):
    """Rounded pill badge for status."""
    def __init__(self, text, color, width=70, height=18):
        Flowable.__init__(self)
        self.text = text
        self.color = color
        self.width = width
        self.height = height

    def wrap(self, *a): return (self.width, self.height)

    def draw(self):
        c = self.canv
        h = self.height
        c.setFillColor(H(self.color.hexval()[1:], 0.15))
        c.roundRect(0, 0, self.width, h, h/2, fill=1, stroke=0)
        
        c.setStrokeColor(self.color)
        c.setLineWidth(1)
        c.roundRect(0, 0, self.width, h, h/2, fill=0, stroke=1)
        
        c.setFillColor(self.color)
        c.setFont('Helvetica-Bold', 8.5)
        tw = c.stringWidth(self.text, 'Helvetica-Bold', 8.5)
        c.drawString((self.width - tw)/2, h/2 - 3, self.text)


class IconShape(Flowable):
    """Draws a simple sleek vector icon based on type."""
    def __init__(self, kind, color, size=24):
        Flowable.__init__(self)
        self.kind = kind
        self.color = color
        self.size = size

    def wrap(self, *a): return (self.size, self.size)

    def draw(self):
        c = self.canv
        s = self.size
        cx, cy = s/2, s/2
        
        c.setFillColor(H(self.color.hexval()[1:], 0.1))
        c.roundRect(0, 0, s, s, 6, fill=1, stroke=0)
        
        c.setStrokeColor(self.color)
        c.setFillColor(self.color)
        c.setLineWidth(1.5)
        c.setLineCap(1)
        c.setLineJoin(1)
        
        if self.kind == 'Engine':
            c.rect(cx-5, cy-4, 10, 8, fill=0, stroke=1)
            c.line(cx-7, cy, cx-5, cy)
            c.line(cx+5, cy, cx+7, cy)
            c.line(cx, cy-6, cx, cy-4)
            c.line(cx, cy+4, cx, cy+6)
        elif self.kind == 'Fuel':
            c.rect(cx-4, cy-6, 8, 12, fill=0, stroke=1)
            c.line(cx-4, cy+2, cx+4, cy+2)
            c.rect(cx+5, cy-6, 2, 8, fill=1, stroke=0)
        elif self.kind == 'Efficiency':
            c.circle(cx, cy, 6, fill=0, stroke=1)
            c.line(cx, cy+6, cx, cy+2)
            c.line(cx, cy+2, cx+3, cy-1)
        elif self.kind == 'Driving':
            c.arc(cx-6, cy-6, cx+6, cy+6, startAng=0, extent=180)
            c.line(cx-7, cy, cx+7, cy)
            c.line(cx, cy, cx+3, cy+3)
        elif self.kind == 'Thermal':
            c.rect(cx-2, cy-2, 4, 8, fill=0, stroke=1)
            c.circle(cx, cy-4, 3, fill=0, stroke=1)
        elif self.kind == 'Rec':
            c.circle(cx, cy, 6, fill=0, stroke=1)
            c.line(cx, cy-3, cx, cy+1)
            c.circle(cx, cy+3, 0.5, fill=1, stroke=0)

class SectionHeader(Flowable):
    def __init__(self, text, color=CYAN):
        Flowable.__init__(self)
        self.text = text.upper()
        self.color = color

    def wrap(self, aw, ah):
        self._w = aw
        return (aw, 30)

    def draw(self):
        c = self.canv
        c.setFillColor(self.color)
        c.rect(0, 5, 4, 16, fill=1, stroke=0)
        c.setFillColor(TEXT_D)
        c.setFont('Helvetica-Bold', 12)
        c.drawString(12, 8, self.text)

# ── Page callback ─────────────────────────────────────────────────────

def _make_page_fn(vehicle_name, vehicle_model, gen_date, n_rows, quality):
    def _draw(canvas, doc):
        canvas.saveState()
        w, h = doc.pagesize
        HDR = 54 * mm

        # Base Page Background
        canvas.setFillColor(PAGE_BG)
        canvas.rect(0, 0, w, h, fill=1, stroke=0)

        # Header background
        canvas.setFillColor(NAVY)
        canvas.rect(0, h - HDR, w, HDR, fill=1, stroke=0)

        # Subtle geometric pattern in header
        canvas.setStrokeColor(H('#1e293b', 0.6))
        canvas.setLineWidth(0.5)
        for i in range(0, int(w), 20):
            canvas.line(i, h - HDR, i + 40, h)
            canvas.line(i, h, i + 40, h - HDR)

        # Bottom glowing border of header
        canvas.setFillColor(CYAN)
        canvas.rect(0, h - HDR, w, 2, fill=1, stroke=0)

        # VEXIS logotype
        canvas.setFillColor(CYAN)
        canvas.setFont('Helvetica-Bold', 34)
        canvas.drawString(MX, h - 22*mm, 'VEXIS')

        canvas.setFillColor(TEXT_L)
        canvas.setFont('Helvetica-Bold', 9)
        canvas.drawString(MX, h - 28.5*mm, 'AI VEHICLE INTELLIGENCE PLATFORM')

        # Vehicle name block
        canvas.setFillColor(WHITE)
        canvas.setFont('Helvetica-Bold', 18)
        v_name = vehicle_name.upper()
        canvas.drawString(MX, h - 42*mm, v_name)
        if vehicle_model:
            canvas.setFillColor(CYAN)
            canvas.setFont('Helvetica-Bold', 10)
            canvas.drawString(MX + canvas.stringWidth(v_name, 'Helvetica-Bold', 18) + 10, h - 42*mm, f"// {vehicle_model.upper()}")

        # Right block
        rx = w - MX
        canvas.setFillColor(WHITE)
        canvas.setFont('Helvetica-Bold', 12)
        canvas.drawRightString(rx, h - 22*mm, 'VEHICLE HEALTH REPORT')
        
        canvas.setFont('Helvetica', 9)
        canvas.setFillColor(H('#94a3b8'))
        canvas.drawRightString(rx, h - 28.5*mm, f'GENERATED: {gen_date.upper()}')
        canvas.drawRightString(rx, h - 35*mm, f'READINGS: {n_rows}   |   QUALITY: {quality.upper()}')
        
        canvas.setFillColor(CYAN)
        canvas.drawRightString(rx, h - 42*mm, 'POWERED BY VEXIS ML ENGINE')

        # Footer
        canvas.setFillColor(WHITE)
        canvas.rect(0, 0, w, 12*mm, fill=1, stroke=0)
        canvas.setStrokeColor(BORDER)
        canvas.setLineWidth(1)
        canvas.line(0, 12*mm, w, 12*mm)
        canvas.setFillColor(MUTED)
        canvas.setFont('Helvetica-Bold', 7)
        canvas.drawString(MX, 4.5*mm, 'VEXIS AI REPORT  //  AUTOMATED ML ANALYSIS — CONSULT A CERTIFIED MECHANIC FOR OFFICIAL DIAGNOSIS.')
        canvas.drawRightString(w - MX, 4.5*mm, f'PAGE {doc.page}')
        canvas.restoreState()
    return _draw


# ── Main generator ────────────────────────────────────────────────────

def generate_report_pdf(
    vehicle_name, vehicle_model,
    overall_score, engine_score, fuel_score,
    efficiency_score, driving_score, thermal_score,
    status_label, failure_risk,
    persist_issues, issue_counts, n_results, quality
):
    gen_date = datetime.now().strftime('%d %b %Y, %H:%M')
    buf      = io.BytesIO()

    TOP_PAD = 54*mm + 6*mm
    BOT_PAD = 12*mm + 6*mm
    CW = PAGE_W - 2*MX

    frame = Frame(MX, BOT_PAD, CW, PAGE_H - TOP_PAD - BOT_PAD,
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    page_fn = _make_page_fn(vehicle_name, vehicle_model, gen_date, n_results, quality)
    tmpl    = PageTemplate(id='p', frames=[frame], onPage=page_fn)
    pdoc    = BaseDocTemplate(buf, pagesize=A4, pageTemplates=[tmpl])

    story = []

    # ── HERO: Score ring + info + mini components ─────────────────────
    ov_lbl, ov_clr, ov_hex = score_info(overall_score)
    ring = ScoreRing(overall_score, ov_clr, size=130)

    risk_clr = RED if failure_risk else GREEN
    risk_txt = 'CRITICAL RISK' if failure_risk else 'SYSTEM HEALTHY'

    score_block = Table([
        [Paragraph('OVERALL HEALTH SCORE', ps('oht', fontSize=9, textColor=MUTED, fontName='Helvetica-Bold', leading=12))],
        [Spacer(1, 4)],
        [StatusPill(ov_lbl, ov_clr, width=90, height=22)],
        [Spacer(1, 6)],
        [StatusPill(risk_txt, risk_clr, width=110, height=22)],
    ], colWidths=[130])
    score_block.setStyle(TableStyle([
        ('LEFTPADDING',  (0,0),(-1,-1), 0),
        ('RIGHTPADDING', (0,0),(-1,-1), 0),
        ('TOPPADDING',   (0,0),(-1,-1), 0),
        ('BOTTOMPADDING',(0,0),(-1,-1), 0),
    ]))

    # Mini component dashboard panel (Dark Theme)
    mini_comps = [
        ('ENGINE', engine_score), ('FUEL', fuel_score),
        ('EFFICIENCY', efficiency_score), ('DRIVING', driving_score),
        ('THERMAL', thermal_score)
    ]
    mini_rows = []
    for cname, cscore in mini_comps:
        lbl, clr, chx = score_info(cscore)
        
        # Mini bar
        bar = PremiumProgressBar(cscore, clr, width=70, height=6)
        
        mini_rows.append([
            Paragraph(cname, ps(f'mn{cname}', fontSize=8, textColor=TEXT_L, fontName='Helvetica-Bold')),
            Paragraph(f'<font color="{chx}"><b>{int(cscore)}</b></font>', ps(f'ms{cname}', fontSize=10, fontName='Helvetica-Bold', alignment=TA_RIGHT)),
            bar,
            Paragraph(f'<font color="{chx}"><b>{lbl}</b></font>', ps(f'ml{cname}', fontSize=7, fontName='Helvetica-Bold', alignment=TA_RIGHT)),
        ])

    mini_tbl = Table(mini_rows, colWidths=[65, 25, 75, 45])
    mini_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,-1), SLATE),
        ('TOPPADDING',    (0,0),(-1,-1), 8),
        ('BOTTOMPADDING', (0,0),(-1,-1), 8),
        ('LEFTPADDING',   (0,0),(0,-1),  12),
        ('RIGHTPADDING',  (3,0),(3,-1),  12),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ('LINEBELOW',     (0,0),(-1,-2), 0.5, H('#334155')),
        ('ROUNDEDCORNERS',[8]),
    ]))

    hero = Table([[ring, score_block, mini_tbl]], colWidths=[140, 130, 230])
    hero.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(1,0), WHITE),
        ('TOPPADDING',    (0,0),(-1,-1), 20),
        ('BOTTOMPADDING', (0,0),(-1,-1), 20),
        ('LEFTPADDING',   (0,0),(-1,-1), 16),
        ('RIGHTPADDING',  (0,0),(-1,-1), 16),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ('BOX',           (0,0),(-1,-1), 1, BORDER),
        ('ROUNDEDCORNERS',[12]),
    ]))
    
    # Shadow for hero card (simulated with a slightly offset gray table behind it)
    # To keep it simple in ReportLab, we just use the nice rounded border.
    story.append(hero)
    story.append(Spacer(1, 20))

    # ── COMPONENT CARDS ───────────────────────────────────────────────
    story.append(SectionHeader('System Component Analysis', CYAN))
    story.append(Spacer(1, 10))

    all_comps = [
        ('Engine',     engine_score),
        ('Fuel',       fuel_score),
        ('Efficiency', efficiency_score),
        ('Driving',    driving_score),
        ('Thermal',    thermal_score),
    ]

    def make_card(cname, cscore):
        lbl, clr, chx = score_info(cscore)
        icon = IconShape(cname, clr, size=28)
        bar = PremiumProgressBar(cscore, clr, width=170, height=10)
        
        header_tbl = Table([
            [icon, Paragraph(f'<b>{cname.upper()}</b>', ps(f'cc{cname}', fontSize=11, fontName='Helvetica-Bold', textColor=TEXT_D)),
             Paragraph(f'<font color="{chx}"><b>{int(cscore)}</b></font>', ps(f'cs{cname}', fontSize=22, fontName='Helvetica-Bold', alignment=TA_RIGHT))]
        ], colWidths=[35, 100, 60])
        header_tbl.setStyle(TableStyle([('VALIGN', (0,0),(-1,-1), 'MIDDLE'), ('LEFTPADDING', (0,0),(-1,-1), 0), ('RIGHTPADDING', (0,0),(-1,-1), 0)]))
        
        inner = Table([
            [header_tbl],
            [Spacer(1, 8)],
            [bar],
            [Spacer(1, 4)],
            [Paragraph(f'<font color="{chx}"><b>STATUS: {lbl}</b></font>', ps(f'cl{cname}', fontSize=8, fontName='Helvetica-Bold', textColor=clr))]
        ], colWidths=[195])
        inner.setStyle(TableStyle([('LEFTPADDING', (0,0),(-1,-1), 0), ('RIGHTPADDING', (0,0),(-1,-1), 0), ('TOPPADDING', (0,0),(-1,-1), 0), ('BOTTOMPADDING', (0,0),(-1,-1), 0)]))
        
        card = Table([[inner]], colWidths=[235])
        card.setStyle(TableStyle([
            ('BACKGROUND',    (0,0),(-1,-1), WHITE),
            ('BOX',           (0,0),(-1,-1), 1, BORDER),
            ('TOPPADDING',    (0,0),(-1,-1), 16),
            ('BOTTOMPADDING', (0,0),(-1,-1), 16),
            ('LEFTPADDING',   (0,0),(-1,-1), 16),
            ('RIGHTPADDING',  (0,0),(-1,-1), 16),
            ('ROUNDEDCORNERS',[10]),
        ]))
        return card

    left  = [[make_card(n, s)] for n, s in all_comps[:3]]
    right = [[make_card(n, s)] for n, s in all_comps[3:]]
    right.append([Spacer(1, 1)]) # Balance the columns

    def vcol(rows, w):
        t = Table(rows, colWidths=[w])
        t.setStyle(TableStyle([
            ('TOPPADDING', (0,0),(-1,-1), 0),
            ('BOTTOMPADDING', (0,0),(-1,-2), 12),
            ('BOTTOMPADDING', (0,-1),(-1,-1), 0),
            ('LEFTPADDING', (0,0),(-1,-1), 0),
            ('RIGHTPADDING', (0,0),(-1,-1), 0),
        ]))
        return t

    comp_grid = Table([[vcol(left, 235), vcol(right, 235)]], colWidths=[245, 245])
    comp_grid.setStyle(TableStyle([
        ('VALIGN',       (0,0),(-1,-1), 'TOP'),
        ('TOPPADDING',   (0,0),(-1,-1), 0),
        ('BOTTOMPADDING',(0,0),(-1,-1), 0),
        ('LEFTPADDING',  (0,0),(-1,-1), 0),
        ('RIGHTPADDING', (0,0),(-1,-1), 0),
    ]))
    story.append(comp_grid)
    story.append(Spacer(1, 20))

    # ── ISSUES ────────────────────────────────────────────────────────
    story.append(SectionHeader('Diagnostic Fault Codes & Issues', RED if persist_issues else GREEN))
    story.append(Spacer(1, 10))

    if persist_issues:
        hdr_st = ps('issh', fontSize=9, textColor=WHITE, fontName='Helvetica-Bold')
        rows = [[
            Paragraph('ID', hdr_st),
            Paragraph('ISSUE DESCRIPTION', hdr_st),
            Paragraph('FREQUENCY', hdr_st),
        ]]
        for i, iss in enumerate(persist_issues, 1):
            cnt = issue_counts[iss]
            pct = round(cnt / n_results * 100)
            is_high = pct >= 50
            bg  = H('#fef2f2') if is_high else WHITE
            tx_clr = '#ef4444' if is_high else '#0f172a'
            rows.append([
                Paragraph(f'<b>{i:02d}</b>', ps(f'iss0{i}', fontSize=9, textColor=MUTED)),
                Paragraph(f'<b>{iss}</b>' if is_high else iss, ps(f'iss1{i}', fontSize=9, textColor=H(tx_clr))),
                StatusPill(f'{pct}%', RED if is_high else AMBER, width=45, height=16)
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
            IconShape('Rec', GREEN, 24),
            Paragraph('<b>NO PERSISTENT FAULTS DETECTED.</b> System operating within normal parameters.',
            ps('noiss', fontSize=10, textColor=GREEN, fontName='Helvetica-Bold'))
        ]], colWidths=[35, int(CW)-40])
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

    rec_rows = []
    for i, r in enumerate(recs, 1):
        rec_rows.append([
            IconShape('Rec', AMBER, 20),
            Paragraph(r, ps(f'rt{i}', fontSize=9.5, textColor=TEXT_D, fontName='Helvetica-Bold')),
        ])
    
    for r in rec_rows:
        t = Table([r], colWidths=[35, int(CW)-45])
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
    cw4 = (int(CW) - 30) // 4
    sum_data = [[
        Paragraph('READINGS ANALYSED', ps('sh0', fontSize=8, textColor=MUTED, fontName='Helvetica-Bold')),
        Paragraph('DATA QUALITY',      ps('sh1', fontSize=8, textColor=MUTED, fontName='Helvetica-Bold')),
        Paragraph('ANALYSIS ENGINE',   ps('sh2', fontSize=8, textColor=MUTED, fontName='Helvetica-Bold')),
        Paragraph('REPORT DATE',       ps('sh3', fontSize=8, textColor=MUTED, fontName='Helvetica-Bold')),
    ], [
        Paragraph(f'<b>{n_results}</b>', ps('sv0', fontSize=14, fontName='Helvetica-Bold', textColor=CYAN)),
        Paragraph(f'<b>{quality.upper()}</b>',   ps('sv1', fontSize=14, fontName='Helvetica-Bold', textColor=TEXT_D)),
        Paragraph('<b>VEXIS ML V1.0</b>',ps('sv2', fontSize=12, fontName='Helvetica-Bold', textColor=TEXT_D)),
        Paragraph(f'<b>{datetime.now().strftime("%d %b %Y")}</b>',  ps('sv3', fontSize=12,  fontName='Helvetica-Bold', textColor=TEXT_D)),
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

    pdoc.build(story)
    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes
