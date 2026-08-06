"""
cover_art.py

Draws the illustration that fills the empty lower half of the report cover, chosen to
match the project's industry — fields and a rising sun for agriculture, a plant and
chimneys for manufacturing, a mortarboard and books for education, and so on.

The art is DRAWN, not fetched: no downloads, no image files to ship, no licensing, and
it can never be missing at generation time. Everything is flat vector shapes in the
report's own indigo palette, sitting on a soft wash that fades up into the page, so it
reads as part of the cover rather than a picture dropped on top of it.

One entry point: `cover_art(industry) -> PNG bytes | None`. A missing matplotlib or an
unknown industry simply returns None and the cover renders as before.
"""

from __future__ import annotations

import io
import logging

logger = logging.getLogger("cover_art")

# the report's palette
DEEP = "#2B2BD4"
MID = "#5B5BF5"
SOFT = "#8F8FF8"
PALE = "#B9B9FB"
MIST = "#DCDCFC"
WASH = "#F2F2FE"

W, H = 6.4, 2.5          # inches — spans the cover's body column


def _mpl():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def _canvas():
    """A 100x40 field with a soft wash that fades upward into the page."""
    plt = _mpl()
    import numpy as np
    fig, ax = plt.subplots(figsize=(W, H))
    grad = np.linspace(1, 0, 256).reshape(-1, 1)
    ax.imshow(grad, extent=[0, 100, 0, 40], aspect="auto", origin="upper",
              cmap=_wash_cmap(), zorder=0, alpha=0.9)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 40)
    ax.axis("off")
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    return fig, ax


def _wash_cmap():
    from matplotlib.colors import LinearSegmentedColormap
    return LinearSegmentedColormap.from_list("wash", ["#FFFFFF", WASH])


def _ground(ax, y=8, color=MIST):
    ax.fill_between([0, 100], 0, y, color=color, zorder=1)


def _rect(ax, x, y, w, h, color, z=3, alpha=1.0):
    from matplotlib.patches import Rectangle
    ax.add_patch(Rectangle((x, y), w, h, color=color, zorder=z, alpha=alpha, lw=0))


def _poly(ax, pts, color, z=3, alpha=1.0):
    from matplotlib.patches import Polygon
    ax.add_patch(Polygon(pts, closed=True, color=color, zorder=z, alpha=alpha, lw=0))


def _circle(ax, x, y, r, color, z=2, alpha=1.0):
    from matplotlib.patches import Circle
    ax.add_patch(Circle((x, y), r, color=color, zorder=z, alpha=alpha, lw=0))


def _save(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=190, transparent=True,
                bbox_inches="tight", pad_inches=0)
    import matplotlib.pyplot as plt
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


# ── per-industry compositions ───────────────────────────────────────────────────
def _agriculture(ax):
    _circle(ax, 80, 28, 7.5, PALE, z=1)
    # two soft rolling bands, then the field the crop rows are rooted in
    ax.fill_between([0, 100], 0, [14, 20], color=MIST, zorder=1)
    ax.fill_between([0, 100], 0, [11, 16], color=PALE, zorder=2)
    _ground(ax, 12, SOFT)
    for x in range(7, 98, 9):                        # crop rows standing ON the field
        _poly(ax, [(x, 12), (x + 1.7, 23), (x + 3.4, 12)], MID, z=4)
        _rect(ax, x + 1.4, 12, 0.6, 8, DEEP, z=5)


def _manufacturing(ax):
    _ground(ax, 8, MIST)
    _rect(ax, 8, 8, 30, 16, SOFT)                    # shed
    _poly(ax, [(8, 24), (23, 32), (38, 24)], MID)
    for x in (44, 52, 60):                           # chimneys
        _rect(ax, x, 8, 5, 22, PALE)
        _rect(ax, x, 28, 5, 2, MID)
    for i in range(4):                               # windows
        _rect(ax, 12 + i * 7, 13, 4, 5, "#FFFFFF", z=4, alpha=0.75)
    _circle(ax, 78, 20, 8, PALE, z=2)                # gear
    _circle(ax, 78, 20, 4, WASH, z=3)
    for a in range(0, 360, 45):
        import math
        _rect(ax, 78 + 7.4 * math.cos(math.radians(a)) - 1,
              20 + 7.4 * math.sin(math.radians(a)) - 1, 2, 2, MID, z=3)


def _education(ax):
    _ground(ax, 8, MIST)
    for i, (w, c) in enumerate([(26, PALE), (20, SOFT), (14, MID)]):   # book stack
        _rect(ax, 12, 8 + i * 4, w, 3.2, c, z=3)
    _poly(ax, [(60, 24), (78, 30), (96, 24), (78, 18)], MID, z=3)      # mortarboard
    _rect(ax, 76.5, 14, 3, 5, SOFT, z=2)
    _poly(ax, [(96, 24), (96, 16), (94.5, 16), (94.5, 24)], DEEP, z=4)
    _circle(ax, 95.2, 15, 1.4, DEEP, z=4)


