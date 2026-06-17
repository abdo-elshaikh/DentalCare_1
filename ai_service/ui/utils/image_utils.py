import math
from PIL import Image, ImageDraw, ImageFont
from typing import List, Dict, Any, Optional, Sequence, Tuple

def _get_font(size=12):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        return ImageFont.load_default()


def _norm_name(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "").replace("-", "").replace("_", "")


def _landmark_index(landmarks: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Build tolerant lookup by id, short name, and common ceph aliases."""
    aliases = {
        "sella": "s", "nasion": "n", "orbitale": "or", "porion": "po",
        "subspinale": "a", "apoint": "a", "apointsubspinale": "a",
        "supramentale": "b", "bpoint": "b", "bpointsupramentale": "b",
        "pogonion": "pog", "menton": "me", "gnathion": "gn", "gonion": "go",
        "lowerincisortip": "lit", "incisioninferius": "lit", "li": "lit",
        "upperincisortip": "uit", "incisionsuperius": "uit", "ui": "uit",
        "upperlip": "ul", "lowerlip": "ll", "subnasale": "sn",
        "softtissuepogonion": "pog'", "softtissuepogonionpog": "pog'",
        "posteriornasalspine": "pns", "anteriornasalspine": "ans",
        "articulare": "ar",
    }
    id_to_short = {
        1: "s", 2: "n", 3: "or", 4: "po", 5: "a", 6: "b", 7: "pog",
        8: "me", 9: "gn", 10: "go", 11: "lit", 12: "uit", 13: "ul",
        14: "ll", 15: "sn", 16: "pog'", 17: "pns", 18: "ans", 19: "ar",
    }
    idx: Dict[str, Dict[str, Any]] = {}
    for lm in landmarks:
        keys = []
        if lm.get("id") is not None:
            try:
                keys.extend([str(int(lm["id"])), id_to_short.get(int(lm["id"]), "")])
            except Exception:
                keys.append(str(lm.get("id")))
        name = str(lm.get("name") or "")
        keys.append(name)
        keys.append(name.split("(")[0])
        if "(" in name and ")" in name:
            keys.append(name[name.find("(") + 1:name.find(")")])
        for key in keys:
            nk = _norm_name(key)
            if nk:
                idx[nk] = lm
                if nk in aliases:
                    idx[_norm_name(aliases[nk])] = lm
    return idx


def _pt(lm: Optional[Dict[str, Any]]) -> Optional[Tuple[float, float]]:
    if not lm:
        return None
    return float(lm.get("x", 0)), float(lm.get("y", 0))


def _lookup(idx: Dict[str, Dict[str, Any]], *names: str) -> Optional[Tuple[float, float]]:
    for name in names:
        item = idx.get(_norm_name(name))
        if item is not None:
            return _pt(item)
    return None


def _line(draw: ImageDraw.ImageDraw, points: Sequence[Optional[Tuple[float, float]]], fill, width=2):
    clean = [p for p in points if p is not None]
    if len(clean) >= 2:
        draw.line(clean, fill=fill, width=width, joint="curve")


def _bezier_points(points: Sequence[Tuple[float, float]], steps: int = 28) -> List[Tuple[float, float]]:
    """Sample a quadratic/cubic Bezier curve."""
    if len(points) == 3:
        p0, p1, p2 = points
        return [
            (
                (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0],
                (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1],
            )
            for t in [i / steps for i in range(steps + 1)]
        ]
    if len(points) == 4:
        p0, p1, p2, p3 = points
        return [
            (
                (1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0] + 3 * (1 - t) * t ** 2 * p2[0] + t ** 3 * p3[0],
                (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1] + 3 * (1 - t) * t ** 2 * p2[1] + t ** 3 * p3[1],
            )
            for t in [i / steps for i in range(steps + 1)]
        ]
    return list(points)


def _curve(draw: ImageDraw.ImageDraw, points: Sequence[Optional[Tuple[float, float]]], fill, width=2):
    clean = [p for p in points if p is not None]
    if len(clean) == 2:
        draw.line(clean, fill=fill, width=width)
    elif len(clean) in (3, 4):
        draw.line(_bezier_points(clean), fill=fill, width=width, joint="curve")
    elif len(clean) > 4:
        draw.line(clean, fill=fill, width=width, joint="curve")


def _label(draw: ImageDraw.ImageDraw, xy: Tuple[float, float], text: str, font, fill):
    x, y = xy
    draw.text((x + 7, y - 16), text, fill=(20, 20, 20), font=font)
    draw.text((x + 6, y - 17), text, fill=fill, font=font)


def _draw_angle_arc(
    draw: ImageDraw.ImageDraw,
    center: Optional[Tuple[float, float]],
    p1: Optional[Tuple[float, float]],
    p2: Optional[Tuple[float, float]],
    radius: float,
    fill,
    width=1,
):
    if center is None or p1 is None or p2 is None:
        return
    a1 = math.degrees(math.atan2(p1[1] - center[1], p1[0] - center[0]))
    a2 = math.degrees(math.atan2(p2[1] - center[1], p2[0] - center[0]))
    if abs(a2 - a1) > 180:
        if a1 > a2:
            a2 += 360
        else:
            a1 += 360
    box = [center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius]
    draw.arc(box, start=a1, end=a2, fill=fill, width=width)


def _draw_reference_tracing(draw: ImageDraw.ImageDraw, idx: Dict[str, Dict[str, Any]], width: int, height: int):
    blue = (35, 82, 255)
    black = (12, 12, 12)
    gray = (245, 245, 245)

    s = _lookup(idx, "s", "sella")
    n = _lookup(idx, "n", "nasion")
    or_ = _lookup(idx, "or", "orbitale")
    po = _lookup(idx, "po", "porion")
    a = _lookup(idx, "a", "subspinale")
    b = _lookup(idx, "b", "supramentale")
    pog = _lookup(idx, "pog", "pogonion")
    me = _lookup(idx, "me", "menton")
    gn = _lookup(idx, "gn", "gnathion")
    go = _lookup(idx, "go", "gonion")
    lit = _lookup(idx, "lit", "lower incisor tip")
    uit = _lookup(idx, "uit", "upper incisor tip")
    ul = _lookup(idx, "ul", "upper lip")
    ll = _lookup(idx, "ll", "lower lip")
    sn = _lookup(idx, "sn", "subnasale")
    pog_soft = _lookup(idx, "pog'", "soft tissue pogonion")
    pns = _lookup(idx, "pns", "posterior nasal spine")
    ans = _lookup(idx, "ans", "anterior nasal spine")
    ar = _lookup(idx, "ar", "articulare")

    # Black construction lines like the reference cephalometric overlay.
    for pair in [(s, n), (po, or_), (go, me), (n, a), (n, b), (a, pog), (pns, ans), (uit, a), (lit, b)]:
        _line(draw, pair, black, width=1)

    # Blue anatomical tracing approximation. The model has 19 landmarks, so these
    # contours intentionally interpolate between available hard/soft-tissue points.
    if s and n and or_:
        _curve(draw, [s, ((s[0] + n[0]) / 2, min(s[1], n[1]) - height * 0.04), n, or_], blue, width=2)
    if po and ar and go:
        _curve(draw, [po, ar, go], blue, width=2)
    if go and me and pog and b:
        _curve(draw, [go, ((go[0] + me[0]) / 2, max(go[1], me[1]) + height * 0.05), me, pog], blue, width=2)
        _curve(draw, [pog, b], blue, width=2)
    if pns and ans and a:
        _curve(draw, [pns, ans, a], blue, width=2)
    if n and sn and ul and ll and pog_soft:
        _curve(draw, [n, sn, ul, ll], blue, width=2)
        _curve(draw, [ll, pog_soft], blue, width=2)
    if uit and lit:
        tooth_w = max(8, width * 0.006)
        _curve(draw, [(uit[0] - tooth_w, uit[1] - 12), uit, (uit[0] + tooth_w, uit[1] + 28)], blue, width=2)
        _curve(draw, [(lit[0] - tooth_w, lit[1] + 12), lit, (lit[0] + tooth_w, lit[1] - 28)], blue, width=2)
    if pns and go:
        mid = ((pns[0] + go[0]) / 2, (pns[1] + go[1]) / 2)
        _curve(draw, [pns, mid, go], blue, width=2)

    # Angle arcs at key analysis junctions.
    _draw_angle_arc(draw, n, s, a, 28, black, width=1)
    _draw_angle_arc(draw, n, s, b, 42, black, width=1)
    _draw_angle_arc(draw, me, go, n, 42, black, width=1)
    _draw_angle_arc(draw, a, n, uit, 28, gray, width=1)
    _draw_angle_arc(draw, b, n, lit, 28, gray, width=1)

def annotate_image(
    image: Image.Image,
    landmarks: List[Dict[str, Any]],
    draw_points: bool = True,
    show_lines: bool = True,
    show_labels: bool = True,
    show_scores: bool = False
) -> Image.Image:
    """Draw landmarks, labels, construction lines, and clinical tracing."""
    img = image.convert("RGB").copy()
    draw = ImageDraw.Draw(img)
    font = _get_font(max(12, int(min(image.size) * 0.018)))
    idx = _landmark_index(landmarks)

    if show_lines:
        _draw_reference_tracing(draw, idx, image.width, image.height)

    # Draw basic points and labels
    for lm in landmarks:
        x, y = lm.get("x", 0), lm.get("y", 0)
        label = str(lm.get("name") or lm.get("id", ""))
        
        if draw_points:
            r = max(3, int(min(image.size) * 0.004))
            draw.ellipse([(x - r, y - r), (x + r, y + r)], fill=(255, 30, 0), outline=(30, 30, 30), width=1)
            
        if show_labels and label:
            _label(draw, (x, y), label, font, fill=(255, 240, 0))
            
        if show_scores and "score" in lm:
            score = lm["score"]
            draw.text((x + 5, y + 5), f"{score:.2f}", fill=(0, 255, 255), font=font)

    return img

def draw_cartoon_outline(
    image: Image.Image,
    landmarks: List[Dict[str, Any]],
    blank_background: bool = False,
    px_to_mm: float = 1.0
) -> Image.Image:
    """Draw a simplified line-art/tracing of the cephalometric points."""
    if blank_background:
        img = Image.new("RGB", image.size, (255, 255, 255))
    else:
        img = image.convert("RGB").copy()

    draw = ImageDraw.Draw(img)
    idx = _landmark_index(landmarks)
    _draw_reference_tracing(draw, idx, image.width, image.height)

    for lm in landmarks:
        x, y = lm.get("x", 0), lm.get("y", 0)
        r = max(3, int(min(image.size) * 0.004))
        draw.ellipse([(x - r, y - r), (x + r, y + r)], fill=(255, 30, 0), outline=(30, 30, 30), width=1)
        label = str(lm.get("name") or lm.get("id", ""))
        if label:
            _label(draw, (x, y), label, _get_font(max(12, int(min(image.size) * 0.018))), fill=(255, 240, 0))

    return img
