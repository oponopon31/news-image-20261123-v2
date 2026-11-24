#!/usr/bin/env python3
"""The World in One Day - Monday 23 November 2026.

A program that draws one front-page image summing up 23 November 2026
world news: 52 verified stories, every one carrying its source.

Pure Python standard library only. Stroke-based vector font (sfont.py), hand-rolled
PNG encoder, no network, no randomness, deterministic output.

Run: python3 main.py
Writes entry.png (1024x1024) to $MAKEFUN_OUTPUT_DIR or the current dir.
"""

import math
import os
import struct
import zlib

import sfont

W, H = 1024, 1024

PAPER = (253, 250, 240)
INK = (18, 18, 18)
RED = (178, 34, 34)
BLUE = (28, 58, 128)
GREY = (110, 108, 100)
LIGHT = (238, 233, 220)
WHITE = (255, 255, 255)
GOLD = (176, 128, 20)
MAPFILL = (196, 218, 236)

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
class Canvas:
    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.px = bytearray(w * h * 3)
        self.rect(0, 0, w, h, bg)

    def set(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i], self.px[i + 1], self.px[i + 2] = color

    def rect(self, x, y, w, h, color):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        r, g, b = color
        for yy in range(y0, y1):
            base = (yy * self.w + x0) * 3
            for xx in range(x0, x1):
                i = base + (xx - x0) * 3
                self.px[i], self.px[i + 1], self.px[i + 2] = r, g, b

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
        """Bresenham line."""
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            if thick == 1:
                self.set(x0, y0, color)
            else:
                self.rect(x0 - thick // 2, y0 - thick // 2,
                          thick, thick, color)
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
                self.hline(int(xs[i]), y,
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
        for y in range(cy - r, cy + r + 1):
            dx = int((r * r - (y - cy) ** 2) ** 0.5)
            self.hline(cx - dx, y, 2 * dx + 1, color)

    def ring(self, cx, cy, r, color, thick=1, inner=WHITE):
        """Circle outline: filled disc, then a smaller disc of `inner`."""
        self.circle(cx, cy, r, color)
        self.circle(cx, cy, r - thick, inner)

    def text(self, s, x, y, scale, color):
        return sfont.draw_text(self, s, x, y, scale, color)

    def text_center(self, s, cx, y, scale, color):
        self.text(s, cx - text_width(s, scale) // 2, y, scale, color)


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
     "IMMEDIATELY, 11 DAYS AFTER HE RESIGNED. SHARES JUMPED 31 PERCENT."),
    ("WALL STREET SURGES AS NVIDIA JUMPS 31 PERCENT (REUTERS)",
     "THE S AND P 500 ROSE 4.73 PERCENT, THE NASDAQ JUMPED 6.51 "
     "PERCENT AND THE DOW GAINED 3.01 PERCENT, THE BEST DAY SINCE "
     "APRIL 2025."),
    ("EU PROPOSES 22ND SANCTIONS PACKAGE AGAINST RUSSIA (REUTERS)",
     "THE PACKAGE TARGETS 60 BANKS, CRYPTO PLATFORMS AND 70 MORE "
     "SHADOW-FLEET VESSELS, AND BANS RUSSIAN TEAMS UNDER THE "
     "RUSSIAN FLAG."),
]

