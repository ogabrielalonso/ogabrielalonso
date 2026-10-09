"""One-off: turn the source photo into the card's printed halftone (ink layer, transparent paper).

Same ordered dither as the Focus AI HalftoneImage (Bayer 4x4, luminance^gamma + spread*bayer > 0.5);
paper shows where that test passes, ink everywhere else, so the result matches the GitHub avatar.
The source photo is not committed; only the output PNG ships.
"""
import sys

import numpy as np
from PIL import Image

BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16 - 0.5
GAMMA = 1.6
INK = (16, 16, 20)


def main(src, out, cols, rows, scale):
    img = np.asarray(Image.open(src).convert("L"), dtype=np.float64)
    h, w = img.shape
    # lift dark hair off the pure black background so the head keeps its contour
    yy = np.linspace(0, 1, h)[:, None]
    top = np.clip((0.5 - yy) / 0.12, 0, 1)
    hair = np.clip((img - 3) / 12, 0, 1) * np.clip((110 - img) / 40, 0, 1)
    img = img + img * 2.6 * hair * top
    # the black t-shirt reads as stray specks on the ink block: send it to the background
    low = np.clip((yy - 0.56) / 0.05, 0, 1)
    img = np.where(img < 70, img * (1 - low), img)
    # crop to the portrait slot aspect, centred on the face
    cw = int(h * cols / rows)
    x0 = max(0, (w - cw) // 2)
    crop = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).crop((x0, 0, x0 + cw, h))
    small = np.asarray(crop.resize((cols, rows), Image.LANCZOS), dtype=np.float64) / 255
    th = BAYER[np.arange(rows)[:, None] & 3, np.arange(cols)[None, :] & 3]
    paper = small ** GAMMA + th > 0.5
    rgba = np.zeros((rows, cols, 4), dtype=np.uint8)
    rgba[~paper] = (*INK, 255)
    Image.fromarray(rgba).resize((cols * scale, rows * scale), Image.NEAREST).save(out, optimize=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]))
