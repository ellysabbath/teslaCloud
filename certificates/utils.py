# certificates/utils.py

"""
Certificate utilities for Tesla Cloud  Institute (TCI).

Responsibilities
----------------
* ``generate_certificate_number`` — sequential number (TCI 0001, ...)
* ``build_verification_url``      — URL encoded in the QR code
* ``render_certificate_base64``   — draws the certificate as PNG
* ``_draw_signature``             — deterministic handwritten signature

Layout
------
* Cream background, dark-green outer border, gold inner border
* Corner ornaments, small TCI logo mark top-center
* Institute name + divider line + Certificate of Course Completion
* "This is to certify that" + candidate name (underlined)
* Body paragraph (≈ 200 words) mentioning the program
* "Issued on <date>"
* Two handwritten signatures, each above a printed name + title
* Gold TCI seal centered between the two signatures
* Certificate number bottom-left, QR code bottom-right
* Optional diagonal "PREVIEW" watermark for previews

Install requirements
--------------------
    pip install pillow qrcode
"""

from __future__ import annotations

import base64
import io
from datetime import date

from django.conf import settings
from django.db import transaction

from PIL import Image, ImageDraw, ImageFont

try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False


# ============================================================
# CONSTANTS
# ============================================================
CERT_PREFIX = "TCI"

CERT_SIGNATORIES = [
    {"title": "Executive Director", "name": "Elisha S. Mwanajela"},
    {"title": "Program Director", "name": "Ruth E. Sabbath"},
]

CANVAS_W = 1754
CANVAS_H = 1240

BG_COLOR = (248, 249, 246)
OUTER_BORDER = (30, 78, 66)
INNER_BORDER = (201, 162, 39)
TEXT_BLACK = (10, 10, 10)
TEXT_DARK_GREEN = (30, 78, 66)
TEXT_GREY = (107, 114, 128)
SEAL_GOLD = (229, 168, 60)
SEAL_GOLD_DARK = (176, 122, 34)
WATERMARK_FILL = (200, 200, 200)
SIGNATURE_INK = (22, 22, 92)


# ============================================================
# FONTS
# ============================================================
def _font(size: int, bold: bool = False, serif: bool = False) -> ImageFont.ImageFont:
    """
    Load a general-purpose font. Serif fonts are used for headline
    text so the certificate feels formal.
    """
    candidates: list[str] = []

    if serif:
        if bold:
            candidates += [
                "C:/Windows/Fonts/timesbd.ttf",
                "C:/Windows/Fonts/georgiab.ttf",
                "C:/Windows/Fonts/cambriab.ttf",
            ]
        else:
            candidates += [
                "C:/Windows/Fonts/times.ttf",
                "C:/Windows/Fonts/georgia.ttf",
                "C:/Windows/Fonts/cambria.ttf",
            ]
        candidates += [
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
            "/Library/Fonts/Times New Roman Bold.ttf"
            if bold
            else "/Library/Fonts/Times New Roman.ttf",
        ]
    else:
        if bold:
            candidates += [
                "C:/Windows/Fonts/arialbd.ttf",
                "C:/Windows/Fonts/segoeuib.ttf",
                "C:/Windows/Fonts/calibrib.ttf",
            ]
        else:
            candidates += [
                "C:/Windows/Fonts/arial.ttf",
                "C:/Windows/Fonts/segoeui.ttf",
                "C:/Windows/Fonts/calibri.ttf",
            ]
        candidates += [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/Library/Fonts/Arial Bold.ttf"
            if bold
            else "/Library/Fonts/Arial.ttf",
        ]

    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue

    return ImageFont.load_default()


