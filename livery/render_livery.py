"""Render the original Apex Noir 07 texture atlas for TORCS car1-ow1.

Requires Pillow only for artwork generation. The racing controller has no
dependency on this script or on Pillow.
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
SCALE = 3
SIZE = 512 * SCALE

NAVY = (12, 22, 32)
MIDNIGHT = (7, 15, 23)
GRAPHITE = (26, 39, 48)
PANEL = (33, 48, 58)
AQUA = (18, 207, 200)
AQUA_LIGHT = (91, 243, 226)
GOLD = (195, 160, 91)
SILVER = (226, 234, 231)


def poly(draw, points, fill):
    draw.polygon([(round(x * SCALE), round(y * SCALE)) for x, y in points], fill=fill)


def line(draw, points, fill, width=1):
    draw.line([(round(x * SCALE), round(y * SCALE)) for x, y in points], fill=fill, width=round(width * SCALE), joint="curve")


def ellipse(draw, box, fill, outline=None, width=1):
    draw.ellipse(tuple(round(v * SCALE) for v in box), fill=fill, outline=outline, width=round(width * SCALE))


def number(draw, xy, size, rotation=0):
    font = ImageFont.truetype("C:/Windows/Fonts/bahnschrift.ttf", round(size * SCALE))
    badge = Image.new("RGBA", (round(size * 2.7 * SCALE), round(size * 1.45 * SCALE)))
    bd = ImageDraw.Draw(badge)
    bd.text((round(size * .12 * SCALE), 0), "07", font=font, fill=(*SILVER, 255), stroke_width=round(.6 * SCALE), stroke_fill=(*SILVER, 255))
    if rotation:
        badge = badge.rotate(rotation, expand=True, resample=Image.Resampling.BICUBIC)
    canvas.alpha_composite(badge, (round(xy[0] * SCALE), round(xy[1] * SCALE)))


canvas = Image.new("RGBA", (SIZE, SIZE), (*NAVY, 255))
d = ImageDraw.Draw(canvas)

# Fine stepped reflections give the dark paint a metallic appearance while
# remaining completely authored artwork, with no simulator source pixels.
for y in range(SIZE):
    t = y / SIZE
    lift = round(4 * (1 - abs(2 * t - 1)))
    d.line((0, y, SIZE, y), fill=(NAVY[0] + lift, NAVY[1] + lift, NAVY[2] + lift + 1, 255))
for x in range(0, 512, 9):
    line(d, [(x, 0), (x - 115, 512)], (19, 31, 41, 255), .45)

# Dark cockpit opening and nacelle sections, taken from the UV layout rather
# than copied from either earlier livery.
poly(d, [(229, 37), (358, 27), (390, 3), (422, 0), (477, 2), (506, 31), (510, 59), (481, 78), (400, 84), (356, 64), (230, 58)], (*MIDNIGHT, 255))
poly(d, [(66, 0), (229, 0), (229, 82), (65, 82)], (*GRAPHITE, 255))
line(d, [(68, 77), (216, 77)], (*AQUA, 255), 3)
line(d, [(68, 72), (216, 72)], (*GOLD, 255), .9)
poly(d, [(0, 126), (143, 126), (145, 377), (0, 380)], (*GRAPHITE, 255))
poly(d, [(11, 139), (82, 152), (132, 261), (135, 340), (100, 365), (0, 358)], (*PANEL, 255))
poly(d, [(197, 140), (446, 135), (488, 192), (487, 307), (220, 312), (211, 242)], (*GRAPHITE, 255))
poly(d, [(0, 400), (510, 397), (510, 453), (0, 460)], (*GRAPHITE, 255))
poly(d, [(0, 464), (512, 459), (512, 512), (0, 512)], (*MIDNIGHT, 255))

# The narrow yellow/red stock canopy areas are replaced with smoked silver
# glass and thin aqua highlights.
poly(d, [(55, 84), (214, 84), (213, 115), (55, 115)], (*SILVER, 255))
poly(d, [(60, 90), (204, 90), (199, 107), (60, 107)], (22, 49, 59, 255))
poly(d, [(61, 90), (103, 90), (97, 106), (60, 106)], (68, 91, 98, 255))
poly(d, [(158, 90), (190, 90), (198, 106), (153, 106)], (68, 91, 98, 255))
line(d, [(55, 84), (214, 84)], (*AQUA, 255), 2)
ellipse(d, (180, 88, 208, 113), (16, 103, 110, 255), (*AQUA_LIGHT, 255), 1)

# Forward-arrow aero ribbons on the largest sidepod surfaces.
poly(d, [(207, 196), (337, 171), (481, 196), (479, 215), (333, 190), (220, 211)], (*AQUA, 255))
poly(d, [(217, 219), (332, 201), (476, 226), (475, 230), (329, 209), (220, 227)], (*GOLD, 255))
poly(d, [(212, 263), (352, 274), (480, 255), (481, 266), (351, 289), (212, 279)], (*AQUA_LIGHT, 255))
line(d, [(227, 302), (476, 302)], (*GOLD, 255), 1.4)

# Nose and wing stripes: each follows a broad UV island and has a separate
# gold pinline to keep the design legible at game distance.
poly(d, [(0, 144), (36, 148), (100, 355), (88, 373), (72, 364)], (*AQUA, 255))
poly(d, [(53, 144), (70, 146), (133, 301), (135, 332), (122, 339)], (*AQUA, 255))
line(d, [(42, 151), (96, 348)], (*GOLD, 255), 1.2)
poly(d, [(0, 386), (156, 399), (270, 423), (427, 415), (512, 423), (512, 438), (426, 428), (267, 439), (149, 414), (0, 400)], (*AQUA, 255))
line(d, [(0, 404), (149, 418), (266, 443), (425, 432), (512, 441)], (*GOLD, 255), 1.3)
poly(d, [(0, 475), (101, 468), (194, 493), (323, 481), (511, 476), (511, 491), (325, 498), (195, 506), (100, 481), (0, 493)], (*AQUA, 255))
line(d, [(0, 498), (104, 487), (196, 510)], (*GOLD, 255), 1.1)

# Restrained race numbers, deliberately kept clear of the main stripe seams.
number(d, (337, 231), 38)
number(d, (309, 444), 26)

# Micro-markings resemble technical motorsport detailing without a sponsor
# logo or another organization's identity.
for x in (244, 252, 260):
    line(d, [(x, 155), (x + 13, 155)], (*SILVER, 255), 1)
for x in (401, 409, 417):
    line(d, [(x, 351), (x + 17, 351)], (*AQUA_LIGHT, 255), 1)

texture = canvas.resize((512, 512), Image.Resampling.LANCZOS)
texture.save(ROOT / "apex-noir-07.png", optimize=True)
texture.save(ROOT / "car1-ow1.rgb", format="SGI")
print("Rendered", ROOT / "apex-noir-07.png", "and", ROOT / "car1-ow1.rgb")