FEATURED = [
    ("UKRAINE SAYS IT SANK RUSSIAN CORVETTE OFF LIBYA (REUTERS)",
     "SEVEN NAVAL DRONES SANK THE MERKURY AT BENGHAZI PORT AND HIT "
     "THE CARGO SHIP ANGARA, ZELENSKYY SAID."),
    ("RUSSIAN OVERNIGHT STRIKES KILL AT LEAST 15 IN KYIV REGION (AP)",
     "RUSSIA LAUNCHED 153 DRONES AT UKRAINE OVERNIGHT INTO MONDAY."),
    ("IRAN VOWS TO USE ALL MEANS AGAINST US BLOCKADE (REUTERS)",
     "TEHRAN WILL COUNTER THE US NAVAL BLOCKADE OF THE STRAIT OF "
     "HORMUZ, THE FOREIGN MINISTRY SAID."),
    ("INDIA PLEDGES 1.6 BILLION DOLLARS TO NEPAL IN RESET OF TIES (BBC)",
     "PM MODI PLEDGED A 240 BILLION RUPEE PACKAGE TO HELP NEPAL "
     "REBUILD AFTER AUGUST FLOODS."),
    ("UK RECOGNISES ROHINGYA GENOCIDE AND SANCTIONS MYANMAR GENERALS (BBC)",
     "LONDON SANCTIONED FIVE SENIOR MYANMAR OFFICERS AND PLANS TO "
     "RESTRICT AVIATION FUEL EXPORTS."),
    ("DEMOCRATS WIN LARGEST HOUSE MAJORITY SINCE 1992 (BBC)",
     "DEMOCRATS WON AT LEAST 258 HOUSE SEATS AFTER FLIPPING A "
     "NORTH CAROLINA SEAT."),
    ("FIFA NAMES 2031 AND 2035 WOMENS WORLD CUP HOSTS (AP)",
     "US, MEXICO, COSTA RICA AND JAMAICA HOST 2031; ENGLAND, "
     "NORTHERN IRELAND, SCOTLAND AND WALES HOST 2035."),
    ("AUSTRALIAN MUSIC LEGEND MOLLY MELDRUM DIES AGED 83 (REUTERS)",
     "THE COUNTDOWN HOST WHO CHAMPIONED AUSTRALIAN MUSIC FOR SIX "
     "DECADES DIED IN MELBOURNE."),
    ("NIKKEI FALLS MORE THAN 5 PERCENT IN ASIAN TRADING (AP)",
     "JAPANS NIKKEI FELL MORE THAN 5 PERCENT WHILE WALL STREET "
     "LATER RALLIED."),
    ("US TO BLACKLIST MEGASPEED CHIP FIRM LINKED TO NVIDIA SCANDAL (REUTERS)",
     "THE SINGAPORE-BASED CHIP FIRM WAS ADDED TO THE US TRADE "
     "BLACKLIST ON MONDAY."),
]

