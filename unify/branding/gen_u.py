"""Unify Slicer "U" mark (issue #9). Same tile, colour, slant and size as the Snapmaker italic S mark.
Coordinates are in the 140-unit box used by splash_app_icon.svg."""
import math, io, struct, sys, pathlib
from PIL import Image, ImageDraw

TOP, BOT, CX = 33.3, 99.3, 68.4
STROKE, GAP = 13.0, 13.0           # leg width, inside gap
SLANT = math.tan(math.radians(10)) # italic slant like the S
YMID = (TOP + BOT) / 2

def polygon(n_arc=48):
    ro = GAP / 2 + STROKE           # outer radius
    ri = GAP / 2                    # inner radius
    cy = BOT - ro
    pts = [(CX - ro, TOP), (CX - ro, cy)]
    for i in range(1, n_arc):        # outer arc, left -> bottom -> right
        a = math.pi - math.pi * i / n_arc
        pts.append((CX + ro * math.cos(a), cy + ro * math.sin(a)))
    pts += [(CX + ro, cy), (CX + ro, TOP), (CX + ri, TOP), (CX + ri, cy)]
    for i in range(1, n_arc):        # inner arc, right -> bottom -> left
        a = math.pi * i / n_arc
        pts.append((CX + ri * math.cos(a), cy + ri * math.sin(a)))
    pts += [(CX - ri, cy), (CX - ri, TOP)]
    return [(x + (YMID - y) * SLANT, y) for x, y in pts]

POLY = polygon()

def svg_path(scale=1.0):
    return "M" + " L".join(f"{x*scale:.2f} {y*scale:.2f}" for x, y in POLY) + " Z"

def bbox(points):
    xs = [p[0] for p in points]; ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)

S_BOX = (45.02, 33.08, 94.98, 99.54)   # the S mark in the same 140-unit box

def redraw(img):
    """Replace the white S in a tile image with the U, keeping the tile."""
    img = img.convert("RGBA")
    w, h = img.size
    px = img.load()
    # glyph = bright pixels; tile colour = darkest opaque colour near the centre
    bright = [(x, y) for y in range(h) for x in range(w) if px[x, y][3] >= 250 and min(px[x, y][:3]) > 150 and abs(x - w / 2) < w * 0.3 and abs(y - h / 2) < h * 0.35]
    if not bright:
        return img
    gx0 = min(p[0] for p in bright); gx1 = max(p[0] for p in bright) + 1
    gy0 = min(p[1] for p in bright); gy1 = max(p[1] for p in bright) + 1
    tile = None
    for y in range(gy0, gy1):
        for x in range(gx0, gx1):
            r, g, b, a = px[x, y]
            if a == 255 and max(r, g, b) < 60:
                tile = (r, g, b); break
        if tile: break
    tile = tile or (0, 0, 0)
    glyph_col = max(((px[x, y][:3]) for x, y in bright), key=sum)
    # paint the S out (blend its pixels back to the tile colour, keep alpha)
    for x, y in bright + [(x, y) for y in range(max(0, gy0-2), min(h, gy1+2)) for x in range(max(0, gx0-2), min(w, gx1+2))]:
        r, g, b, a = px[x, y]
        if a > 0:
            px[x, y] = tile + (a,)
    # map the S box in this image onto the 140-unit box, then draw the U supersampled
    sx = (gx1 - gx0) / (S_BOX[2] - S_BOX[0]); sy = (gy1 - gy0) / (S_BOX[3] - S_BOX[1])
    s = (sx + sy) / 2
    ox = (gx0 + gx1) / 2 - (S_BOX[0] + S_BOX[2]) / 2 * s
    oy = (gy0 + gy1) / 2 - (S_BOX[1] + S_BOX[3]) / 2 * s
    k = 8
    mask = Image.new("L", (w * k, h * k), 0)
    ImageDraw.Draw(mask).polygon([((x * s + ox) * k, (y * s + oy) * k) for x, y in POLY], fill=255)
    mask = mask.resize((w, h), Image.LANCZOS)
    layer = Image.new("RGBA", (w, h), glyph_col + (255,))
    out = img.copy()
    out.paste(layer, (0, 0), mask)
    # keep the original alpha (tile shape)
    a0 = img.getchannel("A"); out.putalpha(a0)
    return out

def write_icns(src, dst):
    d = open(src, "rb").read(); off = 8; chunks = []
    while off < len(d):
        t = d[off:off+4]; n = struct.unpack(">I", d[off+4:off+8])[0]; chunks.append((t, d[off+8:off+n])); off += n
    out = b""; frames = {}
    for t, data in chunks:
        if data[:8] != b"\x89PNG\r\n\x1a\n":
            continue  # old raw ARGB 16/32 px frames and 'info': replaced by PNG icp4/icp5 below
        im = redraw(Image.open(io.BytesIO(data)))
        frames[t] = im
        b = io.BytesIO(); im.save(b, "PNG", optimize=True); b = b.getvalue()
        out += t + struct.pack(">I", len(b) + 8) + b
    src32 = frames.get(b"ic11") or frames.get(b"ic12")
    for t, size in ((b"icp4", 16), (b"icp5", 32)):
        b = io.BytesIO(); src32.resize((size, size), Image.LANCZOS).save(b, "PNG", optimize=True); b = b.getvalue()
        out = t + struct.pack(">I", len(b) + 8) + b + out
    open(dst, "wb").write(b"icns" + struct.pack(">I", len(out) + 8) + out)

def splash_svg():
    return ('<!-- Unify U logo -->\n<svg width="140" height="140" viewBox="0 0 140 140" fill="none" xmlns="http://www.w3.org/2000/svg">\n'
            '<rect width="140" height="140" rx="20" fill="#171717"/>\n'
            f'<path d="{svg_path()}" fill="#FFFFFF"/>\n</svg>\n')

def glyph_svg():
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024"><path d="{svg_path(1024/140)}" fill="#FFFFFF"/></svg>\n'

def apply(root):
    """Swap the S mark for the U mark in a source tree (run by unify/build_local_mac.sh after apply_unify.py)."""
    root = pathlib.Path(root)
    img = root / "resources" / "images"
    # Tracked file, so `git checkout -- .` resets it together with the images it stands for.
    splash = img / "splash_app_icon.svg"
    if splash.exists() and "Unify U logo" in splash.read_text():
        print("  U logo: already applied")
        return
    for f in sorted(img.glob("Snapmaker_Orca*.png")):
        redraw(Image.open(f)).save(f, optimize=True)
        print("  U logo:", f.name)
    icns = root / "resources" / "Icon.icns"
    write_icns(icns, icns)
    (img / "Snapmaker_Orca.icns").write_bytes(icns.read_bytes())
    (img / "splash_app_icon.svg").write_text(splash_svg())
    glyph = root / "resources" / "AppIcon.icon" / "Assets" / "glyph.svg"
    if glyph.parent.is_dir():
        glyph.write_text(glyph_svg())
    print("  U logo: Icon.icns, Snapmaker_Orca.icns, splash_app_icon.svg, AppIcon glyph.svg")

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--apply":
        apply(sys.argv[2])
        sys.exit(0)
    src, dst = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
    dst.mkdir(parents=True, exist_ok=True)
    for f in sorted(src.glob("Snapmaker_Orca*.png")):
        redraw(Image.open(f)).save(dst / f.name, optimize=True)
    write_icns(src / "Icon.icns", dst / "Icon.icns")
    (dst / "splash_app_icon.svg").write_text(splash_svg())
    (dst / "glyph.svg").write_text(glyph_svg())
    print("bbox", bbox(POLY))
