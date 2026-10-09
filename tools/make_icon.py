"""Draw the cursor-buddy icon -> build/moodleclicky.ico (used by the Windows build)."""

from pathlib import Path

from PIL import Image, ImageDraw


def icon(size: int = 256, color: str = "#4f8cff") -> Image.Image:
    s = size / 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=int(14 * s), fill="#16171b")
    pts = [(0, 0), (0, 34), (9, 26), (16, 42), (23, 39), (16, 24), (28, 24)]
    d.polygon([((17 + x) * s, (10 + y) * s) for x, y in pts], fill=color, outline="white", width=max(1, int(s)))
    for ex, ey in ((22, 25), (28, 28)):
        r, pr = 3.2 * s, 1.5 * s
        d.ellipse(((ex * s) - r, (ey * s) - r, (ex * s) + r, (ey * s) + r), fill="white")
        d.ellipse(((ex * s) - pr, (ey * s) - pr, (ex * s) + pr, (ey * s) + pr), fill="#111")
    return img


if __name__ == "__main__":
    out = Path(__file__).resolve().parents[1] / "build"
    out.mkdir(exist_ok=True)
    icon().save(out / "moodleclicky.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128),
                                                  (256, 256)])
    icon().save(out / "moodleclicky.png")
    print("wrote", out / "moodleclicky.ico")