# One line each: number, condensed headline, source. Must fit one line
# at scale 1 in a 486 px column (81 chars max).
ALSO = [
    "5. TRUMP SAYS HE CONVINCED NVIDIA TO REINSTATE HUANG (BBC)",
    "9. FINLAND SUMMONS RUSSIAN AMBASSADOR; RUSSIA WARNS ESTONIA (REUTERS)",
    "10. NATO COUNCIL MEETS ON POLAND MISSILE STRIKES (REUTERS)",
    "11. POLAND SAYS RUSSIA TRIED TO KILL RAPPER KYIVSTONER TWICE (REUTERS)",
    "13. IRAN SAYS IT CAN REOPEN HORMUZ QUICKLY IF US MEETS TERMS (REUTERS)",
    "15. BANGLADESH SAYS HASINA WILL BE ARRESTED IF SHE RETURNS (REUTERS)",
    "16. SOUTH KOREA RESHUFFLES CABINET, NAMES FIRST WOMAN SPY CHIEF (REUTERS)",
    "17. KIM STRESSES SOVEREIGNTY AFTER REBUFFING TRUMP TALKS OFFER (REUTERS)",
    "19. FOURTEEN COUNTRIES BACK ICJ ROHINGYA GENOCIDE RULING (REUTERS)",
    "20. ALBANESE BLAMES COP31 FAILURE ON DIFFICULT GEOPOLITICAL TIMES (AFP)",
    "21. GUTERRES URGES GREATER AI REGULATION AT BARBADOS SUMMIT (UN NEWS)",
    "22. WHO SAYS FIGHTING DISRUPTS EBOLA RESPONSE IN DR CONGO (REUTERS)",
    "23. UN LIBYA MISSION URGES PROBE INTO BENGHAZI PORT ATTACKS (UN NEWS)",
    "24. KENYA AND DR CONGO RESTORE FULL DIPLOMATIC TIES (REUTERS)",
    "25. MEXICAN SOLDIERS ATTACKED AFTER CHAPO ISIDRO ARREST (BBC)",
    "27. JIMMY GOMEZ TO RESIGN AFTER ETHICS PANEL FINDS MISCONDUCT (BBC)",
    "28. SEATTLE AIRPORT OPERATOR OUTRAGED OVER ICE ARREST (BBC)",
    "29. US BUSINESS ACTIVITY STAYS STRONG IN NOVEMBER FLASH PMI (REUTERS)",
    "31. BRENTFORD BEAT EVERTON 4-0 IN PREMIER LEAGUE (SKY SPORTS)",
    "33. TYSON FURY REVEALS SCHIZOPHRENIA DIAGNOSIS IN NETFLIX FILM (BBC)",
    "34. IRAN FLOGS SINGER PARASTOO AHMADI AND FOUR TEAM MEMBERS (BBC)",
    "35. OXFAM SAYS GAZA TURNED INTO TOXIC WASTELAND BY ISRAELI ATTACKS (BBC)",
    "36. BELGIUM AIRPORTS SHUT FOR A DAY AS CONTROLLERS STRIKE (BBC)",
    "37. ARMENIA PROPOSES NEW CONSTITUTION IN STEP TOWARD PEACE (REUTERS)",
    "38. DENMARK TO PROPOSE MOBILE PHONE BAN IN SCHOOLS IN 2027 (REUTERS)",
    "39. ISRAELI STRIKES KILL AT LEAST 3 IN GAZA, INCLUDING UN WORKER (REUTERS)",
    "40. TRUMP TO WELCOME INVESTORS AT GALA FOR PLUNGING MEME COIN (REUTERS)",
    "41. GISELE PELICOT HUMILIATED AFTER NUDE PHOTOS SENT TO MEDIA (BBC)",
    "42. CATHERINE TALKS ABOUT MORTALITY IN NEW DOCUMENTARY CLIP (BBC)",
    "43. ANDREW MOUNTBATTEN-WINDSOR GOT 750,000 POUNDS, COURT TOLD (BBC)",
    "44. BURNHAM SAYS CLOSER EU TIES COULD MAKE NEXT DECADE BETTER (BBC)",
    "45. US DECLASSIFIES MORE UFO FOOTAGE FILMED IN MIDDLE EAST (BBC)",
    "46. MELANIA TRUMP WELCOMES WHITE HOUSE CHRISTMAS TREE (BBC)",
    "47. ZIMBABWE PREACHER ARRESTED ON SEXUAL ASSAULT ALLEGATIONS (BBC)",
    "48. SYDNEY DOUBLE MURDER TRIAL TOLD DEATHS WERE EXECUTION (AAP)",
    "49. US ARMY TO DETONATE TOXIC EXPLOSIVES IN IOWA DESPITE COURT HOLD (BBC)",
    "50. JAPAN MARKS LABOUR THANKSGIVING DAY (WIKIPEDIA)",
    "51. SEARCH AND RESCUE RACE AFTER NIGERIA BOAT TRAGEDY (BBC)",
    "52. NIGERIA PRESIDENT SAYS VILLA HIT BY WATER AND POWER CUTS (BBC)",
]

SOURCES = ("SOURCES: REUTERS, BBC, AP, AFP, UN NEWS, AAP, XINHUA, "
           "SKY SPORTS, GOV.UK, WIKIPEDIA")

DATE_CHECK = ("EVERY STORY ON THIS PAGE HAPPENED OR WAS FIRST REPORTED ON "
              "MONDAY 23 NOVEMBER 2026. LEFT OUT ON PURPOSE: COP31 TALKS "
              "FAILURE (22 NOV) - IRGC BAHRAIN PATRIOT-RADAR CLAIM "
              "(21-22 NOV) - TRUMP 350BN SHUTDOWN DEMAND (20 NOV) - "
              "INDONESIA FACTORY FIRE (21-22 NOV) - SUNDAY SPORT RESULTS "
              "(22 NOV) - EU-INDONESIA TRADE DEAL (21 NOV).")


# ---------------------------------------------------------------- illustrations
# Hand-drawn scenes for the three lead stories and a stylized world map.
# All shapes are code-drawn lines/polygons/circles: no photos, no PIL,
# no network. Written fresh for this revision; each scene is 48 px tall.

