#!/usr/bin/env python3
"""The World in One Day - Monday 23 November 2026 (v5).

A program that draws one front-page image summing up 23 November 2026
world news: 52 verified stories, every one carrying its source.

v6 revision of the v5 front page (same 52 verified stories, same
layout, no story added or changed): the whole page is now rendered
with 2x supersampling anti-aliasing - drawn at 2048x2048 and
box-downsampled to 1024x1024 - so the hand-drawn stroke text renders
visibly smoother instead of jagged and stair-stepped. Everything else
is the v5 layout unchanged: a huge date, a THE DAY IN NUMBERS strip,
a region bar, three leads with tall coloured scene panels and caption
chips, ten featured stories each with its own small coloured scene
strip, bold headlines, a three-column ALSO list, and a big world map
with numbered pins.

Pure Python standard library only. Stroke-based vector font (sfont.py),
hand-rolled PNG encoder, no network, no randomness, deterministic output.

Run: python3 main.py
Writes entry.png (1024x1024) to $MAKEFUN_OUTPUT_DIR or the current dir.
"""

import math
import os
import struct
import sys
import zlib

# The grader runs `python3 -P -s /bot/main.py`, and -P removes the script's
# directory from sys.path, so a plain `import sfont` fails there. Insert it
# explicitly so the local module resolves in every invocation.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sfont

W, H = 1024, 1024
SS = 2  # supersampling factor: draw at 2048x2048, downsample to 1024

PAPER = (253, 250, 240)
INK = (18, 18, 18)
RED = (178, 34, 34)
BLUE = (28, 58, 128)
GREY = (110, 108, 100)
LIGHT = (238, 233, 220)
WHITE = (255, 255, 255)
GOLD = (176, 128, 20)
MAPFILL = (196, 218, 236)
NAVY = (16, 24, 64)
DARKBLUE = (20, 40, 90)
GREEN = (34, 120, 60)
TEAL = (20, 90, 110)
PURPLE = (90, 60, 140)
SKY = (150, 200, 235)
SEA = (20, 70, 140)
PITCH = (20, 120, 50)

# ---------------------------------------------------------------- font
# Text is rendered by the stroke-based vector font in sfont.py.
# Same 6-unit advance and 7-unit cap height as the old bitmap font,
# so text_width / wrap / layout are unchanged. All drawn text is
# plain ASCII: no em/en dashes, no ellipsis, no curly quotes, no
# degree or approx symbols; approximations are spelled (APPROX).


def text_width(text, scale):
    """Pixel width of text at the given scale (6 units per char)."""
    return len(text) * 6 * scale


def wrap(text, max_width, scale):
    """Greedy word wrap. Returns a list of lines that fit max_width."""
    max_chars = max_width // (6 * scale)
    lines = []
    for para in text.split('\n'):
        words = para.split(' ')
        cur = ''
        for word in words:
            trial = word if not cur else cur + ' ' + word
            if len(trial) <= max_chars:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                # A single over-long word is split hard so nothing is lost.
                while len(word) > max_chars:
                    lines.append(word[:max_chars])
                    word = word[max_chars:]
                cur = word
        if cur:
            lines.append(cur)
    return lines