def _retail(ax):
    _ground(ax, 8, MIST)
    _rect(ax, 10, 8, 40, 15, SOFT)                   # shopfront
    for i in range(5):                               # awning
        _poly(ax, [(10 + i * 8, 23), (14 + i * 8, 28), (18 + i * 8, 23)],
              MID if i % 2 == 0 else PALE, z=4)
    _rect(ax, 20, 8, 8, 9, WASH, z=4)
    for i, (x, w, h) in enumerate([(60, 12, 14), (76, 10, 11), (89, 8, 9)]):  # bags
        _rect(ax, x, 8, w, h, [MID, SOFT, PALE][i], z=3)
        ax.plot([x + w * .3, x + w * .3], [8 + h, 8 + h + 3], color=DEEP, lw=1.4, zorder=4)
        ax.plot([x + w * .7, x + w * .7], [8 + h, 8 + h + 3], color=DEEP, lw=1.4, zorder=4)


def _restaurant(ax):
    _ground(ax, 8, MIST)
    _circle(ax, 30, 16, 11, SOFT, z=2)               # plate
    _circle(ax, 30, 16, 7, WASH, z=3)
    _rect(ax, 54, 10, 1.8, 18, MID, z=3)             # fork
    for i in range(3):
        _rect(ax, 52.6 + i * 1.6, 24, 1, 6, MID, z=3)
    _rect(ax, 66, 10, 1.8, 18, MID, z=3)             # knife
    _poly(ax, [(65.4, 28), (69, 28), (67, 34)], MID, z=3)
    for i, x in enumerate((80, 87, 94)):             # steam
        ax.plot([x, x + 2, x], [22 + i, 27 + i, 32 + i], color=PALE, lw=2.2, zorder=3)


