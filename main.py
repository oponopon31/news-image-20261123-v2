#!/usr/bin/env python3
"""The World in One Day - Monday 23 November 2026.

A program that draws one front-page image summing up 23 November 2026
world news: 52 verified stories, every one carrying its source.

Pure Python standard library only. Hand-drawn 5x7 bitmap font, hand-rolled
PNG encoder, no network, no randomness, deterministic output.

Run: python3 main.py
Writes entry.png (1024x1024) to $MAKEFUN_OUTPUT_DIR or the current dir.
"""

import os
import struct
import zlib

W, H = 1024, 1024

PAPER = (253, 250, 240)
INK = (18, 18, 18)
RED = (178, 34, 34)
BLUE = (28, 58, 128)
GREY = (110, 108, 100)
LIGHT = (238, 233, 220)
WHITE = (255, 255, 255)
GOLD = (176, 128, 20)

# ---------------------------------------------------------------- font
# 5x7 bitmap glyphs, one row per int, bit 4 = leftmost column.
# Uppercase letters, digits and punctuation only. All drawn text is
# plain ASCII: no em/en dashes, no ellipsis, no curly quotes, no
# degree or approx symbols; approximations are spelled (APPROX).
FONT = {
    'A': (14, 17, 17, 31, 17, 17, 17),
    'B': (30, 17, 17, 30, 17, 17, 30),
    'C': (14, 17, 16, 16, 16, 17, 14),
    'D': (28, 18, 17, 17, 17, 18, 28),
    'E': (31, 16, 16, 30, 16, 16, 31),
    'F': (31, 16, 16, 30, 16, 16, 16),
    'G': (14, 17, 16, 23, 17, 17, 15),
    'H': (17, 17, 17, 31, 17, 17, 17),
    'I': (14, 4, 4, 4, 4, 4, 14),
    'J': (7, 2, 2, 2, 2, 18, 12),
    'K': (17, 18, 20, 24, 20, 18, 17),
    'L': (16, 16, 16, 16, 16, 16, 31),
    'M': (17, 27, 21, 21, 17, 17, 17),
    'N': (17, 25, 21, 19, 17, 17, 17),
    'O': (14, 17, 17, 17, 17, 17, 14),
    'P': (30, 17, 17, 30, 16, 16, 16),
    'Q': (14, 17, 17, 17, 21, 18, 13),
    'R': (30, 17, 17, 30, 20, 18, 17),
    'S': (15, 16, 16, 14, 1, 1, 30),
    'T': (31, 4, 4, 4, 4, 4, 4),
    'U': (17, 17, 17, 17, 17, 17, 14),
    'V': (17, 17, 17, 17, 17, 10, 4),
    'W': (17, 17, 17, 21, 21, 27, 17),
    'X': (17, 17, 10, 4, 10, 17, 17),
    'Y': (17, 17, 10, 4, 4, 4, 4),
    'Z': (31, 1, 2, 4, 8, 16, 31),
    '0': (14, 17, 19, 21, 25, 17, 14),
    '1': (4, 12, 4, 4, 4, 4, 14),
    '2': (14, 17, 1, 6, 8, 16, 31),
    '3': (31, 2, 4, 2, 1, 17, 14),
    '4': (2, 6, 10, 18, 31, 2, 2),
    '5': (31, 16, 30, 1, 1, 17, 14),
    '6': (6, 8, 16, 30, 17, 17, 14),
    '7': (31, 1, 2, 4, 8, 8, 8),
    '8': (14, 17, 17, 14, 17, 17, 14),
    '9': (14, 17, 17, 15, 1, 2, 12),
    ' ': (0, 0, 0, 0, 0, 0, 0),
    '.': (0, 0, 0, 0, 0, 12, 12),
    ',': (0, 0, 0, 0, 12, 4, 8),
    ':': (0, 12, 12, 0, 12, 12, 0),
    ';': (0, 12, 12, 0, 12, 4, 8),
    '(': (2, 4, 8, 8, 8, 4, 2),
    ')': (8, 4, 2, 2, 2, 4, 8),
    '-': (0, 0, 0, 14, 0, 0, 0),
    '/': (1, 2, 2, 4, 8, 8, 16),
    "'": (4, 4, 8, 0, 0, 0, 0),
    '%': (25, 26, 2, 4, 8, 11, 19),
    '$': (4, 15, 20, 14, 5, 30, 4),
    '&': (12, 18, 20, 8, 21, 18, 13),
    '!': (4, 4, 4, 4, 4, 0, 4),
    '?': (14, 17, 1, 6, 4, 0, 4),
    '+': (0, 4, 4, 31, 4, 4, 0),
    '=': (0, 0, 31, 0, 31, 0, 0),
    '"': (10, 10, 10, 0, 0, 0, 0),
    '#': (10, 10, 31, 10, 31, 10, 10),
    '_': (0, 0, 0, 0, 0, 0, 31),
}