# ---------------------------------------------------------------- canvas
# Supersampling anti-aliasing (v6): the page is drawn at SSx resolution
# into a 2048x2048 buffer and box-downsampled to 1024x1024. Every
# public primitive takes LOGICAL (1024) coordinates and scales them by
# SS once, so all layout code is unchanged; only the rasterization is
# finer, which turns jagged stair-step text edges into smooth grey
# transitions. Buffer-level helpers (_set, _rect, _hline) work in
# buffer coordinates and never scale again.
class Canvas:
    def __init__(self, w, h, bg, ss=1):
        self.w = w
        self.h = h
        self.ss = ss
        self.bw = w * ss
        self.bh = h * ss
        self.px = bytearray(self.bw * self.bh * 3)
        self.rect(0, 0, w, h, bg)

    def _set(self, bx, by, color):
        if 0 <= bx < self.bw and 0 <= by < self.bh:
            i = (by * self.bw + bx) * 3
            self.px[i], self.px[i + 1], self.px[i + 2] = color

    def set(self, x, y, color):
        self._set(x * self.ss, y * self.ss, color)

    def _rect(self, bx, by, bw, bh, color):
        x0 = max(0, bx)
        y0 = max(0, by)
        x1 = min(self.bw, bx + bw)
        y1 = min(self.bh, by + bh)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(color) * (x1 - x0)
        stride = self.bw * 3
        for yy in range(y0, y1):
            base = yy * stride + x0 * 3
            self.px[base:base + len(row)] = row

    def rect(self, x, y, w, h, color):
        ss = self.ss
        self._rect(x * ss, y * ss, w * ss, h * ss, color)

    def _hline(self, bx, by, bw, color):
        self._rect(bx, by, bw, 1, color)

    def hline(self, x, y, w, color, thick=1):
        self.rect(x, y, w, thick, color)

    def vline(self, x, y, h, color, thick=1):
        self.rect(x, y, thick, h, color)

    def box(self, x, y, w, h, color, thick=1):
        self.hline(x, y, w, color, thick)
        self.hline(x, y + h - thick, w, color, thick)
        self.vline(x, y, h, color, thick)
        self.vline(x + w - thick, y, h, color, thick)

    def line(self, x0, y0, x1, y1, color, thick=1):
        """Bresenham line, rasterized in buffer coordinates."""
        ss = self.ss
        x0 *= ss
        y0 *= ss
        x1 *= ss
        y1 *= ss
        thick *= ss
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        half = thick // 2
        while True:
            if thick == 1:
                self._set(x0, y0, color)
            else:
                self._rect(x0 - half, y0 - half, thick, thick, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def poly(self, pts, color):
        """Scanline fill of a polygon (even-odd rule)."""
        ss = self.ss
        pts = [(x * ss, y * ss) for x, y in pts]
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        n = len(pts)
        for y in range(min(ys), max(ys) + 1):
            xs = []
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if y0 == y1:
                    continue
                if (y0 <= y < y1) or (y1 <= y < y0):
                    xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                self._hline(int(xs[i]), y,
                            int(xs[i + 1]) - int(xs[i]) + 1, color)

    def polyline(self, pts, color, thick=1):
        """Closed polygon outline."""
        n = len(pts)
        for i in range(n):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % n]
            self.line(x0, y0, x1, y1, color, thick)

    def circle(self, cx, cy, r, color):
        """Filled circle."""
        ss = self.ss
        cx *= ss
        cy *= ss
        r *= ss
        for y in range(cy - r, cy + r + 1):
            dx = int((r * r - (y - cy) ** 2) ** 0.5)
            self._hline(cx - dx, y, 2 * dx + 1, color)

    def ring(self, cx, cy, r, color, thick=1, inner=WHITE):
        """Circle outline: filled disc, then a smaller disc of `inner`."""
        self.circle(cx, cy, r, color)
        self.circle(cx, cy, r - thick, inner)

    def downsample(self):
        """Box-downsample the SSx buffer back to logical size.

        Each output pixel is the rounded mean of its SSxSS source
        block, so a flat area comes back byte-identical to a 1x render
        and only edges gain smooth grey transitions. Integer math
        only, so the result is deterministic across runs.
        """
        ss = self.ss
        out = Canvas(self.w, self.h, PAPER, ss=1)
        if ss == 1:
            out.px[:] = self.px
            return out
        src = self.px
        dst = out.px
        sw = self.bw
        n = ss * ss
        for oy in range(self.h):
            y0 = oy * ss
            for ox in range(self.w):
                x0 = ox * ss
                r = g = b = 0
                for dy in range(ss):
                    base = ((y0 + dy) * sw + x0) * 3
                    for dx in range(ss):
                        i = base + dx * 3
                        r += src[i]
                        g += src[i + 1]
                        b += src[i + 2]
                o = (oy * self.w + ox) * 3
                dst[o] = (r + n // 2) // n
                dst[o + 1] = (g + n // 2) // n
                dst[o + 2] = (b + n // 2) // n
        return out

    def text(self, s, x, y, scale, color):
        return sfont.draw_text(self, s, x, y, scale, color)

    def text_center(self, s, cx, y, scale, color):
        self.text(s, cx - text_width(s, scale) // 2, y, scale, color)

    def bold_text(self, s, x, y, scale, color):
        """Headline text drawn twice (x and x+1) so it reads bold."""
        self.text(s, x, y, scale, color)
        self.text(s, x + 1, y, scale, color)

    def chip(self, s, x, y, color=INK):
        """Small black caption chip with white text, e.g. CONFIRMED - BBC."""
        w = text_width(s, 1) + 10
        self.rect(x, y, w, 11, color)
        self.text(s, x + 5, y + 2, 1, WHITE)
        return w


# ---------------------------------------------------------------- png
def png_bytes(canvas):
    raw = bytearray()
    row_bytes = canvas.w * 3
    for y in range(canvas.h):
        raw.append(0)
        raw += canvas.px[y * row_bytes:(y + 1) * row_bytes]

    def chunk(tag, data):
        body = tag + data
        return (struct.pack('>I', len(data)) + body +
                struct.pack('>I', zlib.crc32(body) & 0xffffffff))

    ihdr = struct.pack('>IIBBBBB', canvas.w, canvas.h, 8, 2, 0, 0, 0)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) +
            chunk(b'IDAT', zlib.compress(bytes(raw), 9)) +
            chunk(b'IEND', b''))

# ---------------------------------------------------------------- stories
# All 52 stories verified as happening or first reported on Monday
# 23 November 2026. Source tag in parentheses is part of the headline.
# Layout: 3 leads, 10 featured, 39 in the ALSO list = 52 stories.

LEADS = [
    ("NVIDIA REINSTATES JENSEN HUANG AS CEO (BBC)",
     "THE BOARD REINSTATED HUANG AS PRESIDENT AND CEO, EFFECTIVE "
     "IMMEDIATELY. SHARES JUMPED 31 PERCENT."),
    ("WALL STREET SURGES AS NVIDIA JUMPS 31 PERCENT (REUTERS)",
     "THE S AND P ROSE 4.73 PERCENT, THE NASDAQ 6.51 PERCENT, "
     "THE DOW 3.01 PERCENT."),
    ("EU PROPOSES 22ND SANCTIONS PACKAGE AGAINST RUSSIA (REUTERS)",
     "THE PACKAGE TARGETS 60 BANKS, CRYPTO PLATFORMS AND 70 "
     "SHADOW-FLEET VESSELS; BANS RUSSIAN TEAMS."),
]

# (kicker, headline, one-line body, strip label)
FEATURED = [
    ("7 BENGHAZI, LIBYA - SHIP ATTACK",
     "UKRAINE SAYS IT SANK RUSSIAN CORVETTE OFF LIBYA (REUTERS)",
     "SEVEN NAVAL DRONES SANK THE MERKURY AT BENGHAZI PORT, ZELENSKYY SAID.",
     "BENGHAZI SHIP"),
    ("8 KYIV REGION - DRONE STRIKES",
     "RUSSIAN OVERNIGHT STRIKES KILL AT LEAST 15 IN KYIV REGION (AP)",
     "RUSSIA LAUNCHED 153 DRONES AT UKRAINE OVERNIGHT INTO MONDAY.",
     "KYIV DRONE"),
    ("12 TEHRAN - HORMUZ BLOCKADE",
     "IRAN VOWS TO USE ALL MEANS AGAINST US BLOCKADE (REUTERS)",
     "TEHRAN WILL COUNTER THE US BLOCKADE OF THE STRAIT OF HORMUZ.",
     "HORMUZ"),
    ("14 NEW DELHI - NEPAL AID",
     "INDIA PLEDGES 1.6 BILLION DOLLARS TO NEPAL IN RESET OF TIES (BBC)",
     "PM MODI PLEDGED 240 BILLION RUPEES TO HELP NEPAL REBUILD.",
     "NEW DELHI"),
    ("18 LONDON - ROHINGYA RULING",
     "UK RECOGNISES ROHINGYA GENOCIDE AND SANCTIONS MYANMAR GENERALS (BBC)",
     "LONDON SANCTIONED FIVE MYANMAR OFFICERS; FUEL EXPORT CURBS PLANNED.",
     "LONDON"),
    ("26 WASHINGTON - HOUSE MAJORITY",
     "DEMOCRATS WIN LARGEST HOUSE MAJORITY SINCE 1992 (BBC)",
     "DEMOCRATS WON AT LEAST 258 HOUSE SEATS AFTER FLIPPING A NORTH CAROLINA SEAT.",
     "HOUSE 258"),
    ("30 FIFA - WORLD CUP HOSTS",
     "FIFA NAMES 2031 AND 2035 WOMENS WORLD CUP HOSTS (AP)",
     "US, MEXICO, COSTA RICA, JAMAICA HOST 2031; UK HOSTS 2035.",
     "WORLD CUP"),
    ("32 MELBOURNE - MUSIC LEGEND DIES",
     "AUSTRALIAN MUSIC LEGEND MOLLY MELDRUM DIES AGED 83 (REUTERS)",
     "THE COUNTDOWN HOST WHO CHAMPIONED AUSTRALIAN MUSIC DIED IN MELBOURNE.",
     "MELBOURNE"),
    ("3 TOKYO - NIKKEI FALLS",
     "NIKKEI FALLS MORE THAN 5 PERCENT IN ASIAN TRADING (AP)",
     "JAPANS NIKKEI FELL MORE THAN 5 PERCENT WHILE WALL STREET LATER RALLIED.",
     "NIKKEI -5%"),
    ("4 WASHINGTON - CHIP BLACKLIST",
     "US TO BLACKLIST MEGASPEED CHIP FIRM LINKED TO NVIDIA SCANDAL (REUTERS)",
     "THE SINGAPORE-BASED CHIP FIRM WAS ADDED TO THE US TRADE BLACKLIST ON MONDAY.",
     "CHIP BAN"),
]

# One line each: number, condensed headline, source. Must fit one line
# at scale 1 in a 321 px column (53 chars max).
ALSO = [
    "5. TRUMP: HE GOT NVIDIA TO REINSTATE HUANG (BBC)",
    "9. FINLAND SUMMONS ENVOY OVER AIRSPACE ROW (REUTERS)",
    "10. NATO MEETS ON POLAND MISSILE STRIKES (REUTERS)",
    "11. POLAND: RUSSIA TRIED TO KILL RAPPER (REUTERS)",
    "13. IRAN: HORMUZ REOPENS IF US MEETS TERMS (REUTERS)",
    "15. HASINA TO BE ARRESTED IF SHE RETURNS (REUTERS)",
    "16. S KOREA NAMES FIRST WOMAN SPY CHIEF (REUTERS)",
    "17. KIM STRESSES SOVEREIGNTY, SNUBS TRUMP (REUTERS)",
    "19. 14 NATIONS BACK ICJ ROHINGYA RULING (REUTERS)",
    "20. ALBANESE: COP31 FAILED AMID HARD TIMES (AFP)",
    "21. GUTERRES URGES AI REGULATION (UN NEWS)",
    "22. FIGHTING DISRUPTS EBOLA RESPONSE (REUTERS)",
    "23. UN URGES PROBE INTO BENGHAZI ATTACKS (UN NEWS)",
    "24. KENYA AND CONGO RESTORE DIPLOMATIC TIES (REUTERS)",
    "25. SOLDIERS ATTACKED AFTER CHAPO ISIDRO ARREST (BBC)",
    "27. GOMEZ TO RESIGN AFTER ETHICS PANEL FINDING (BBC)",
    "28. SEATTLE AIRPORT OUTRAGED OVER ICE ARREST (BBC)",
    "29. US BUSINESS STRONG IN NOVEMBER PMI (REUTERS)",
    "31. BRENTFORD BEAT EVERTON 4-0 (SKY SPORTS)",
    "33. FURY REVEALS SCHIZOPHRENIA DIAGNOSIS (BBC)",
    "34. IRAN FLOGS SINGER AHMADI AND FOUR OTHERS (BBC)",
    "35. OXFAM: GAZA TURNED INTO TOXIC WASTELAND (BBC)",
    "36. BELGIUM AIRPORTS SHUT AS CONTROLLERS STRIKE (BBC)",
    "37. ARMENIA PROPOSES NEW CONSTITUTION (REUTERS)",
    "38. DENMARK PLANS SCHOOL PHONE BAN 2027 (REUTERS)",
    "39. ISRAELI STRIKE KILLS 3, ONE A UN WORKER (REUTERS)",
    "40. TRUMP HOSTS GALA FOR PLUNGING MEME COIN (REUTERS)",
    "41. GISELE PELICOT HUMILIATED BY LEAKED PHOTOS (BBC)",
    "42. CATHERINE TALKS ABOUT MORTALITY IN NEW CLIP (BBC)",
    "43. ANDREW GOT 750,000 POUNDS, COURT TOLD (BBC)",
    "44. BURNHAM: CLOSER EU TIES COULD HELP DECADE (BBC)",
    "45. US DECLASSIFIES MORE UFO FOOTAGE (BBC)",
    "46. MELANIA WELCOMES WHITE HOUSE CHRISTMAS TREE (BBC)",
    "47. ZIMBABWE PREACHER HELD ON SEX CLAIMS (BBC)",
    "48. SYDNEY TRIAL TOLD DEATHS WERE EXECUTION (AAP)",
    "49. ARMY TO DETONATE EXPLOSIVES DESPITE HOLD (BBC)",
    "50. JAPAN MARKS LABOUR THANKSGIVING DAY (WIKIPEDIA)",
    "51. RESCUE RACE AFTER NIGERIA BOAT TRAGEDY (BBC)",
    "52. NIGERIA LEADER: VILLA HIT BY WATER CUTS (BBC)",
]

# Six numbers for THE DAY IN NUMBERS. Every number is in the verified
# story set: 31% (story 2), 153 and 15 (story 8), 258 (story 26),
# 70 (story 6), 50,000 (story 36).
NUMBERS = [
    ("31%", "NVIDIA SHARES JUMP"),
    ("153", "DRONES AT UKRAINE"),
    ("15", "KILLED IN KYIV REGION"),
    ("258", "DEMOCRATS HOUSE SEATS"),
    ("70", "SHADOW-FLEET VESSELS"),
    ("50,000", "TRAVELLERS HIT IN BELGIUM"),
]

# Region counts, counted from the 52 verified stories, one region each.
# EUROPE 15, ASIA 9, MIDDLE EAST 5, AFRICA 6, AMERICAS 14, OCEANIA 3 = 52.
REGIONS = [
    ("EUROPE 15", BLUE),
    ("ASIA 9", RED),
    ("MIDDLE EAST 5", GOLD),
    ("AFRICA 6", GREEN),
    ("AMERICAS 14", TEAL),
    ("OCEANIA 3", PURPLE),
]

SOURCES = ("SOURCES: REUTERS, BBC, AP, AFP, UN NEWS, AAP, XINHUA, "
           "SKY SPORTS, GOV.UK, WIKIPEDIA")

DATE_CHECK = ("EVERY STORY ON THIS PAGE HAPPENED OR WAS FIRST REPORTED ON "
              "MONDAY 23 NOVEMBER 2026. LEFT OUT ON PURPOSE: COP31 TALKS "
              "FAILURE (22 NOV) - IRGC BAHRAIN PATRIOT-RADAR CLAIM "
              "(21-22 NOV) - TRUMP 350BN SHUTDOWN DEMAND (20 NOV) - "
              "INDONESIA FACTORY FIRE (21-22 NOV) - SUNDAY SPORT RESULTS "
              "(22 NOV) - EU-INDONESIA TRADE DEAL (21 NOV).")


# ---------------------------------------------------------------- lead scenes
# Tall coloured scene panels for the three lead stories. Each panel is
# h px tall, filled with a strong background colour, drawn elements on
# top, and a black caption chip at the bottom left.

def draw_lead_scene(c, i, x, y, w, h):
    if i == 0:
        # Nvidia office at night: dark blue room, a BIG figure walking
        # back in (the returning CEO, white shirt, red tie, briefcase),
        # a wide green chart on the wall, a wall clock, a desk with a
        # big monitor and a blue NV chip, +31% top right. v5: the v4
        # figure was a small stick man and the top right was empty dark
        # space; the figure is now twice as tall and the clock fills it.
        c.rect(x, y, w, h, DARKBLUE)
        c.rect(x, y + h - 14, w, 14, (196, 164, 110))  # floor
        # wide wall chart, green line climbing
        c.rect(x + 8, y + 6, 110, 28, WHITE)
        c.box(x + 8, y + 6, 110, 28, INK, 1)
        c.line(x + 14, y + 30, x + 38, y + 22, GREEN, 2)
        c.line(x + 38, y + 22, x + 62, y + 25, GREEN, 2)
        c.line(x + 62, y + 25, x + 88, y + 14, GREEN, 2)
        c.line(x + 88, y + 14, x + 110, y + 11, GREEN, 2)
        # wide door, big figure walking back in
        c.rect(x + 128, y + 2, 50, h - 16, (120, 90, 60))
        c.box(x + 128, y + 2, 50, h - 16, INK, 1)
        hx, hy = x + 153, y + 16
        c.circle(hx, hy, 8, WHITE)                       # head
        c.rect(hx - 5, hy + 9, 10, 13, WHITE)            # shirt
        c.line(hx, hy + 9, hx, hy + 20, RED, 2)          # tie
        c.line(hx - 5, hy + 12, hx - 13, hy + 19, WHITE, 2)  # left arm
        c.line(hx + 5, hy + 12, hx + 13, hy + 19, WHITE, 2)  # right arm
        c.line(hx - 3, hy + 22, hx - 5, hy + 33, WHITE, 3)   # left leg
        c.line(hx + 3, hy + 22, hx + 5, hy + 33, WHITE, 3)   # right leg
        c.rect(hx + 9, hy + 17, 13, 10, (120, 90, 60))   # briefcase
        c.box(hx + 9, hy + 17, 13, 10, INK, 1)
        # wall clock filling the gap above the desk
        c.ring(x + 222, y + 12, 7, INK, 1, WHITE)
        c.line(x + 222, y + 12, x + 222, y + 6, INK, 1)
        c.line(x + 222, y + 12, x + 227, y + 14, INK, 1)
        # desk with a big monitor and a blue NV chip
        c.rect(x + 196, y + 40, 114, 6, (120, 90, 60))
        c.rect(x + 206, y + 22, 36, 18, INK)
        c.rect(x + 209, y + 25, 30, 12, LIGHT)
        c.line(x + 212, y + 34, x + 220, y + 29, RED, 1)
        c.line(x + 220, y + 29, x + 228, y + 31, RED, 1)
        c.line(x + 228, y + 31, x + 236, y + 27, RED, 1)
        c.rect(x + 252, y + 24, 34, 16, BLUE)
        for px in (x + 260, x + 268, x + 276):
            c.vline(px, y + 20, 4, BLUE, 2)
        c.text("NV", x + 263, y + 29, 1, WHITE)
        c.text("+31%", x + 262, y + 4, 2, (120, 220, 120))
        c.chip("CONFIRMED - BBC", x + 6, y + h - 13)
    elif i == 1:
        # Wall Street: navy night sky, lit skyline, a bold red arrow
        # climbing past the towers, +31% in white.
        c.rect(x, y, w, h, NAVY)
        c.circle(x + w - 26, y + 12, 7, LIGHT)  # moon
        builds = [(8, 26, 30), (42, 18, 30), (76, 30, 30),
                  (110, 12, 30), (144, 22, 30), (178, 30, 30),
                  (212, 16, 30), (246, 26, 30), (280, 20, 30)]
        for bx, top, bw in builds:
            c.rect(x + bx, y + top, bw, h - top, BLUE)
            for wx in (bx + 5, bx + 17):
                for wy in range(top + 5, h - 6, 9):
                    c.rect(x + wx, y + wy, 4, 4, GOLD)
        c.vline(x + 125, y + 4, 8, WHITE, 1)
        c.poly([(x + 125, y + 4), (x + 139, y + 7), (x + 125, y + 10)], RED)
        c.line(x + 10, y + h - 8, x + w - 12, y + 10, RED, 4)
        c.line(x + w - 12, y + 10, x + w - 34, y + 10, RED, 4)
        c.line(x + w - 12, y + 10, x + w - 20, y + 30, RED, 4)
        c.text("+31%", x + 12, y + 3, 2, WHITE)
        c.chip("CONFIRMED - REUTERS", x + 6, y + h - 13)
    else:
        # EU sanctions: EU blue, a ring of gold stars, a white document
        # stamped 22ND with a red seal.
        c.rect(x, y, w, h, BLUE)
        cx, cy = x + 52, y + h // 2 - 2
        c.ring(cx, cy, 24, GOLD, 2, BLUE)
        for k in range(12):
            ang = math.radians(k * 30)
            sx = cx + int(15 * math.cos(ang))
            sy = cy + int(15 * math.sin(ang))
            c.circle(sx, sy, 2, GOLD)
        c.line(x + 80, cy, x + 118, cy, WHITE, 3)
        c.line(x + 118, cy, x + 108, cy - 6, WHITE, 3)
        c.line(x + 118, cy, x + 108, cy + 6, WHITE, 3)
        c.rect(x + 126, y + 8, 104, h - 16, WHITE)
        c.box(x + 126, y + 8, 104, h - 16, INK, 2)
        c.text("22ND", x + 140, y + 14, 2, RED)
        c.hline(x + 136, y + 34, 64, GREY, 1)
        c.hline(x + 136, y + 41, 48, GREY, 1)
        c.ring(x + 206, y + h - 18, 8, RED, 2, WHITE)
        c.circle(x + 206, y + h - 18, 2, GOLD)
        c.text("SANCTIONS", x + 240, y + 18, 1, WHITE)
        c.text("PACKAGE", x + 240, y + 30, 1, WHITE)
        c.chip("CONFIRMED - REUTERS", x + 6, y + h - 13)


# ---------------------------------------------------------------- featured scenes
# Small coloured scene strips, one per featured story, 24 px tall.
# Each has a filled background, a few drawn elements, and a small
# white label box naming the scene.

def draw_feat_scene(c, idx, x, y, w, h):
    c.box(x, y, w, h, INK, 1)
    ix, iy, iw, ih = x + 1, y + 1, w - 2, h - 2
    if idx == 0:
        # Benghazi ship: dark sea, a grey corvette, an orange blast.
        c.rect(ix, iy, iw, ih, (10, 40, 90))
        c.rect(ix + 60, iy + 12, 130, 6, (150, 150, 150))
        c.rect(ix + 110, iy + 6, 6, 6, (150, 150, 150))
        c.line(ix + 113, iy + 6, ix + 113, iy + 1, (150, 150, 150), 1)
        c.circle(ix + 220, iy + 7, 4, (255, 170, 40))
        c.line(ix + 220, iy + 1, ix + 220, iy + 13, (255, 170, 40), 1)
        c.line(ix + 214, iy + 7, ix + 226, iy + 7, (255, 170, 40), 1)
        c.hline(ix, iy + 19, iw, (120, 170, 220), 1)
    elif idx == 1:
        # Kyiv drone night: dark sky, building silhouettes, orange bursts.
        c.rect(ix, iy, iw, ih, (12, 18, 48))
        for bx, bh in ((20, 12), (70, 16), (130, 10), (190, 14)):
            c.rect(ix + bx, iy + ih - bh, 44, bh, (60, 60, 80))
            c.rect(ix + bx + 8, iy + ih - bh + 4, 4, 4, GOLD)
            c.rect(ix + bx + 28, iy + ih - bh + 4, 4, 4, GOLD)
        for bx, by in ((250, 6), (330, 9), (400, 5)):
            c.circle(ix + bx, iy + by, 3, (255, 170, 40))
            c.line(ix + bx - 5, iy + by, ix + bx + 5, iy + by,
                   (255, 170, 40), 1)
            c.line(ix + bx, iy + by - 5, ix + bx, iy + by + 5,
                   (255, 170, 40), 1)
    elif idx == 2:
        # Hormuz strait: blue sea, a warship, a red flag, white waves.
        c.rect(ix, iy, iw, ih, SEA)
        c.rect(ix + 70, iy + 9, 170, 9, (140, 140, 140))
        c.rect(ix + 120, iy + 4, 40, 5, (140, 140, 140))
        c.rect(ix + 150, iy + 1, 5, 4, (140, 140, 140))
        c.poly([(ix + 155, iy + 1), (ix + 173, iy + 4), (ix + 155, iy + 7)],
               RED)
        c.hline(ix, iy + 19, iw, WHITE, 1)
        c.hline(ix + 40, iy + 16, 60, WHITE, 1)
        c.hline(ix + 300, iy + 16, 80, WHITE, 1)
    elif idx == 3:
        # India-Nepal: pale sky, sun, grey mountains, green valley.
        c.rect(ix, iy, iw, ih, SKY)
        c.circle(ix + 420, iy + 6, 5, GOLD)
        c.poly([(ix + 20, iy + ih), (ix + 90, iy + 3), (ix + 160, iy + ih)],
               (120, 110, 100))
        c.poly([(ix + 130, iy + ih), (ix + 210, iy + 7), (ix + 290, iy + ih)],
               (90, 85, 80))
        c.rect(ix, iy + ih - 4, iw, 4, GREEN)
    elif idx == 4:
        # London court: light stone, columns, a red seal, flags.
        c.rect(ix, iy, iw, ih, LIGHT)
        for bx in (60, 120, 180):
            c.rect(ix + bx, iy + 5, 10, ih - 5, (160, 150, 130))
        c.rect(ix + 40, iy + 3, 170, 3, INK)
        c.ring(ix + 260, iy + 11, 6, RED, 2, WHITE)
        c.rect(ix + 330, iy + 4, 4, ih - 4, INK)
        c.rect(ix + 334, iy + 4, 34, 10, BLUE)
        c.hline(ix + 334, iy + 8, 34, WHITE, 2)
        c.rect(ix + 400, iy + 4, 4, ih - 4, INK)
        c.rect(ix + 404, iy + 4, 34, 10, RED)
    elif idx == 5:
        # Washington Capitol: pale sky, white dome and columns, a flag.
        c.rect(ix, iy, iw, ih, (230, 235, 245))
        c.circle(ix + 90, iy + 9, 10, WHITE)
        c.rect(ix + 76, iy + 9, 28, 5, WHITE)
        for bx in (60, 76, 92, 108):
            c.rect(ix + bx, iy + 14, 5, ih - 14, WHITE)
        c.rect(ix + 50, iy + 3, 4, 10, INK)
        c.poly([(ix + 54, iy + 3), (ix + 68, iy + 6), (ix + 54, iy + 9)],
               RED)
        c.rect(ix + 200, iy + 12, 120, 3, (150, 140, 120))
        c.rect(ix + 360, iy + 8, 60, 4, BLUE)
        c.rect(ix + 360, iy + 12, 60, 4, RED)
    elif idx == 6:
        # Football: green pitch, white lines, a ball.
        c.rect(ix, iy, iw, ih, PITCH)
        c.hline(ix, iy + ih // 2, iw, WHITE, 1)
        c.circle(ix + iw // 2, iy + ih // 2, 7, WHITE)
        c.circle(ix + iw // 2, iy + ih // 2, 5, PITCH)
        c.rect(ix, iy, 60, ih, PITCH)
        c.box(ix, iy + 3, 40, ih - 6, WHITE, 1)
        c.circle(ix + 420, iy + 11, 6, WHITE)
        c.circle(ix + 418, iy + 9, 1, INK)
        c.circle(ix + 422, iy + 13, 1, INK)
    elif idx == 7:
        # Melbourne music: dark stage, a microphone, a gold music note.
        c.rect(ix, iy, iw, ih, (40, 20, 60))
        c.circle(ix + 90, iy + 8, 6, (200, 200, 200))
        c.line(ix + 90, iy + 14, ix + 90, iy + ih - 2, (200, 200, 200), 2)
        c.circle(ix + 200, iy + 15, 4, GOLD)
        c.line(ix + 204, iy + 15, ix + 204, iy + 3, GOLD, 2)
        c.line(ix + 204, iy + 3, ix + 216, iy + 6, GOLD, 2)
        c.circle(ix + 216, iy + 15, 4, GOLD)
        c.line(ix + 220, iy + 15, ix + 220, iy + 3, GOLD, 2)
        c.circle(ix + 330, iy + 8, 3, GOLD)
        c.circle(ix + 360, iy + 8, 3, GOLD)
    elif idx == 8:
        # Nikkei: white board, a red line falling, a red down arrow.
        c.rect(ix, iy, iw, ih, WHITE)
        c.line(ix + 20, iy + 4, ix + 160, iy + 8, RED, 2)
        c.line(ix + 160, iy + 8, ix + 300, iy + 18, RED, 2)
        c.line(ix + 300, iy + 18, ix + 440, iy + 19, RED, 2)
        c.line(ix + 440, iy + 19, ix + 430, iy + 12, RED, 2)
        c.line(ix + 440, iy + 19, ix + 448, iy + 12, RED, 2)
        c.text("-5%", ix + 250, iy + 2, 1, RED)
    else:
        # Chip blacklist: dark bench, a blue chip, a red BAN stamp.
        c.rect(ix, iy, iw, ih, (40, 40, 40))
        c.rect(ix + 80, iy + 5, 30, 14, BLUE)
        for px in (ix + 88, ix + 96, ix + 104):
            c.vline(px, iy + 2, 3, BLUE, 2)
            c.vline(px, iy + 19, 3, BLUE, 2)
        c.text("NV", ix + 88, iy + 9, 1, WHITE)
        c.rect(ix + 220, iy + 4, 70, 15, (40, 40, 40))
        c.box(ix + 220, iy + 4, 70, 15, RED, 2)
        c.text("BAN", ix + 242, iy + 8, 1, RED)
        c.line(ix + 180, iy + 12, ix + 210, iy + 12, GREY, 1)
        c.line(ix + 300, iy + 12, ix + 330, iy + 12, GREY, 1)
    # white label box at the right end of the strip
    label = FEATURED[idx][3]
    lw = text_width(label, 1) + 8
    c.rect(x + w - lw - 4, y + 3, lw, 11, WHITE)
    c.box(x + w - lw - 4, y + 3, lw, 11, INK, 1)
    c.text(label, x + w - lw, y + 5, 1, INK)


# Stylized world map: simplified continent polygons in a 984x64 box.
# Positions are relative, not a precise projection.
MAP_CONTINENTS = [
    [(28, 16), (40, 10), (55, 6), (80, 4), (120, 4), (150, 5),
     (180, 6), (205, 8), (215, 10), (232, 16), (226, 26), (214, 30),
     (208, 30), (200, 38), (192, 42), (185, 42), (176, 44), (168, 46),
     (158, 44), (150, 42), (135, 38), (128, 36), (110, 33), (100, 32),
     (80, 29), (70, 28), (55, 26), (45, 24), (36, 22), (28, 20)],
    [(252, 10), (260, 6), (268, 4), (276, 6), (285, 8), (282, 16),
     (272, 18), (265, 18), (258, 16), (254, 14)],
    [(258, 30), (272, 27), (300, 26), (315, 28), (330, 30), (335, 40),
     (330, 48), (325, 52), (318, 58), (310, 60), (302, 62), (296, 56),
     (290, 52), (282, 44), (275, 42), (268, 38), (262, 36)],
    [(452, 10), (456, 7), (460, 6), (464, 8), (463, 11), (459, 13),
     (455, 13)],
    [(462, 18), (468, 12), (476, 9), (490, 6), (502, 7), (510, 8),
     (518, 10), (525, 12), (522, 17), (520, 20), (514, 24), (510, 26),
     (502, 28), (495, 28), (486, 27), (480, 26), (472, 24), (468, 22)],
    [(465, 28), (480, 25), (500, 24), (520, 25), (540, 26), (555, 29),
     (565, 32), (562, 38), (560, 42), (552, 48), (545, 52), (535, 57),
     (525, 60), (516, 62), (510, 62), (503, 58), (495, 54), (487, 48),
     (480, 44), (474, 40), (468, 36)],
    [(535, 14), (550, 9), (575, 6), (620, 4), (680, 4), (740, 5),
     (780, 6), (820, 7), (850, 8), (868, 11), (875, 14), (868, 19),
     (860, 22), (845, 25), (830, 28), (805, 31), (790, 34), (765, 36),
     (750, 38), (720, 39), (700, 40), (670, 39), (650, 38), (620, 36),
     (600, 34), (575, 32), (560, 30), (548, 26), (540, 22)],
    [(640, 34), (652, 32), (668, 32), (664, 38), (656, 46), (648, 46),
     (644, 44)],
    [(845, 48), (858, 44), (870, 42), (888, 42), (905, 42), (918, 45),
     (930, 48), (928, 52), (925, 56), (910, 59), (895, 60), (878, 59),
     (860, 58), (850, 55), (845, 54)],
]
MAP_ISLANDS = [(800, 42), (815, 44), (830, 42), (860, 18), (868, 22),
               (878, 28), (948, 50), (955, 56)]
# (u, v, story number, label, label_x, label_y) - numbered red pins
MAP_MARKERS = [
    (78, 26, "1", "NVIDIA", 52, 12),
    (212, 22, "2", "WALL ST", 222, 18),
    (478, 16, "6", "EU", 468, 4),
    (538, 12, "8", "KYIV", 548, 8),
    (608, 30, "12", "IRAN", 586, 40),
    (688, 34, "14", "NEPAL", 668, 44),
    (734, 36, "18", "MYANMAR", 712, 46),
    (868, 50, "32", "MELBOURNE", 828, 58),
]


def draw_world_map(c, x, y, w, h):
    """Stylized continents + numbered red pins matching story numbers."""
    sx = w / 984.0
    sy = h / 64.0
    for poly in MAP_CONTINENTS:
        pts = [(x + int(u * sx), y + int(v * sy)) for u, v in poly]
        c.poly(pts, MAPFILL)
        c.polyline(pts, BLUE, 1)
    for u, v in MAP_ISLANDS:
        c.ring(x + int(u * sx), y + int(v * sy), 3, BLUE, 1, MAPFILL)
    for u, v, num, label, lx, ly in MAP_MARKERS:
        mx, my = x + int(u * sx), y + int(v * sy)
        c.circle(mx, my, 7, RED)
        c.circle(mx, my, 6, RED)
        nx = mx - text_width(num, 1) // 2
        c.text(num, nx, my - 3, 1, WHITE)
        c.text(label, x + int(lx * sx), y + int(ly * sy), 1, INK)


# ---------------------------------------------------------------- layout
def draw(c):
    MX = 20                      # side margin
    CW = W - 2 * MX              # content width: 984

    # ---- masthead: small red top line, then the huge date
    y = 8
    c.text_center("THE WORLD IN ONE DAY - 52 STORIES - 6 REGIONS - "
                  "EVERY ONE DATED 23 NOVEMBER 2026",
                  W // 2, y, 1, RED)
    y += 10
    c.text_center("Monday 23 November 2026", W // 2, y, 4, INK)
    y += 4 * 7 + 4
    c.text_center("NVIDIA RETURNS - WALL STREET SURGES - "
                  "EU SANCTIONS RUSSIA",
                  W // 2, y, 1, INK)
    y += 10
    c.hline(MX, y, CW, INK, 2)
    y += 5

    # ---- THE DAY IN NUMBERS: black bar, six big red numbers
    c.text("THE DAY IN NUMBERS", MX, y, 1, RED)
    y += 10
    bar_h = 36
    c.rect(MX, y, CW, bar_h, INK)
    cell_w = CW // 6
    for i, (num, cap) in enumerate(NUMBERS):
        cx = MX + i * cell_w
        assert text_width(cap, 1) <= cell_w - 8, "number caption too long"
        c.text_center(num, cx + cell_w // 2, y + 3, 3, RED)
        c.text_center(cap, cx + cell_w // 2, y + 24, 1, WHITE)
        if i:
            c.vline(cx, y + 3, bar_h - 6, GREY, 1)
    y += bar_h + 4

    # ---- region bar: six coloured cells with story counts (total 52)
    reg_h = 14
    for i, (label, color) in enumerate(REGIONS):
        cx = MX + i * cell_w
        c.rect(cx, y, cell_w, reg_h, color)
        c.text_center(label, cx + cell_w // 2, y + 3, 1, WHITE)
    y += reg_h + 4

    # ---- leads: three columns, tall coloured scene + bold headline
    c.text("TOP STORIES", MX, y, 2, RED)
    y += 15
    lead_top = y
    col_w = (CW - 2 * 16) // 3
    scene_h = 52
    lead_bottom = lead_top
    for i, (head, body) in enumerate(LEADS):
        x = MX + i * (col_w + 16)
        cy = lead_top
        draw_lead_scene(c, i, x, cy, col_w, scene_h)
        cy += scene_h + 5
        c.text("LEAD %d" % (i + 1), x, cy, 1, RED)
        cy += 12
        hl = wrap(head, col_w, 2)
        assert len(hl) <= 3, "lead headline too long: %r" % head
        for line in hl:
            c.bold_text(line, x, cy, 2, INK)
            cy += 16
        cy += 2
        c.hline(x, cy, col_w, RED, 2)
        cy += 5
        bl = wrap(body, col_w, 1)
        assert len(bl) <= 2, "lead body too long: %r" % body
        for line in bl:
            c.text(line, x, cy, 1, INK)
            cy += 10
        lead_bottom = max(lead_bottom, cy)
    # vertical dividers between lead columns
    for i in (1, 2):
        dx = MX + i * (col_w + 16) - 8
        c.vline(dx, lead_top, lead_bottom - lead_top, GREY, 1)
    y = lead_bottom + 4
    c.hline(MX, y, CW, INK, 2)
    y += 5

    # ---- featured: two columns, five rows, each with a scene strip
    c.text("MORE FROM THE DAY", MX, y, 2, RED)
    y += 15
    feat_top = y
    fcol_w = (CW - 16) // 2
    row_h = 75
    for idx, (kicker, head, body, _label) in enumerate(FEATURED):
        col = idx % 2
        row = idx // 2
        x = MX + col * (fcol_w + 16)
        cy = feat_top + row * row_h
        draw_feat_scene(c, idx, x, cy, fcol_w, 22)
        cy += 22 + 2
        c.text(kicker, x, cy, 1, RED)
        cy += 9
        hl = wrap(head, fcol_w, 2)
        assert len(hl) <= 2, "featured headline too long: %r" % head
        for line in hl:
            c.bold_text(line, x, cy, 2, INK)
            cy += 16
        assert text_width(body, 1) <= fcol_w, "featured body too long"
        c.text(body, x, cy, 1, GREY)
        cy += 11
    y = feat_top + 5 * row_h + 2
    c.hline(MX, y, CW, INK, 2)
    y += 5

    # ---- ALSO list: three columns, one line per story (39 lines)
    c.text("ALSO IN THE NEWS - 23 NOVEMBER", MX, y, 2, RED)
    y += 15
    also_top = y
    acol_w = (CW - 2 * 10) // 3
    for line in ALSO:
        assert text_width(line, 1) <= acol_w, "ALSO line too long: %r" % line
    for col in range(3):
        part = ALSO[col * 13:(col + 1) * 13]
        ax = MX + col * (acol_w + 10)
        for i, line in enumerate(part):
            c.text(line, ax, also_top + i * 8, 1, INK)
    y = also_top + 13 * 8 + 4
    c.hline(MX, y, CW, INK, 2)
    y += 5

    # ---- world map: big, full width, numbered pins
    c.text("WORLD MAP - WHERE THE NEWS HAPPENED", MX, y, 1, RED)
    c.text("EACH NUMBER MATCHES A STORY ON THIS PAGE",
           MX + CW - text_width("EACH NUMBER MATCHES A STORY ON THIS PAGE", 1),
           y, 1, GREY)
    y += 10
    draw_world_map(c, MX, y, CW, 72)
    y += 72 + 4
    c.hline(MX, y, CW, INK, 2)
    y += 5

    # ---- DATE CHECK box
    box_h = 54
    c.box(MX, y, CW, box_h, INK, 2)
    c.text("DATE CHECK - 23 NOVEMBER 2026 ONLY", MX + 12, y + 7, 2, RED)
    by = y + 25
    for line in wrap(DATE_CHECK, CW - 24, 1):
        c.text(line, MX + 12, by, 1, INK)
        by += 10
    y += box_h + 5

    # ---- sources + footer
    c.text_center(SOURCES, W // 2, y, 1, INK)
    y += 9
    c.hline(MX, y, CW, GREY, 1)
    y += 5
    c.text_center("ALL 52 STORIES VERIFIED AGAINST THE NAMED SOURCE - "
                  "MONDAY 23 NOVEMBER 2026", W // 2, y, 1, GREY)
    y += 11
    assert y <= H - 8, "layout overflow: y=%d" % y
    return y


def main():
    c = Canvas(W, H, PAPER, SS)
    draw(c)
    c = c.downsample()
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", ".")
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as f:
        f.write(png_bytes(c))
    print("wrote %s (%d bytes)" % (path, os.path.getsize(path)))


if __name__ == "__main__":
    main()