def _script_font(size: int) -> ImageFont.ImageFont:
    """
    Load a cursive/script font for the handwritten signatures.
    Falls back to an italic serif if no script font is installed —
    still legible, still not a plain print font.
    """
    candidates = [
        # Windows
        "C:/Windows/Fonts/segoesc.ttf",
        "C:/Windows/Fonts/SCRIPTBL.TTF",
        "C:/Windows/Fonts/BRUSHSCI.TTF",
        "C:/Windows/Fonts/LHANDW.TTF",
        "C:/Windows/Fonts/ITCKRIST.TTF",
        # macOS
        "/Library/Fonts/Snell Roundhand.ttc",
        "/System/Library/Fonts/Noteworthy.ttc",
        # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue

    for path in (
        "C:/Windows/Fonts/timesi.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue

    return ImageFont.load_default()


# ============================================================
# NUMBER GENERATOR — WORI style: "TCI 0001"
# ============================================================
def generate_certificate_number(year: str | None = None) -> str:
    """
    Produce the next certificate number in the WORI style:

        TCI 0001
        TCI 0002
        ...

    Atomic. The counter resets each calendar year. The year is
    stored in ``CertificateSequence`` but is not printed.
    """
    from .models import CertificateSequence  # noqa: WPS433

    if year is None:
        year = str(date.today().year)

    with transaction.atomic():
        seq, _ = (
            CertificateSequence.objects
            .select_for_update()
            .get_or_create(year=year)
        )
        seq.last_sequence += 1
        seq.save(update_fields=["last_sequence", "updated_at"])
        return f"{CERT_PREFIX} {seq.last_sequence:04d}"


# ============================================================
# URL BUILDER — takes the certificate UUID
# ============================================================
def build_verification_url(certificate_id: str) -> str:
    """
    Build the URL encoded in the QR code:
        <FRONTEND_BASE_URL>/certificates/verify/<uuid>
    """
    base = getattr(settings, "FRONTEND_BASE_URL", "").rstrip("/")
    path = f"/certificates/verify/{certificate_id}"
    return f"{base}{path}" if base else path


# ============================================================
# HELPERS — QR
# ============================================================
def _qr_image(text: str, size: int = 220) -> Image.Image | None:
    if not HAS_QRCODE or not text:
        return None
    try:
        qr = qrcode.QRCode(
            version=None,
            box_size=10,
            border=2,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
        )
        qr.add_data(text)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        return img.convert("RGBA").resize((size, size), Image.LANCZOS)
    except Exception:
        return None


# ============================================================
# HELPERS — text layout
# ============================================================
def _center_text(draw, text, font, y, fill=TEXT_BLACK):
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
    except Exception:
        w = len(text) * (font.size // 2)
    draw.text(((CANVAS_W - w) / 2, y), text, font=font, fill=fill)


def _wrap_lines(draw, text, font, max_width):
    """Wrap text to fit within max_width (in pixels)."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        try:
            bbox = draw.textbbox((0, 0), test, font=font)
            w = bbox[2] - bbox[0]
        except Exception:
            w = len(test) * (font.size // 2)
        if w <= max_width or not current:
            current = test
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


# ============================================================
# HELPERS — seal
# ============================================================
def _draw_seal(canvas: Image.Image, cx: int, cy: int, radius: int = 55) -> None:
    """
    Draw the golden central seal with concentric rings and a
    monogram in the middle.
    """
    draw = ImageDraw.Draw(canvas)

    draw.ellipse(
        [(cx - radius, cy - radius), (cx + radius, cy + radius)],
        fill=SEAL_GOLD,
        outline=SEAL_GOLD_DARK,
        width=4,
    )
    inner = int(radius * 0.72)
    draw.ellipse(
        [(cx - inner, cy - inner), (cx + inner, cy + inner)],
        outline=SEAL_GOLD_DARK,
        width=2,
    )
    core = int(radius * 0.55)
    draw.ellipse(
        [(cx - core, cy - core), (cx + core, cy + core)],
        fill=SEAL_GOLD_DARK,
    )

    font = _font(int(radius * 0.55), bold=True)
    text = "TCI"
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
    except Exception:
        tw, th = radius, radius
    draw.text(
        (cx - tw / 2, cy - th / 2 - 4),
        text,
        font=font,
        fill=(255, 255, 255),
    )


# ============================================================
# HELPERS — handwritten signature
# ============================================================
def _draw_signature(
    canvas: Image.Image,
    name: str,
    *,
    x: int,
    y: int,
    width: int,
    color=SIGNATURE_INK,
    base_font_size: int = 46,
) -> None:
    """
    Draw a deterministic handwritten-style signature for ``name``.

    The name is drawn with a script font, characters are nudged
    along a subtle wave, and a tail flourish closes the signature.
    Same name → same signature every time, so certificate re-renders
    are identical.
    """
    seed = sum(ord(ch) for ch in name) or 1
    amplitude = 2 + (seed % 3)
    tail_len = 40 + (seed % 30)

    font = _script_font(base_font_size)
    temp_draw = ImageDraw.Draw(canvas)

    # Fit the signature into the available width.
    try:
        bbox = temp_draw.textbbox((0, 0), name, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
    except Exception:
        text_w = len(name) * (base_font_size // 2)
        text_h = base_font_size

    while text_w > width and base_font_size > 20:
        base_font_size -= 2
        font = _script_font(base_font_size)
        try:
            bbox = temp_draw.textbbox((0, 0), name, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
        except Exception:
            text_w = len(name) * (base_font_size // 2)
            text_h = base_font_size

    start_x = x + max(0, (width - text_w) // 2)
    start_y = y

    # Draw each character, nudging the baseline slightly.
    cursor_x = start_x
    for i, ch in enumerate(name):
        offset = int(amplitude * ((i % 3) - 1))
        char_font = font
        if i == 0:
            # First letter slightly larger — a personal touch.
            char_font = _script_font(base_font_size + 4)

        try:
            bbox = temp_draw.textbbox((0, 0), ch, font=char_font)
            ch_w = bbox[2] - bbox[0]
        except Exception:
            ch_w = base_font_size // 2

        temp_draw.text(
            (cursor_x, start_y + offset),
            ch,
            font=char_font,
            fill=color,
        )
        cursor_x += ch_w

    # Sweeping tail flourish.
    tail_start_x = start_x + text_w
    tail_start_y = start_y + text_h // 2
    steps = 12
    for s in range(steps):
        t0 = s / steps
        t1 = (s + 1) / steps
        x0 = tail_start_x + tail_len * t0
        y0 = tail_start_y + int(amplitude * 2 * (t0 - t0 * t0))
        x1 = tail_start_x + tail_len * t1
        y1 = tail_start_y + int(amplitude * 2 * (t1 - t1 * t1))
        temp_draw.line([(x0, y0), (x1, y1)], fill=color, width=2)

    # Small underline flourish.
    flourish_y = y + text_h + 10
    temp_draw.line(
        [
            (start_x + 10, flourish_y),
            (start_x + text_w * 0.6, flourish_y + 3),
        ],
        fill=color,
        width=2,
    )


# ============================================================
# MAIN RENDERER → BASE64 DATA URL
# ============================================================
def render_certificate_base64(
    *,
    certificate_number: str,
    candidate_name: str,
    candidate_photo_data_url: str | None = None,   # accepted, unused
    course_title: str,
    grade: str | None = None,
    final_percentage: float | None = None,
    issue_date,
    verification_url: str,
    watermarked: bool = False,
) -> str:
    """
    Draw the certificate and return a data URL of the form
    ``data:image/png;base64,iVBORw0KGgo...``.

    ``candidate_photo_data_url`` is accepted for backward
    compatibility but is not used — the design does not include a
    photo.
    """
    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), BG_COLOR)
    draw = ImageDraw.Draw(canvas)

    # ---------- borders ----------
    draw.rectangle(
        [(25, 25), (CANVAS_W - 25, CANVAS_H - 25)],
        outline=OUTER_BORDER,
        width=10,
    )
    draw.rectangle(
        [(50, 50), (CANVAS_W - 50, CANVAS_H - 50)],
        outline=INNER_BORDER,
        width=4,
    )

    # ---------- watermark (drawn under everything) ----------
    if watermarked:
        wm = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))

        wm_font = _font(240, bold=True)
        wm_layer = Image.new("RGBA", (1400, 400), (0, 0, 0, 0))
        ImageDraw.Draw(wm_layer).text(
            (40, 60),
            "PREVIEW",
            font=wm_font,
            fill=(*WATERMARK_FILL, 110),
        )
        wm_layer = wm_layer.rotate(30, expand=1, resample=Image.BICUBIC)

        cap_font = _font(48)
        cap_layer = Image.new("RGBA", (1400, 100), (0, 0, 0, 0))
        ImageDraw.Draw(cap_layer).text(
            (40, 10),
            "Not valid for verification",
            font=cap_font,
            fill=(*WATERMARK_FILL, 130),
        )
        cap_layer = cap_layer.rotate(30, expand=1, resample=Image.BICUBIC)

        lw, lh = wm_layer.size
        wm.paste(wm_layer, ((CANVAS_W - lw) // 2, (CANVAS_H - lh) // 2), wm_layer)
        cw, ch = cap_layer.size
        wm.paste(cap_layer, ((CANVAS_W - cw) // 2, CANVAS_H // 2 + 200), cap_layer)

        canvas.alpha_composite(wm)
        draw = ImageDraw.Draw(canvas)

    # ---------- corner ornaments ----------
    orn = 30
    for x in (45, CANVAS_W - 45 - orn):
        draw.rectangle(
            [(x, 45), (x + orn, 45 + orn)],
            outline=INNER_BORDER,
            width=3,
        )
        draw.rectangle(
            [(x, CANVAS_H - 45 - orn), (x + orn, CANVAS_H - 45)],
            outline=INNER_BORDER,
            width=3,
        )

    # ---------- logo mark (top center) ----------
    logo_box = 90
    logo_x = (CANVAS_W - logo_box) // 2
    logo_y = 110

    draw.rectangle(
        [(logo_x, logo_y), (logo_x + logo_box, logo_y + logo_box)],
        fill=(255, 255, 255),
        outline=INNER_BORDER,
        width=2,
    )
    draw.arc(
        [(logo_x + 10, logo_y + 25), (logo_x + logo_box - 10, logo_y + 60)],
        start=200,
        end=340,
        fill=TEXT_DARK_GREEN,
        width=4,
    )
    draw.line(
        [(logo_x + 20, logo_y + 65), (logo_x + logo_box - 20, logo_y + 65)],
        fill=SEAL_GOLD,
        width=4,
    )

    logo_font = _font(28, bold=True)
    try:
        bbox = draw.textbbox((0, 0), "TCI", font=logo_font)
        tw = bbox[2] - bbox[0]
    except Exception:
        tw = 50
    draw.text(
        (logo_x + (logo_box - tw) / 2, logo_y + 55),
        "TCI",
        font=logo_font,
        fill=TEXT_DARK_GREEN,
    )

    # ---------- headline ----------
    title_font = _font(58, bold=True, serif=True)
    _center_text(
        draw,
        "Tesla Cloud Institute",
        title_font,
        235,
        fill=TEXT_DARK_GREEN,
    )

    draw.line(
        [(300, 315), (CANVAS_W - 300, 315)],
        fill=TEXT_DARK_GREEN,
        width=2,
    )

    # ---------- subtitle ----------
    sub_font = _font(44, bold=True, serif=True)
    _center_text(
        draw,
        "Certificate of Course Completion",
        sub_font,
        345,
        fill=TEXT_DARK_GREEN,
    )

    # ---------- intro line ----------
    intro_font = _font(26)
    _center_text(
        draw,
        "This is to certify that",
        intro_font,
        430,
        fill=TEXT_BLACK,
    )

    # ---------- candidate name ----------
    name_font = _font(56, bold=True, serif=True)
    _center_text(draw, candidate_name, name_font, 470, fill=TEXT_BLACK)

    try:
        bbox = draw.textbbox((0, 0), candidate_name, font=name_font)
        name_w = bbox[2] - bbox[0]
    except Exception:
        name_w = len(candidate_name) * 30
    line_w = min(name_w + 80, CANVAS_W - 500)
    draw.line(
        [((CANVAS_W - line_w) / 2, 545), ((CANVAS_W + line_w) / 2, 545)],
        fill=TEXT_GREY,
        width=2,
    )

    # ---------- body paragraph ----------
    body_font = _font(24)
    body_text = (
        f"has successfully completed the program “{course_title}” at "
        "Tesla Cloud  Institute, demonstrating a comprehensive "
        "understanding of the required skills, practical competencies, and "
        "professional standards expected in the field. Throughout the "
        "program, the candidate has shown commitment, discipline, and "
        "dedication toward achieving the learning outcomes. This "
        "certificate is awarded in recognition of the successful "
        "completion of all course requirements and confirms that the "
        "holder is hereby recognized as a certified graduate of the "
        "program."
    )
    body_lines = _wrap_lines(draw, body_text, body_font, CANVAS_W - 320)
    body_y = 575
    for line in body_lines:
        _center_text(draw, line, body_font, body_y, fill=TEXT_BLACK)
        body_y += 32

    # ---------- issued on ----------
    issued_font = _font(26)
    issued_text = f"Issued on {issue_date.strftime('%B %d, %Y')}"
    _center_text(draw, issued_text, issued_font, body_y + 15, fill=TEXT_BLACK)

    # ---------- signatures + seal ----------
    sig_y = CANVAS_H - 235
    left_x = 210
    right_x = CANVAS_W - 560
    line_w_sig = 320

    printed_name_font = _font(26, bold=True, serif=True)
    printed_title_font = _font(20)

    # Left signature — Executive Director
    _draw_signature(
        canvas,
        CERT_SIGNATORIES[0]["name"],
        x=left_x,
        y=sig_y - 20,
        width=line_w_sig,
    )
    draw = ImageDraw.Draw(canvas)
    draw.line(
        [(left_x, sig_y), (left_x + line_w_sig, sig_y)],
        fill=TEXT_BLACK,
        width=2,
    )
    draw.text(
        (left_x, sig_y + 10),
        CERT_SIGNATORIES[0]["name"],
        font=printed_name_font,
        fill=TEXT_BLACK,
    )
    draw.text(
        (left_x, sig_y + 50),
        CERT_SIGNATORIES[0]["title"],
        font=printed_title_font,
        fill=TEXT_BLACK,
    )

    # Right signature — Program Director
    _draw_signature(
        canvas,
        CERT_SIGNATORIES[1]["name"],
        x=right_x,
        y=sig_y - 20,
        width=line_w_sig,
    )
    draw = ImageDraw.Draw(canvas)
    draw.line(
        [(right_x, sig_y), (right_x + line_w_sig, sig_y)],
        fill=TEXT_BLACK,
        width=2,
    )
    draw.text(
        (right_x, sig_y + 10),
        CERT_SIGNATORIES[1]["name"],
        font=printed_name_font,
        fill=TEXT_BLACK,
    )
    draw.text(
        (right_x, sig_y + 50),
        CERT_SIGNATORIES[1]["title"],
        font=printed_title_font,
        fill=TEXT_BLACK,
    )

    # Center seal between the two signatures
    _draw_seal(canvas, CANVAS_W // 2, sig_y + 25, radius=58)
    draw = ImageDraw.Draw(canvas)

    # ---------- certificate number (bottom-left) ----------
    num_font = _font(24)
    draw.text(
        (95, CANVAS_H - 140),
        "Certificate No. ",
        font=num_font,
        fill=TEXT_BLACK,
    )
    try:
        bbox = draw.textbbox((0, 0), "Certificate No. ", font=num_font)
        num_x = 95 + (bbox[2] - bbox[0])
    except Exception:
        num_x = 95 + 160
    draw.text(
        (num_x, CANVAS_H - 140),
        certificate_number,
        font=_font(24, bold=True),
        fill=SEAL_GOLD_DARK,
    )

    # ---------- QR code (bottom-right) ----------
    qr_size = 180
    qr = _qr_image(verification_url, size=qr_size) if verification_url else None
    if qr:
        qr_x = CANVAS_W - 95 - qr_size
        qr_y = CANVAS_H - 95 - qr_size
        canvas.alpha_composite(qr, (qr_x, qr_y))

    # ---------- encode ----------
    out = io.BytesIO()
    canvas.convert("RGB").save(out, format="PNG", optimize=True)
    b64 = base64.b64encode(out.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"