def draw_lead1(c, x, y, w):
    """Nvidia CEO returns: a richer office scene — open door, a figure
    walking back in with a briefcase, desk with monitor, papers and a
    chip, a wall chart, and a red BACK arrow pointing into the door."""
    c.hline(x, y + 46, w, GREY, 1)
    # open doorway, left
    c.box(x + 8, y + 2, 38, 44, INK, 2)
    # figure walking in through the door, briefcase in hand
    hx, hy = x + 27, y + 14
    c.circle(hx, hy, 4, INK)
    c.line(hx, hy + 5, hx, hy + 18, INK, 2)
    c.line(hx, hy + 23, hx - 7, hy + 32, INK, 2)
    c.line(hx, hy + 23, hx + 7, hy + 30, INK, 2)
    c.line(hx, hy + 10, hx - 8, hy + 15, INK, 2)
    c.line(hx, hy + 10, hx + 8, hy + 14, INK, 2)
    c.rect(hx + 10, hy + 15, 10, 8, INK)
    c.rect(hx + 12, hy + 17, 6, 4, PAPER)
    # red BACK arrow pointing left into the door
    c.line(x + 150, y + 26, x + 54, y + 26, RED, 3)
    c.line(x + 54, y + 26, x + 68, y + 19, RED, 3)
    c.line(x + 54, y + 26, x + 68, y + 33, RED, 3)
    c.text("BACK", x + 92, y + 14, 1, RED)
    # framed wall chart
    c.box(x + 160, y + 4, 36, 20, INK, 1)
    c.line(x + 164, y + 20, x + 172, y + 14, RED, 1)
    c.line(x + 172, y + 14, x + 180, y + 16, RED, 1)
    c.line(x + 180, y + 16, x + 188, y + 9, RED, 1)
    # desk with papers, monitor and chip
    c.hline(x + 150, y + 36, 162, INK, 2)
    c.vline(x + 156, y + 36, 10, INK, 2)
    c.vline(x + 304, y + 36, 10, INK, 2)
    c.rect(x + 160, y + 30, 22, 6, WHITE)
    c.hline(x + 163, y + 33, 16, GREY, 1)
    c.rect(x + 186, y + 31, 18, 5, WHITE)
    c.hline(x + 189, y + 33, 12, GREY, 1)
    c.rect(x + 210, y + 20, 36, 16, INK)
    c.rect(x + 213, y + 23, 30, 10, LIGHT)
    c.line(x + 216, y + 31, x + 224, y + 26, RED, 1)
    c.line(x + 224, y + 26, x + 232, y + 28, RED, 1)
    c.line(x + 232, y + 28, x + 240, y + 24, RED, 1)
    # chip, right, sitting on the desk
    c.rect(x + 272, y + 20, 26, 16, BLUE)
    for px in (x + 278, x + 286, x + 294):
        c.vline(px, y + 16, 4, BLUE, 2)
    c.hline(x + 268, y + 26, 4, BLUE, 2)
    c.hline(x + 268, y + 31, 4, BLUE, 2)
    c.hline(x + 298, y + 26, 4, BLUE, 2)
    c.hline(x + 298, y + 31, 4, BLUE, 2)
    c.text("NV", x + 278, y + 25, 1, WHITE)


def draw_lead2(c, x, y, w):
    """Wall Street surges: a fuller skyline with lit windows, a flag on
    the tallest tower, and a bold red arrow climbing past it, +31%."""
    c.hline(x, y + 46, w, GREY, 1)
    # skyline, six buildings of rising and falling height
    builds = [(6, 26, 26), (36, 18, 26), (66, 28, 26),
              (96, 10, 26), (126, 20, 26), (156, 30, 24)]
    for bx, top, bw in builds:
        c.rect(x + bx, y + top, bw, 46 - top, BLUE)
        for wx in (bx + 5, bx + 15):
            if wx + 4 > bx + bw - 3:
                continue
            for wy in range(top + 5, 42, 9):
                c.rect(x + wx, y + wy, 4, 4, LIGHT)
    # flag on the tallest tower
    c.vline(x + 109, y + 2, 8, INK, 1)
    c.poly([(x + 109, y + 2), (x + 121, y + 5), (x + 109, y + 8)], RED)
    # bold rising arrow over the skyline
    c.line(x + 6, y + 44, x + 300, y + 6, RED, 4)
    c.line(x + 300, y + 6, x + 280, y + 6, RED, 4)
    c.line(x + 300, y + 6, x + 294, y + 24, RED, 4)
    c.text("+31%", x + 222, y + 28, 2, RED)