def _hotel(ax):
    _ground(ax, 8, MIST)
    for i, (x, w, h, c) in enumerate([(10, 20, 24, PALE), (34, 16, 18, SOFT),
                                      (54, 22, 30, MID), (80, 14, 16, SOFT)]):
        _rect(ax, x, 8, w, h, c, z=3)
        for r in range(int(h // 5)):
            for cc in range(int(w // 6)):
                _rect(ax, x + 2 + cc * 6, 11 + r * 5, 3, 2.6, "#FFFFFF", z=4, alpha=0.7)


def _software(ax):
    _ground(ax, 8, MIST)
    _rect(ax, 14, 12, 44, 24, SOFT, z=2)             # screen
    _rect(ax, 17, 15, 38, 18, WASH, z=3)
    _rect(ax, 30, 8, 12, 4, PALE, z=2)
    for i, w in enumerate((22, 16, 26, 12)):         # code lines
        _rect(ax, 20, 29 - i * 4, w, 1.8, MID if i % 2 == 0 else PALE, z=4)
    nodes = [(72, 28), (86, 32), (94, 22), (78, 16), (90, 12)]
    for i in range(len(nodes) - 1):                  # network
        ax.plot([nodes[i][0], nodes[i + 1][0]], [nodes[i][1], nodes[i + 1][1]],
                color=PALE, lw=1.6, zorder=3)
    for x, y in nodes:
        _circle(ax, x, y, 2.4, MID, z=4)


def _hospital(ax):
    _ground(ax, 8, MIST)
    _rect(ax, 12, 8, 34, 22, SOFT, z=2)              # building
    _rect(ax, 25, 16, 8, 3, "#FFFFFF", z=4)          # cross
    _rect(ax, 27.5, 13.5, 3, 8, "#FFFFFF", z=4)
    pts_x = list(range(56, 100))
    pts_y = []
    for x in pts_x:
        t = x - 56
        pts_y.append(20 + (8 if t in (16, 18) else -6 if t == 17 else 0))
    ax.plot(pts_x, pts_y, color=MID, lw=2.4, zorder=4)


def _transport(ax):
    _ground(ax, 8, MIST)
    _rect(ax, 12, 12, 26, 13, MID, z=3)              # container body
    _poly(ax, [(38, 12), (50, 12), (50, 21), (44, 25), (38, 25)], SOFT, z=3)
    _circle(ax, 20, 11, 3.4, DEEP, z=4)
    _circle(ax, 44, 11, 3.4, DEEP, z=4)
    for i in range(6):                               # road dashes
        _rect(ax, 58 + i * 7, 9.5, 4, 1.2, PALE, z=3)


def _construction(ax):
    _ground(ax, 8, MIST)
    _rect(ax, 14, 8, 4, 28, SOFT, z=3)               # crane mast
    _rect(ax, 14, 32, 40, 3, MID, z=4)
    ax.plot([46, 46], [32, 20], color=DEEP, lw=1.4, zorder=4)
    _rect(ax, 43, 15, 6, 5, PALE, z=4)
    for i, (x, h) in enumerate([(62, 14), (74, 20), (86, 11)]):   # frames
        _rect(ax, x, 8, 10, h, PALE if i % 2 else SOFT, z=3)
        for r in range(int(h // 5)):
            _rect(ax, x, 8 + r * 5, 10, 0.8, MID, z=4)


def _mining(ax):
    _poly(ax, [(0, 8), (26, 34), (52, 8)], SOFT, z=2)
    _poly(ax, [(30, 8), (52, 30), (74, 8)], MID, z=3)
    _poly(ax, [(20, 34), (26, 34), (23, 38)], WASH, z=3)
    _ground(ax, 8, MIST)
    _rect(ax, 78, 8, 16, 10, PALE, z=3)              # tunnel mouth
    _circle(ax, 86, 18, 8, PALE, z=3)
    _circle(ax, 86, 16, 5, WASH, z=4)


def _renewable(ax):
    _ground(ax, 8, MIST)
    _circle(ax, 84, 28, 6.5, PALE, z=1)
    _rect(ax, 21, 8, 1.8, 24, SOFT, z=3)             # turbine
    _circle(ax, 22, 32, 1.6, DEEP, z=5)
    import math
    for a in (90, 210, 330):
        _poly(ax, [(22, 32),
                   (22 + 13 * math.cos(math.radians(a)), 32 + 13 * math.sin(math.radians(a))),
                   (22 + 11 * math.cos(math.radians(a + 12)),
                    32 + 11 * math.sin(math.radians(a + 12)))], MID, z=4)
    for i in range(3):                               # solar rows
        _poly(ax, [(46 + i * 16, 10), (60 + i * 16, 10), (57 + i * 16, 19), (43 + i * 16, 19)],
              MID if i % 2 == 0 else SOFT, z=3)


def _trading(ax):
    _ground(ax, 8, MIST)
    for i, (x, y, w, h, c) in enumerate([(10, 8, 18, 9, MID), (30, 8, 18, 9, SOFT),
                                         (14, 17, 18, 9, PALE), (50, 8, 18, 9, PALE)]):
        _rect(ax, x, y, w, h, c, z=3)
        _rect(ax, x, y + h / 2 - 0.4, w, 0.8, WASH, z=4)
    _poly(ax, [(74, 12), (98, 12), (94, 20), (78, 20)], SOFT, z=3)   # hull
    _rect(ax, 84, 20, 2, 10, MID, z=3)
    _poly(ax, [(86, 30), (86, 21), (95, 25)], MID, z=4)


def _media(ax):
    _ground(ax, 8, MIST)
    _rect(ax, 12, 12, 40, 24, SOFT, z=2)
    _rect(ax, 15, 15, 34, 18, WASH, z=3)
    _poly(ax, [(28, 20), (28, 28), (37, 24)], MID, z=4)              # play
    for i, (x, h) in enumerate([(64, 8), (71, 16), (78, 11), (85, 20), (92, 13)]):
        _rect(ax, x, 10, 4, h, [MID, PALE, SOFT, MID, PALE][i], z=3)  # equaliser


def _generic(ax):
    _ground(ax, 8, MIST)
    for i, (x, w, h, c) in enumerate([(14, 16, 14, PALE), (34, 14, 22, SOFT),
                                      (52, 18, 17, MID), (74, 14, 26, SOFT),
                                      (92, 8, 12, PALE)]):
        _rect(ax, x, 8, w, h, c, z=3)
    for i in range(5):
        _circle(ax, 20 + i * 18, 30 + (i % 2) * 4, 1.8, PALE, z=2)


_MOTIFS = {
    "agriculture": _agriculture, "manufacturing": _manufacturing, "textile": _manufacturing,
    "automobile": _manufacturing, "education": _education, "retail": _retail,
    "restaurant": _restaurant, "hotel": _hotel, "software": _software,
    "hospital": _hospital, "transport": _transport, "construction": _construction,
    "mining": _mining, "renewable_energy": _renewable, "trading": _trading,
    "media": _media, "other": _generic,
}


import os

PHOTO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "templates", "cover_images")


def _photo(key) -> bytes | None:
    """A real photograph for the industry, cropped to the cover band.

    Photographs read as a professional report cover in a way a drawn motif cannot, so
    they are preferred whenever one exists for the industry. Files live in
    templates/cover_images/<industry>.jpg — drop a new file in and it is picked up with
    no code change. (Bundled images are Unsplash-licensed: free for commercial use.)"""
    path = os.path.join(PHOTO_DIR, f"{key}.jpg")
    if not os.path.isfile(path):
        return None
    try:
        from PIL import Image
        im = Image.open(path).convert("RGB")
        # centre-crop to the cover's aspect, then size for print
        target = W / H
        w, h = im.size
        if w / h > target:                       # too wide -> trim the sides
            new_w = int(h * target)
            im = im.crop(((w - new_w) // 2, 0, (w - new_w) // 2 + new_w, h))
        else:                                    # too tall -> trim top/bottom, favour
            new_h = int(w / target)              # the middle where the subject sits
            top = int((h - new_h) * 0.4)
            im = im.crop((0, top, w, top + new_h))
        im = im.resize((int(W * 190), int(H * 190)), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=88, optimize=True)
        buf.seek(0)
        return buf.getvalue()
    except Exception:
        logger.warning("cover photo failed for %r", key, exc_info=True)
        return None


GENERATED_DIR = os.path.join(PHOTO_DIR, "generated")


def _ai_cover(project: dict) -> bytes | None:
    """A cover image made for THIS business, not for its industry bucket.

    The bundled photographs are one per industry key, so every manufacturer — a pickle
    unit, a steel fabricator — received the same welding photograph. This asks the image
    model for something that matches the actual business.

    Generated once and cached on disk: the image must not change between the Word and the
    PDF of the same report, and re-billing an image call on every download would be waste.
    Any failure returns None and the industry photograph is used, exactly as before.
    """
    try:
        from config import settings
        if not settings.OPENAI_API_KEY.strip():
            return None

        import re as _re
        pid = project.get("id") or _re.sub(
            r"[^a-z0-9]+", "_", str(project.get("title") or "project").lower())[:48]
        os.makedirs(GENERATED_DIR, exist_ok=True)
        cached = os.path.join(GENERATED_DIR, f"{pid}.jpg")
        if os.path.isfile(cached):
            with open(cached, "rb") as fh:
                return fh.read()

        title = str(project.get("title") or "").strip()
        industry = str(project.get("industry") or "").strip()
        activity = str(project.get("project_description") or "").strip()[:180]
        subject = ", ".join(x for x in (title, industry, activity) if x)
        prompt = (
            f"A clean, professional photograph for the cover of a financial report about: "
            f"{subject}. Show the real subject of this business — its product, premises or "
            f"work in progress. Documentary photography, natural light, calm neutral "
            f"colours, no people looking at the camera, no text, no logos, no charts, "
            f"no collage. Wide composition with room at the edges."
        )

        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY.strip(), timeout=120, max_retries=1)
        raw = None
        for model in (settings.OPENAI_IMAGE_MODEL.strip() or "gpt-image-1", "dall-e-3"):
            try:
                resp = client.images.generate(model=model, prompt=prompt,
                                              size="1536x1024", n=1)
                item = resp.data[0]
                b64 = getattr(item, "b64_json", None)
                if b64:
                    import base64
                    raw = base64.b64decode(b64)
                elif getattr(item, "url", None):
                    import urllib.request
                    raw = urllib.request.urlopen(item.url, timeout=60).read()
                if raw:
                    logger.info("cover: generated artwork with %s for %r", model, title)
                    break
            except Exception as exc:
                logger.info("cover: %s could not generate (%s); trying the next model",
                            model, str(exc)[:120])

        if not raw:
            return None

        from PIL import Image
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        target = W / H
        w, h = im.size
        if w / h > target:
            nw = int(h * target)
            im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
        else:
            nh = int(w / target)
            top = int((h - nh) * 0.4)
            im = im.crop((0, top, w, top + nh))
        im = im.resize((int(W * 190), int(H * 190)), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=88, optimize=True)
        data = buf.getvalue()
        with open(cached, "wb") as fh:
            fh.write(data)
        return data
    except Exception:
        logger.warning("cover: AI artwork failed; falling back to the industry image",
                       exc_info=True)
        return None


def cover_art(industry, project: dict | None = None) -> bytes | None:
    """Image for the cover's lower half.

    Preference order: artwork generated for THIS business, then the industry photograph,
    then a drawn motif. None if none of them can be produced.
    """
    if project:
        ai = _ai_cover(project)
        if ai:
            return ai

    try:
        from financial_engine.industry_calc.operating_models import get_operating_model
        m = get_operating_model(industry)
        key = m.key if m else "other"
    except Exception:
        key = "other"

    photo = _photo(key) or _photo("other")
    if photo:
        return photo

    draw = _MOTIFS.get(key, _generic)
    try:
        fig, ax = _canvas()
        draw(ax)
        return _save(fig)
    except Exception:
        logger.warning("cover art failed for %r", industry, exc_info=True)
        return None
