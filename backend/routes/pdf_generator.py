"""
Vexis — Premium Enterprise PDF Report Generator
Industry-level design: arc score ring, shadow cards, gradient bars,
dark header with tech pattern, cyan accent, proper typography.
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
    Flowable, Spacer, Paragraph, Table, TableStyle, KeepTogether
)

# ── Palette ──────────────────────────────────────────────────────────
def H(h): return rc.HexColor(h)

NAVY   = H('#0f172a'); SLATE  = H('#1e293b')
CYAN   = H('#0ea5e9'); GREEN  = H('#22c55e')
LIME   = H('#84cc16'); AMBER  = H('#f59e0b')
ORANGE = H('#f97316'); RED    = H('#ef4444')
LGRAY  = H('#f8fafc'); WHITE  = rc.white
BORDER = H('#e2e8f0'); TEXT   = H('#0f172a')
MUTED  = H('#64748b'); SUBTLE = H('#94a3b8')
SLATE2 = H('#334155'); WARM   = H('#fffbeb')

PAGE_W, PAGE_H = A4
MX = 19 * mm


def score_info(s):
    if s >= 90: return ('EXCELLENT', GREEN,  '#22c55e')
    if s >= 75: return ('GOOD',      LIME,   '#84cc16')
    if s >= 60: return ('FAIR',      AMBER,  '#f59e0b')
    if s >= 40: return ('POOR',      ORANGE, '#f97316')
    return              ('CRITICAL', RED,    '#ef4444')


def ps(name, **kw):
    return ParagraphStyle(name, **kw)


# ── Custom Flowables ──────────────────────────────────────────────────

class ScoreRing(Flowable):
    """Arc-based circular score ring."""
    def __init__(self, score, color, size=104):
        Flowable.__init__(self)
        self.score = min(max(float(score), 0), 100)
        self.color = color
        self.size  = size

    def wrap(self, *a): return (self.size, self.size)

    def draw(self):
        c  = self.canv
        sz = self.size
        cx = cy = sz / 2
        ro = sz / 2 - 7
        lw = 11

        # Shadow
        c.setFillColor(H('#dde3ec'))
        c.circle(cx + 1.5, cy - 1.5, ro + lw/2 + 1, fill=1, stroke=0)

        # Track ring
        c.setStrokeColor(H('#e8edf5'))
        c.setLineWidth(lw)
        c.setLineCap(1)
        p = c.beginPath()
        p.arc(cx-ro, cy-ro, cx+ro, cy+ro, startAng=90, extent=-360)
        c.drawPath(p, stroke=1, fill=0)

        # Progress arc
        if self.score > 0:
            c.setStrokeColor(self.color)
            c.setLineWidth(lw)
            c.setLineCap(1)
            p = c.beginPath()
            p.arc(cx-ro, cy-ro, cx+ro, cy+ro,
                  startAng=90, extent=-(self.score/100)*360)
            c.drawPath(p, stroke=1, fill=0)

        # White center
        c.setFillColor(WHITE)
        c.circle(cx, cy, ro - lw/2 - 1, fill=1, stroke=0)

        # Score text
        s = str(int(self.score))
        c.setFillColor(TEXT)
        c.setFont('Helvetica-Bold', 26)
        tw = c.stringWidth(s, 'Helvetica-Bold', 26)
        c.drawString(cx - tw/2, cy + 4, s)
        c.setFillColor(MUTED)
        c.setFont('Helvetica', 9)
        tw2 = c.stringWidth('/100', 'Helvetica', 9)
        c.drawString(cx - tw2/2, cy - 11, '/100')


class ProgressBar(Flowable):
    """Rounded progress bar with highlight."""
    def __init__(self, score, color, width=150, height=9):
        Flowable.__init__(self)
        self.score  = min(max(float(score), 0), 100)
        self.color  = color
        self.width  = width
        self.height = height

    def wrap(self, *a): return (self.width, self.height)

    def draw(self):
        h  = self.height
        c  = self.canv
        c.setFillColor(H('#f1f5f9'))
        c.roundRect(0, 0, self.width, h, h/2, fill=1, stroke=0)
        fw = max((self.score/100)*self.width, h)
        c.setFillColor(self.color)
        c.roundRect(0, 0, fw, h, h/2, fill=1, stroke=0)
        # Top highlight
        if fw > h * 2:
            c.saveState()
            c.setFillColor(WHITE)
            c.setFillAlpha(0.22)
            c.roundRect(h/2, h*0.55, fw - h, h*0.36, h*0.16, fill=1, stroke=0)
            c.restoreState()


class MiniBar(Flowable):
    def __init__(self, score, color, width=76, height=5):
        Flowable.__init__(self)
        self.score = min(max(float(score), 0), 100)
        self.color = color
        self.width = width
        self.height = height

    def wrap(self, *a): return (self.width, self.height)

    def draw(self):
        h = self.height
        self.canv.setFillColor(H('#374151'))
        self.canv.roundRect(0, 0, self.width, h, h/2, fill=1, stroke=0)
        fw = max((self.score/100)*self.width, h)
        self.canv.setFillColor(self.color)
        self.canv.roundRect(0, 0, fw, h, h/2, fill=1, stroke=0)


class SectionTitle(Flowable):
    def __init__(self, text, accent=None):
        Flowable.__init__(self)
        self.text   = text.upper()
        self.accent = accent or CYAN

    def wrap(self, aw, ah):
        self._w = aw
        return (aw, 26)

    def draw(self):
        c = self.canv
        w = self._w
        c.setFillColor(LGRAY)
        c.roundRect(0, 2, w, 22, 4, fill=1, stroke=0)
        c.setFillColor(self.accent)
        c.roundRect(0, 2, 5, 22, 2, fill=1, stroke=0)
        c.setFillColor(TEXT)
        c.setFont('Helvetica-Bold', 11)
        c.drawString(14, 9, self.text)


# ── Page callback ─────────────────────────────────────────────────────

def _make_page_fn(vehicle_name, vehicle_model, gen_date, n_rows, quality):
    def _draw(canvas, doc):
        canvas.saveState()
        w, h = doc.pagesize
        HDR = 46 * mm

        # Header background
        canvas.setFillColor(NAVY)
        canvas.rect(0, h - HDR, w, HDR, fill=1, stroke=0)

        # Subtle dot pattern
        canvas.setFillColor(SLATE)
        for row in range(7):
            for col in range(35):
                canvas.circle(col*7.6*mm, h - HDR + row*7.6*mm, 0.55, fill=1, stroke=0)

        # VEXIS logotype
        canvas.setFillColor(CYAN)
        canvas.setFont('Helvetica-Bold', 30)
        canvas.drawString(MX, h - 19*mm, 'VEXIS')

        canvas.setFillColor(SUBTLE)
        canvas.setFont('Helvetica', 8.5)
        canvas.drawString(MX, h - 25.5*mm, 'AI VEHICLE INTELLIGENCE PLATFORM')

        # Cyan separator
        canvas.setStrokeColor(CYAN)
        canvas.setLineWidth(0.8)
        canvas.line(MX, h - 29*mm, w - MX, h - 29*mm)

        # Vehicle name
        canvas.setFillColor(WHITE)
        canvas.setFont('Helvetica-Bold', 14)
        canvas.drawString(MX, h - 36*mm, vehicle_name.upper())
        if vehicle_model:
            canvas.setFillColor(SUBTLE)
            canvas.setFont('Helvetica', 9)
            canvas.drawString(MX, h - 41*mm, vehicle_model)

        # Right block
        rx = w - MX
        canvas.setFillColor(SUBTLE)
        canvas.setFont('Helvetica-Bold', 8.5)
        canvas.drawRightString(rx, h - 19*mm, 'VEHICLE HEALTH REPORT')
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(H('#64748b'))
        canvas.drawRightString(rx, h - 25*mm, f'Generated: {gen_date}')
        canvas.drawRightString(rx, h - 30.5*mm, f'Readings: {n_rows}  •  Quality: {quality}')
        canvas.drawRightString(rx, h - 36*mm,   'Powered by Vexis ML Engine')

        # Footer
        canvas.setFillColor(LGRAY)
        canvas.rect(0, 0, w, 11*mm, fill=1, stroke=0)
        canvas.setStrokeColor(BORDER)
        canvas.setLineWidth(0.4)
        canvas.line(MX, 11*mm, w - MX, 11*mm)
        canvas.setFillColor(MUTED)
        canvas.setFont('Helvetica', 7)
        canvas.drawString(MX, 3.8*mm,
            'Vexis AI Report  •  Automated ML analysis — consult a certified mechanic for official diagnosis.')
        canvas.drawRightString(w - MX, 3.8*mm, f'Page {doc.page}')
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
    gen_date = datetime.now().strftime('%d %b %Y  •  %H:%M')
    buf      = io.BytesIO()

    TOP_PAD = 46*mm + 8*mm
    BOT_PAD = 11*mm + 7*mm
    frame = Frame(MX, BOT_PAD, PAGE_W - 2*MX, PAGE_H - TOP_PAD - BOT_PAD,
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    page_fn = _make_page_fn(vehicle_name, vehicle_model, gen_date, n_results, quality)
    tmpl    = PageTemplate(id='p', frames=[frame], onPage=page_fn)
    pdoc    = BaseDocTemplate(buf, pagesize=A4, pageTemplates=[tmpl])

    CW = PAGE_W - 2*MX   # content width ≈ 173mm

    story = []

    # ── HERO: Score ring + info + mini components ─────────────────────
    ov_lbl, ov_clr, ov_hex = score_info(overall_score)

    ring = ScoreRing(overall_score, ov_clr, size=104)

    risk_hex = '#ef4444' if failure_risk else '#22c55e'
    risk_txt = '● AT RISK' if failure_risk else '● HEALTHY'

    score_block = Table([
        [Paragraph('OVERALL HEALTH SCORE',
                   ps('oht', fontSize=7.5, textColor=SUBTLE,
                      fontName='Helvetica-Bold', leading=11))],
        [Paragraph(f'<font size="30" color="{ov_hex}"><b>{int(overall_score)}</b></font>'
                   f'<font size="12" color="#94a3b8"> /100</font>',
                   ps('ohs', fontSize=12, leading=36))],
        [Paragraph(ov_lbl,
                   ps('ohl', fontSize=12, textColor=ov_clr,
                      fontName='Helvetica-Bold', leading=15))],
        [Spacer(1, 6)],
        [Paragraph(f'<font color="{risk_hex}"><b>{risk_txt}</b></font>',
                   ps('ohr', fontSize=9, leading=13))],
    ], colWidths=[130])
    score_block.setStyle(TableStyle([
        ('LEFTPADDING',  (0,0),(-1,-1), 0),
        ('RIGHTPADDING', (0,0),(-1,-1), 0),
        ('TOPPADDING',   (0,0),(-1,-1), 2),
        ('BOTTOMPADDING',(0,0),(-1,-1), 2),
    ]))

    # Mini component panel
    mini_comps = [
        ('ENGINE',     engine_score),
        ('FUEL',       fuel_score),
        ('EFFICIENCY', efficiency_score),
        ('DRIVING',    driving_score),
        ('THERMAL',    thermal_score),
    ]
    mini_rows = []
    for cname, cscore in mini_comps:
        lbl, clr, chx = score_info(cscore)
        mini_rows.append([
            Paragraph(cname, ps(f'mn{cname}', fontSize=7.5, textColor=SUBTLE, leading=10)),
            Paragraph(f'<font color="{chx}"><b>{int(cscore)}</b></font>',
                      ps(f'ms{cname}', fontSize=9, fontName='Helvetica-Bold',
                         leading=10, alignment=TA_RIGHT)),
            MiniBar(cscore, clr, width=68, height=5),
            Paragraph(f'<font color="{chx}"><b>{lbl}</b></font>',
                      ps(f'ml{cname}', fontSize=6.5, fontName='Helvetica-Bold',
                         leading=9, alignment=TA_RIGHT)),
        ])

    mini_tbl = Table(mini_rows, colWidths=[52, 22, 68, 48])
    mini_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,-1), SLATE),
        ('TOPPADDING',    (0,0),(-1,-1), 5),
        ('BOTTOMPADDING', (0,0),(-1,-1), 5),
        ('LEFTPADDING',   (0,0),(0,-1),  9),
        ('RIGHTPADDING',  (3,0),(3,-1),  9),
        ('LEFTPADDING',   (1,0),(3,-1),  4),
        ('RIGHTPADDING',  (0,0),(2,-1),  4),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ('LINEBELOW',     (0,0),(-1,-2), 0.3, H('#334155')),
        ('ROUNDEDCORNERS',[6]),
    ]))

    hero = Table([[ring, score_block, mini_tbl]], colWidths=[114, 140, 202])
    hero.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(1,0), WHITE),
        ('TOPPADDING',    (0,0),(-1,-1), 14),
        ('BOTTOMPADDING', (0,0),(-1,-1), 14),
        ('LEFTPADDING',   (0,0),(-1,-1), 12),
        ('RIGHTPADDING',  (0,0),(-1,-1), 12),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ('BOX',           (0,0),(-1,-1), 0.6, BORDER),
        ('LINEAFTER',     (0,0),(0,0),   0.5, BORDER),
        ('LINEAFTER',     (1,0),(1,0),   0.5, BORDER),
        ('ROUNDEDCORNERS',[8]),
    ]))
    story.append(hero)
    story.append(Spacer(1, 14))

    # ── COMPONENT CARDS ───────────────────────────────────────────────
    story.append(SectionTitle('Component Health Scores', CYAN))
    story.append(Spacer(1, 8))

    all_comps = [
        ('Engine',     engine_score),
        ('Fuel System',fuel_score),
        ('Efficiency', efficiency_score),
        ('Driving',    driving_score),
        ('Thermal',    thermal_score),
    ]

    def make_card(cname, cscore):
        lbl, clr, chx = score_info(cscore)
        bar = ProgressBar(cscore, clr, width=150, height=9)
        inner = Table([
            [Paragraph(f'<b>{cname}</b>',
                       ps(f'cc{cname}', fontSize=10, fontName='Helvetica-Bold',
                          textColor=TEXT, leading=13)),
             Paragraph(f'<font color="{chx}"><b>{int(cscore)}</b></font>',
                       ps(f'cs{cname}', fontSize=20, fontName='Helvetica-Bold',
                          leading=22, alignment=TA_RIGHT))],
            [Paragraph(f'<font color="{chx}"><b>{lbl}</b></font>',
                       ps(f'cl{cname}', fontSize=7.5, fontName='Helvetica-Bold',
                          textColor=clr, leading=10)), None],
            [bar, None],
        ], colWidths=[105, 50])
        inner.setStyle(TableStyle([
            ('LEFTPADDING',  (0,0),(-1,-1), 0),
            ('RIGHTPADDING', (0,0),(-1,-1), 0),
            ('TOPPADDING',   (0,0),(-1,-1), 2),
            ('BOTTOMPADDING',(0,0),(-1,-1), 2),
            ('VALIGN',       (0,0),(-1,-1), 'MIDDLE'),
            ('SPAN',         (0,2),(1,2)),
        ]))
        card = Table([[inner]], colWidths=[176])
        card.setStyle(TableStyle([
            ('BACKGROUND',    (0,0),(-1,-1), WHITE),
            ('BOX',           (0,0),(-1,-1), 0.6, BORDER),
            ('TOPPADDING',    (0,0),(-1,-1), 12),
            ('BOTTOMPADDING', (0,0),(-1,-1), 12),
            ('LEFTPADDING',   (0,0),(-1,-1), 14),
            ('RIGHTPADDING',  (0,0),(-1,-1), 14),
            ('ROUNDEDCORNERS',[7]),
        ]))
        return card

    left  = [[make_card(n, s)] for n, s in all_comps[:3]]
    right = [[make_card(n, s)] for n, s in all_comps[3:]]
    right.append([Spacer(1, 1)])

    def vcol(rows, w):
        t = Table(rows, colWidths=[w], rowHeights=None)
        t.setStyle(TableStyle([
            ('TOPPADDING',    (0,0),(-1,-1), 0),
            ('BOTTOMPADDING', (0,0),(-1,-2), 7),
            ('BOTTOMPADDING', (0,-1),(-1,-1), 0),
            ('LEFTPADDING',   (0,0),(-1,-1), 0),
            ('RIGHTPADDING',  (0,0),(-1,-1), 0),
        ]))
        return t

    comp_grid = Table([[vcol(left, 176), vcol(right, 176)]], colWidths=[186, 186])
    comp_grid.setStyle(TableStyle([
        ('VALIGN',       (0,0),(-1,-1), 'TOP'),
        ('TOPPADDING',   (0,0),(-1,-1), 0),
        ('BOTTOMPADDING',(0,0),(-1,-1), 0),
        ('LEFTPADDING',  (0,0),(-1,-1), 0),
        ('RIGHTPADDING', (0,0),(-1,-1), 0),
    ]))
    story.append(comp_grid)
    story.append(Spacer(1, 14))

    # ── ISSUES ────────────────────────────────────────────────────────
    story.append(SectionTitle('Detected Issues', RED if persist_issues else GREEN))
    story.append(Spacer(1, 8))

    if persist_issues:
        hdr_st = ps('issh', fontSize=8.5, textColor=WHITE,
                    fontName='Helvetica-Bold', leading=13)
        rows = [[
            Paragraph('#',               hdr_st),
            Paragraph('Issue Description', hdr_st),
            Paragraph('Frequency',       hdr_st),
        ]]
        for i, iss in enumerate(persist_issues, 1):
            cnt = issue_counts[iss]
            pct = round(cnt / n_results * 100)
            bg  = H('#fff5f5') if pct >= 50 else WHITE
            tx_clr = '#ef4444' if pct >= 50 else '#64748b'
            rows.append([
                Paragraph(str(i),  ps(f'iss0{i}', fontSize=8.5, alignment=TA_CENTER, leading=13)),
                Paragraph(iss,     ps(f'iss1{i}', fontSize=8.5, textColor=TEXT, leading=13)),
                Paragraph(f'{pct}%', ps(f'iss2{i}', fontSize=8.5, alignment=TA_CENTER,
                                        leading=13, textColor=H(tx_clr), fontName='Helvetica-Bold')),
            ])
        iss_tbl = Table(rows, colWidths=[22, 300, 56])
        iss_tbl.setStyle(TableStyle([
            ('BACKGROUND',    (0,0),(-1,0),  RED),
            ('FONTSIZE',      (0,0),(-1,-1), 8.5),
            ('ALIGN',         (0,0),(0,-1),  'CENTER'),
            ('ALIGN',         (2,0),(2,-1),  'CENTER'),
            ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
            ('TOPPADDING',    (0,0),(-1,-1), 7),
            ('BOTTOMPADDING', (0,0),(-1,-1), 7),
            ('LEFTPADDING',   (0,0),(-1,-1), 8),
            ('ROWBACKGROUNDS',(0,1),(-1,-1), [H('#fff5f5'), WHITE]),
            ('GRID',          (0,0),(-1,-1), 0.4, H('#fecaca')),
            ('ROUNDEDCORNERS',[5]),
        ]))
        story.append(iss_tbl)
    else:
        ok = Table([[Paragraph(
            '<b>No persistent issues detected across all OBD readings.</b>',
            ps('noiss', fontSize=9, textColor=GREEN, fontName='Helvetica-Bold', leading=14)
        )]], colWidths=[int(CW)])
        ok.setStyle(TableStyle([
            ('BACKGROUND',    (0,0),(-1,-1), H('#f0fdf4')),
            ('BOX',           (0,0),(-1,-1), 0.6, GREEN),
            ('TOPPADDING',    (0,0),(-1,-1), 10),
            ('BOTTOMPADDING', (0,0),(-1,-1), 10),
            ('LEFTPADDING',   (0,0),(-1,-1), 14),
            ('ROUNDEDCORNERS',[5]),
        ]))
        story.append(ok)

    story.append(Spacer(1, 14))

    # ── RECOMMENDATIONS ───────────────────────────────────────────────
    story.append(SectionTitle('Recommendations', AMBER))
    story.append(Spacer(1, 8))

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
        bg = WARM if i % 2 else WHITE
        rec_rows.append([
            Paragraph(f'<font color="#f59e0b"><b>{i}</b></font>',
                      ps(f'rn{i}', fontSize=10, fontName='Helvetica-Bold',
                         leading=14, alignment=TA_CENTER)),
            Paragraph(r, ps(f'rt{i}', fontSize=8.5, textColor=TEXT, leading=13)),
        ])
    rec_tbl = Table(rec_rows, colWidths=[26, int(CW)-26])
    rec_tbl.setStyle(TableStyle([
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ('TOPPADDING',    (0,0),(-1,-1), 8),
        ('BOTTOMPADDING', (0,0),(-1,-1), 8),
        ('LEFTPADDING',   (0,0),(-1,-1), 8),
        ('RIGHTPADDING',  (0,0),(-1,-1), 8),
        ('BOX',           (0,0),(-1,-1), 0.5, BORDER),
        ('LINEBELOW',     (0,0),(-1,-2), 0.4, BORDER),
        ('ROWBACKGROUNDS',(0,0),(-1,-1), [WARM, WHITE]),
        ('ROUNDEDCORNERS',[5]),
    ]))
    story.append(rec_tbl)
    story.append(Spacer(1, 14))

    # ── SCAN SUMMARY ──────────────────────────────────────────────────
    cw4 = int(CW) // 4
    sum_data = [[
        Paragraph('READINGS ANALYSED', ps('sh0', fontSize=7.5, textColor=MUTED, fontName='Helvetica-Bold', leading=11)),
        Paragraph('DATA QUALITY',      ps('sh1', fontSize=7.5, textColor=MUTED, fontName='Helvetica-Bold', leading=11)),
        Paragraph('ANALYSIS ENGINE',   ps('sh2', fontSize=7.5, textColor=MUTED, fontName='Helvetica-Bold', leading=11)),
        Paragraph('REPORT DATE',       ps('sh3', fontSize=7.5, textColor=MUTED, fontName='Helvetica-Bold', leading=11)),
    ], [
        Paragraph(f'<b>{n_results}</b>', ps('sv0', fontSize=13, fontName='Helvetica-Bold', textColor=TEXT, leading=17)),
        Paragraph(f'<b>{quality}</b>',   ps('sv1', fontSize=13, fontName='Helvetica-Bold', textColor=TEXT, leading=17)),
        Paragraph('<b>Vexis ML v1.0</b>',ps('sv2', fontSize=10, fontName='Helvetica-Bold', textColor=TEXT, leading=17)),
        Paragraph(f'<b>{gen_date}</b>',  ps('sv3', fontSize=9,  fontName='Helvetica-Bold', textColor=TEXT, leading=17)),
    ]]
    sum_tbl = Table(sum_data, colWidths=[cw4, cw4, cw4, cw4])
    sum_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,-1), LGRAY),
        ('BOX',           (0,0),(-1,-1), 0.5, BORDER),
        ('INNERGRID',     (0,0),(-1,-1), 0.4, BORDER),
        ('TOPPADDING',    (0,0),(-1,-1), 9),
        ('BOTTOMPADDING', (0,0),(-1,-1), 9),
        ('LEFTPADDING',   (0,0),(-1,-1), 12),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ('ROUNDEDCORNERS',[6]),
    ]))
    story.append(sum_tbl)

    pdoc.build(story)
    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes
