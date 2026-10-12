"""Render docs/banner.png (README header) - the cursor buddy mid-sentence on a dark gradient."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
W, H = 1280, 400
ACCENT = (79, 140, 255)
CARD = (31, 32, 38)
INK = (236, 238, 243)
MUTED = (163, 168, 180)

FONT_DIRS = ["/usr/share/fonts/truetype/dejavu", "C:/Windows/Fonts"]


def font(names, size):
    for d in FONT_DIRS:
        for n in names:
            p = Path(d) / n
            if p.exists():
                return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def buddy(draw, x, y, k):
    pts = [(0, 0), (0, 34), (9, 26), (16, 42), (23, 39), (16, 24), (28, 24)]
    draw.polygon([(x + px * k, y + py * k) for px, py in pts], fill=ACCENT, outline="white", width=int(k * 1.2))
    for ex, ey in ((5, 15), (11, 18)):
        cx, cy, r, pr = x + ex * k, y + ey * k, 3 * k, 1.4 * k
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill="white")
        draw.ellipse((cx - pr + k * 0.6, cy - pr, cx + pr + k * 0.6, cy + pr), fill=(17, 17, 17))


def main():
    img = Image.new("RGB", (W, H))
    px = img.load()
    for yy in range(H):  # diagonal dark gradient
        for xx in range(W):
            t = (xx / W) * 0.6 + (yy / H) * 0.4
            px[xx, yy] = (int(18 + 14 * t), int(19 + 16 * t), int(26 + 34 * t))
    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).ellipse((60, 40, 460, 380), fill=110)
    glow = glow.filter(ImageFilter.GaussianBlur(70))
    img = Image.composite(Image.new("RGB", (W, H), ACCENT), img, glow.point(lambda v: v // 2))

    d = ImageDraw.Draw(img)
    buddy(d, 110, 95, 4.6)

    # speech bubble beside the buddy
    bx, by, bw, bh = 290, 120, 372, 104
    d.rounded_rectangle((bx, by, bx + bw, by + bh), radius=18, fill=CARD, outline=(74, 77, 88), width=2)
    d.polygon([(bx, by + 26), (bx - 14, by + 34), (bx, by + 44)], fill=CARD)
    d.text((bx + 20, by + 16), "2 / 4", font=font(["DejaVuSans-Bold.ttf", "segoeuib.ttf"], 15), fill=(108, 159, 255))
    body = font(["DejaVuSans.ttf", "segoeui.ttf"], 19)
    d.text((bx + 20, by + 40), "For each pass of the outer loop,", font=body, fill=INK)
    d.text((bx + 20, by + 66), "the inner loop runs n times again.", font=body, fill=INK)

    title = font(["DejaVuSans-Bold.ttf", "segoeuib.ttf"], 60)
    d.text((712, 104), "MoodleClicky", font=title, fill=INK)
    sub = font(["DejaVuSans.ttf", "segoeui.ttf"], 21)
    d.text((716, 186), "A study buddy that lives by your cursor.", font=sub, fill=MUTED)
    d.text((716, 218), "Double-tap Ctrl: it looks, points, explains.", font=sub, fill=MUTED)
    pill = font(["DejaVuSans-Bold.ttf", "segoeuib.ttf"], 15)
    x = 716
    for label in ("Windows", "Claude / DeepSeek", "Lecture notetaker"):
        tw = d.textlength(label, font=pill)
        d.rounded_rectangle((x, 274, x + tw + 24, 306), radius=16, fill=(38, 39, 46), outline=(56, 58, 67))
        d.text((x + 12, 281), label, font=pill, fill=INK)
        x += tw + 34

    out = ROOT / "docs" / "banner.png"
    img.save(out, optimize=True)
    print("wrote", out)


if __name__ == "__main__":
    main()