def draw_lead3(c, x, y, w):
    """EU sanctions package: a gold-rimmed circle of stars, an arrow to
    a layered document with a red seal, 22ND clear."""
    # EU circle of stars with a gold rim
    cx, cy = x + 40, y + 24
    c.ring(cx, cy, 22, GOLD, 2, BLUE)
    for k in range(12):
        ang = math.radians(k * 30)
        sx = cx + int(13 * math.cos(ang))
        sy = cy + int(13 * math.sin(ang))
        c.circle(sx, sy, 2, GOLD)
    # arrow from the circle to the document
    c.line(x + 64, y + 24, x + 104, y + 24, BLUE, 3)
    c.line(x + 104, y + 24, x + 94, y + 18, BLUE, 3)
    c.line(x + 104, y + 24, x + 94, y + 30, BLUE, 3)
    # layered document: back sheet offset, front sheet with seal
    c.rect(x + 120, y + 8, 92, 40, WHITE)
    c.box(x + 120, y + 8, 92, 40, GREY, 1)
    c.rect(x + 112, y + 4, 92, 40, WHITE)
    c.box(x + 112, y + 4, 92, 40, INK, 2)
    c.text("22ND", x + 128, y + 10, 2, RED)
    c.hline(x + 122, y + 28, 56, GREY, 1)
    c.hline(x + 122, y + 34, 44, GREY, 1)
    # red seal with a gold centre on the document
    c.ring(x + 186, y + 38, 7, RED, 2, WHITE)
    c.circle(x + 186, y + 38, 2, GOLD)
    # caption
    c.text("SANCTIONS", x + 216, y + 18, 1, INK)
    c.text("PACKAGE", x + 216, y + 30, 1, INK)


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
# (u, v, label, label_x, label_y) - marker dots + labels
MAP_MARKERS = [
    (78, 26, "NVIDIA", 57, 14),
    (212, 22, "WALL ST", 220, 19),
    (478, 16, "EU", 470, 4),
    (538, 12, "KYIV", 546, 8),
    (640, 10, "RUSSIA", 622, 20),
    (608, 30, "IRAN", 588, 40),
    (688, 34, "NEPAL", 670, 44),
    (734, 36, "MYANMAR", 712, 46),
]


def draw_world_map(c, x, y, w, h):
    """Stylized continents + red markers where the big stories happened."""
    sx = w / 984.0
    sy = h / 64.0
    for poly in MAP_CONTINENTS:
        pts = [(x + int(u * sx), y + int(v * sy)) for u, v in poly]
        c.poly(pts, MAPFILL)
        c.polyline(pts, BLUE, 1)
    for u, v in MAP_ISLANDS:
        c.ring(x + int(u * sx), y + int(v * sy), 3, BLUE, 1, MAPFILL)
    for u, v, label, lx, ly in MAP_MARKERS:
        mx, my = x + int(u * sx), y + int(v * sy)
        c.circle(mx, my, 3, RED)
        c.text(label, x + int(lx * sx), y + int(ly * sy), 1, INK)