BLANK = (0, 0, 0, 0, 0, 0, 0)


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

    def text(self, s, x, y, scale, color):
        cx = x
        for ch in s:
            glyph = FONT.get(ch, BLANK)
            for row in range(7):
                bits = glyph[row]
                for col in range(5):
                    if bits & (1 << (4 - col)):
                        self.rect(cx + col * scale, y + row * scale,
                                  scale, scale, color)
            cx += 6 * scale
        return cx

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


# ---------------------------------------------------------------- layout
def draw(c):
    MX = 20                      # side margin
    CW = W - 2 * MX              # content width: 984

    # ---- masthead
    y = 14
    c.text_center("THE WORLD IN ONE DAY", W // 2, y, 5, INK)
    y += 5 * 7 + 8
    c.hline(MX, y, CW, INK, 3)
    y += 9
    c.text_center("MONDAY 23 NOVEMBER 2026", W // 2, y, 2, RED)
    y += 2 * 7 + 10
    c.hline(MX, y, CW, INK, 1)

    # ---- stat strip
    y += 8
    c.rect(MX, y, CW, 26, INK)
    c.text_center("52 STORIES  -  10 OUTLETS  -  ONE DAY  -  "
                  "MARKETS, WAR, POLITICS, CULTURE, SPORT",
                  W // 2, y + 6, 2, WHITE)
    y += 26 + 10

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
        if i == 1:
            # Small bar chart: Monday index moves, percent.
            cy += 6
            bars = [("S+P 500", 4.73), ("NASDAQ", 6.51), ("DOW", 3.01)]
            bx = x
            for name, val in bars:
                bh = int(val * 4)
                c.rect(bx, cy + 30 - bh, 34, bh, BLUE)
                c.text("+%.2f" % val, bx - 2, cy + 32, 1, INK)
                c.text(name, bx - 2, cy + 44, 1, GREY)
                bx += 62
            cy += 52
        lead_bottom = max(lead_bottom, cy)
    # vertical dividers between lead columns
    for i in (1, 2):
        dx = MX + i * (col_w + 16) - 8
        c.vline(dx, lead_top, lead_bottom - lead_top, GREY, 1)
    y = lead_bottom + 8
    c.hline(MX, y, CW, INK, 2)
    y += 8

    # ---- featured: two columns, five rows each
    c.text("FEATURED", MX, y, 2, RED)
    y += 20
    feat_top = y
    fcol_w = (CW - 16) // 2
    row_h = 60
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
    y += 8

    # ---- ALSO list: two columns, one line per story
    c.text("ALSO IN THE NEWS - 23 NOVEMBER", MX, y, 2, RED)
    y += 20
    also_top = y
    acol_w = (CW - 16) // 2
    left = ALSO[:20]
    right = ALSO[20:]
    for line in ALSO:
        assert text_width(line, 1) <= acol_w, "ALSO line too long: %r" % line
    for i, line in enumerate(left):
        c.text(line, MX, also_top + i * 11, 1, INK)
    for i, line in enumerate(right):
        c.text(line, MX + acol_w + 16, also_top + i * 11, 1, INK)
    y = also_top + 20 * 11 + 6
    c.hline(MX, y, CW, INK, 2)
    y += 8

    # ---- DATE CHECK box
    box_h = 72
    c.box(MX, y, CW, box_h, INK, 2)
    c.text("DATE CHECK - 23 NOVEMBER 2026 ONLY", MX + 12, y + 8, 2, RED)
    by = y + 30
    for line in wrap(DATE_CHECK, CW - 24, 1):
        c.text(line, MX + 12, by, 1, INK)
        by += 11
    y += box_h + 8

    # ---- sources + footer
    c.text_center(SOURCES, W // 2, y, 1, INK)
    y += 12
    c.hline(MX, y, CW, GREY, 1)
    y += 8
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
