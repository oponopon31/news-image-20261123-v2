"""Stroke-based vector font (SANS) for the news23 entry.

Fresh design, written from scratch. Each glyph is one compact string:
strokes separated by ';', points separated by spaces, each point 'x,y'
on a 5x7 grid (x 0..4, y 0..6, y=0 top). One polyline per stroke; a
single-point stroke draws a filled square (dots).

Advance is 6 grid units and cap height is 7 — identical metrics to the
old 5x7 bitmap font, so text_width / wrap / layout code is unchanged.
Only the rendering changes: clean single strokes instead of blocky
filled pixels.

Lowercase letters reuse the uppercase shapes (no lowercase is drawn).
Pure Python standard library only.
"""

GLYPHS = {
    'A': "0,6 2,0 4,6;1,4 3,4",
    'B': "0,0 0,6;0,0 3,0 4,1 4,2 3,3 0,3;0,3 3,3 4,4 4,5 3,6 0,6",
    'C': "4,1 3,0 1,0 0,1 0,5 1,6 3,6 4,5",
    'D': "0,0 0,6;0,0 3,0 4,1 4,5 3,6 0,6",
    'E': "0,0 0,6;0,0 4,0;0,3 3,3;0,6 4,6",
    'F': "0,0 0,6;0,0 4,0;0,3 3,3",
    'G': "4,1 3,0 1,0 0,1 0,5 1,6 3,6 4,5 4,3 2,3",
    'H': "0,0 0,6;4,0 4,6;0,3 4,3",
    'I': "1,0 3,0;2,0 2,6;1,6 3,6",
    'J': "4,0 4,5 3,6 1,6 0,5 0,4",
    'K': "0,0 0,6;4,0 0,3 4,6",
    'L': "0,0 0,6;0,6 4,6",
    'M': "0,6 0,0 2,3 4,0 4,6",
    'N': "0,6 0,0 4,6 4,0",
    'O': "1,0 3,0 4,1 4,5 3,6 1,6 0,5 0,1 1,0",
    'P': "0,0 0,6;0,0 3,0 4,1 4,2 3,3 0,3",
    'Q': "1,0 3,0 4,1 4,5 3,6 1,6 0,5 0,1 1,0;3,4 4,6",
    'R': "0,0 0,6;0,0 3,0 4,1 4,2 3,3 0,3;2,3 4,6",
    'S': "4,1 3,0 1,0 0,1 0,2 1,3 3,3 4,4 4,5 3,6 1,6 0,5",
    'T': "0,0 4,0;2,0 2,6",
    'U': "0,0 0,5 1,6 3,6 4,5 4,0",
    'V': "0,0 2,6 4,0",
    'W': "0,0 1,6 2,3 3,6 4,0",
    'X': "0,0 4,6;4,0 0,6",
    'Y': "0,0 2,3 4,0;2,3 2,6",
    'Z': "0,0 4,0 0,6 4,6",
    '0': "1,0 3,0 4,1 4,5 3,6 1,6 0,5 0,1 1,0",
    '1': "1,1 2,0 2,6;0,6 4,6",
    '2': "0,1 1,0 3,0 4,1 4,2 3,3 1,4 0,5 0,6 4,6",
    '3': "1,0 4,0 4,3 1,3 4,3 4,6 1,6",
    '4': "3,0 3,6;0,3 4,3;0,0 3,3",
    '5': "4,0 0,0 0,3 3,3 4,4 4,5 3,6 1,6 0,5",
    '6': "4,0 3,0 1,0 0,1 0,5 1,6 3,6 4,5 4,4 3,3 1,3 0,4",
    '7': "0,0 4,0 1,6",
    '8': "1,0 3,0 4,1 4,5 3,6 1,6 0,5 0,1 1,0;0,3 4,3",
    '9': "4,6 4,1 3,0 1,0 0,1 0,3 1,4 3,4 4,3",
    ' ': "",
    '.': "2,6",
    ',': "2,4 2,5 1,6",
    ':': "2,1;2,4",
    ';': "2,1;2,4 1,6",
    '(': "3,0 2,1 1,2 1,4 2,5 3,6",
    ')': "1,0 2,1 3,2 3,4 2,5 1,6",
    '-': "0,3 4,3",
    '/': "4,6 0,0",
    "'": "2,0 2,2",
    '%': "4,0 0,6;1,1;3,5",
    '$': "2,0 2,6;0,1 1,0 3,0 4,1 4,2 3,3 1,3 0,4 0,5 1,6 3,6 4,5",
    '&': "3,0 1,0 0,1 0,3 1,4 3,4 4,5 4,6 3,6 1,6 0,5;1,4 4,0",
    '!': "2,0 2,4;2,6",
    '?': "1,0 3,0 4,1 4,2 3,3 2,3;2,6",
    '+': "2,1 2,5;0,3 4,3",
    '=': "0,2 4,2;0,4 4,4",
    '"': "1,0 1,2;3,0 3,2",
    '#': "1,0 1,6;3,0 3,6;0,2 4,2;0,4 4,4",
    '_': "0,6 4,6",
}

# Lowercase reuses the uppercase shapes (no lowercase is drawn).
for _u in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
    GLYPHS[_u.lower()] = GLYPHS[_u]


def _parse(spec):
    strokes = []
    for part in spec.split(';'):
        part = part.strip()
        if not part:
            continue
        pts = []
        for tok in part.split():
            x, y = tok.split(',')
            pts.append((int(x), int(y)))
        if pts:
            strokes.append(pts)
    return strokes


_GLYPHS = {ch: _parse(spec) for ch, spec in GLYPHS.items()}


def text_width(text, scale):
    """Pixel width of text at the given scale (6 units per char)."""
    return len(text) * 6 * scale


def draw_text(canvas, s, x, y, scale, color):
    """Draw string s at (x, y) with the stroke font. Returns end x."""
    thick = max(1, scale)
    cx = x
    for ch in s:
        for pts in _GLYPHS.get(ch, ()):
            if len(pts) == 1:
                px, py = pts[0]
                canvas.rect(cx + px * scale - thick // 2,
                            y + py * scale - thick // 2,
                            thick, thick, color)
            else:
                for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                    canvas.line(cx + x0 * scale, y + y0 * scale,
                                cx + x1 * scale, y + y1 * scale,
                                color, thick)
        cx += 6 * scale
    return cx
