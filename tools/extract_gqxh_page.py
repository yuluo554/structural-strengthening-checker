"""把 gqxh 扫描 PDF 的整页（多图拼接）按内容流位置合成单张 PNG，便于目视核对公式。

用法: py -X utf8 extract_gqxh_page.py <pdf_path> <page_indexes_csv> <outdir>
"""
import io
import os
import re
import sys

import pypdf
from PIL import Image


def page_layout(page):
    """解析 content stream，返回 [(name, x, y, w, h)]（PDF 坐标，y 向上）。"""
    ops = page.get_contents().get_data().decode("latin-1")
    results = []
    # 逐 token 扫描，跟踪 cm 矩阵（简化：只处理 q/Q/cm/Do）
    stack = []
    ctm = [1, 0, 0, 1, 0, 0]

    def mul(m1, m2):
        # m1 then m2
        a1, b1, c1, d1, e1, f1 = m1
        a2, b2, c2, d2, e2, f2 = m2
        return [
            a1 * a2 + b1 * c2,
            a1 * b2 + b1 * d2,
            c1 * a2 + d1 * c2,
            c1 * b2 + d1 * d2,
            e1 * a2 + f1 * c2 + e2,
            e1 * b2 + f1 * d2 + f2,
        ]

    tokens = re.findall(r"/[A-Za-z0-9]+|[-\d.]+|[A-Za-z'\"]+", ops)
    i = 0
    num_stack = []
    while i < len(tokens):
        t = tokens[i]
        if re.match(r"^-?\d", t):
            num_stack.append(float(t))
        elif t == "q":
            stack.append(list(ctm))
            num_stack = []
        elif t == "Q":
            if stack:
                ctm = stack.pop()
            num_stack = []
        elif t == "cm" and len(num_stack) >= 6:
            m = num_stack[-6:]
            ctm = mul(m, ctm)
            num_stack = []
        elif t.startswith("/") and i + 1 < len(tokens) and tokens[i + 1] == "Do":
            name = t[1:]
            a, b, c, d, e, f = ctm
            results.append((name, e, f, abs(a), abs(d)))
        i += 1
    return results


def compose(pdf, page_index, out_path):
    r = pypdf.PdfReader(pdf)
    page = r.pages[page_index]
    layout = page_layout(page)
    xobjs = page["/Resources"]["/XObject"]
    imgs = {}
    for name, x, y, w, h in layout:
        if name not in xobjs and ("/" + name) in xobjs:
            name = "/" + name
        if name not in xobjs:
            continue
        obj = xobjs[name].get_object()
        if obj.get("/Subtype") != "/Image":
            continue
        data = obj.get_data() if obj.get("/Filter") == "/FlateDecode" else obj._data
        try:
            im = Image.open(io.BytesIO(data))
        except Exception:
            if obj.get("/Filter") == "/FlateDecode":
                cs = obj.get("/ColorSpace")
                if cs == "/DeviceRGB":
                    im = Image.frombytes("RGB", (obj["/Width"], obj["/Height"]), data)
                else:
                    im = Image.frombytes("L", (obj["/Width"], obj["/Height"]), data)
                    if obj.get("/ImageMask"):
                        im = im.point(lambda v: 255 - v).convert("RGB")
            else:
                continue
        if obj.get("/ImageMask"):
            im = im.point(lambda v: 255 - v).convert("RGB")
        im = im.convert("RGB")
        imgs[name] = (im, x, y, w, h)

    if not imgs:
        return False
    scale = 2.0  # 放大倍数（PDF pt -> px）
    W = max(x + w for _, x, y, w, h in imgs.values())
    H = max(y + h for _, x, y, w, h in imgs.values())
    canvas = Image.new("RGB", (int(W * scale), int(H * scale)), "white")
    # y 翻转（PDF 原点左下）
    for name, (im, x, y, w, h) in imgs.items():
        px, pw = int(x * scale), int(w * scale)
        ph = int(h * scale)
        py = int((H - y - h) * scale)
        im2 = im.resize((pw, ph))
        canvas.paste(im2, (px, py))
    canvas.save(out_path)
    return True


if __name__ == "__main__":
    pdf, pages_csv, outdir = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(outdir, exist_ok=True)
    for pi in [int(v) for v in pages_csv.split(",")]:
        out = os.path.join(outdir, f"page_{pi:03d}.png")
        ok = compose(pdf, pi, out)
        print(pi, "OK" if ok else "EMPTY", out)