# ---------------------------------------------------------------- layout
def draw(c):
    MX = 20                      # side margin
    CW = W - 2 * MX              # content width: 984

    # ---- masthead
    y = 14
    c.text_center("THE WORLD IN ONE DAY", W // 2, y, 4, INK)
    y += 4 * 7 + 8
    c.hline(MX, y, CW, INK, 3)
    y += 9
    c.text_center("MONDAY 23 NOVEMBER 2026", W // 2, y, 2, RED)
    y += 2 * 7 + 10
    c.hline(MX, y, CW, INK, 1)

    # ---- stat strip
    y += 8
    c.rect(MX, y, CW, 22, INK)
    c.text_center("52 STORIES  -  10 OUTLETS  -  ONE DAY  -  "
                  "MARKETS, WAR, POLITICS, CULTURE, SPORT",
                  W // 2, y + 4, 2, WHITE)
    y += 22 + 8

    # ---- leads: three columns
    lead_top = y
    col_w = (CW - 2 * 16) // 3
    lead_bottom = lead_top
    for i, (head, body) in enumerate(LEADS):
        x = MX + i * (col_w + 16)
        cy = lead_top
        c.text("LEAD %d" % (i + 1), x, cy, 1, RED)
        cy += 12
        hl = wrap(head, col_w, 2)
        for line in hl:
            c.text(line, x, cy, 2, INK)
            cy += 18
        cy += 2
        c.hline(x, cy, col_w, RED, 2)
        cy += 8
        for line in wrap(body, col_w, 1):
            c.text(line, x, cy, 1, INK)
            cy += 11
        # Hand-drawn illustration for the lead story (48 px tall).
        cy += 4
        if i == 0:
            draw_lead1(c, x, cy, col_w)
        elif i == 1:
            draw_lead2(c, x, cy, col_w)
        else:
            draw_lead3(c, x, cy, col_w)
        cy += 48
        lead_bottom = max(lead_bottom, cy)
    # vertical dividers between lead columns
    for i in (1, 2):
        dx = MX + i * (col_w + 16) - 8
        c.vline(dx, lead_top, lead_bottom - lead_top, GREY, 1)
    y = lead_bottom + 6
    c.hline(MX, y, CW, INK, 2)
    y += 6

    # ---- featured: two columns, five rows each
    c.text("FEATURED", MX, y, 2, RED)
    y += 18
    feat_top = y
    fcol_w = (CW - 16) // 2
    row_h = 58
    for idx, (head, body) in enumerate(FEATURED):
        col = idx % 2
        row = idx // 2
        x = MX + col * (fcol_w + 16)
        cy = feat_top + row * row_h
        hl = wrap(head, fcol_w, 2)
        assert len(hl) <= 2, "featured headline too long: %r" % head
        for line in hl:
            c.text(line, x, cy, 2, INK)
            cy += 18
        bl = wrap(body, fcol_w, 1)
        assert len(bl) <= 2, "featured body too long: %r" % body
        for line in bl:
            c.text(line, x, cy, 1, GREY)
            cy += 11
    y = feat_top + 5 * row_h + 2
    c.hline(MX, y, CW, INK, 2)
    y += 6

    # ---- ALSO list: two columns, one line per story
    c.text("ALSO IN THE NEWS - 23 NOVEMBER", MX, y, 2, RED)
    y += 18
    also_top = y
    acol_w = (CW - 16) // 2
    left = ALSO[:20]
    right = ALSO[20:]
    for line in ALSO:
        assert text_width(line, 1) <= acol_w, "ALSO line too long: %r" % line
    for i, line in enumerate(left):
        c.text(line, MX, also_top + i * 9, 1, INK)
    for i, line in enumerate(right):
        c.text(line, MX + acol_w + 16, also_top + i * 9, 1, INK)
    y = also_top + 20 * 9 + 4
    c.hline(MX, y, CW, INK, 2)
    y += 6

    # ---- world map: stylized continents + markers for the big stories
    c.text("WORLD MAP - WHERE THE NEWS HAPPENED", MX, y, 1, RED)
    y += 11
    draw_world_map(c, MX, y, CW, 66)
    y += 66 + 6
    c.hline(MX, y, CW, INK, 2)
    y += 6

    # ---- DATE CHECK box
    box_h = 66
    c.box(MX, y, CW, box_h, INK, 2)
    c.text("DATE CHECK - 23 NOVEMBER 2026 ONLY", MX + 12, y + 8, 2, RED)
    by = y + 30
    for line in wrap(DATE_CHECK, CW - 24, 1):
        c.text(line, MX + 12, by, 1, INK)
        by += 11
    y += box_h + 6

    # ---- sources + footer
    c.text_center(SOURCES, W // 2, y, 1, INK)
    y += 10
    c.hline(MX, y, CW, GREY, 1)
    y += 6
    c.text_center("ALL 52 STORIES VERIFIED AGAINST THE NAMED SOURCE - "
                  "MONDAY 23 NOVEMBER 2026", W // 2, y, 1, GREY)
    y += 11
    assert y <= H - 8, "layout overflow: y=%d" % y
    return y


def main():
    c = Canvas(W, H, PAPER)
    draw(c)
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", ".")
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as f:
        f.write(png_bytes(c))
    print("wrote %s (%d bytes)" % (path, os.path.getsize(path)))


if __name__ == "__main__":
    main()
