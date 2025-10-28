#!/usr/bin/env python3
# u8g2_live_exec_v3.py
#
# Live-reload u8g2-style LCD prototyper (Tk + Pillow) with bitmap cache.
#
# Run:
#   python u8g2_sim.py --file demo/demo_draw.py --width 128 --height 64 --scale 6 --aspect 1.116 --cache-size 64
#
# SECURITY: This executes the contents of --file. Only use trusted files.

import argparse
import os
import sys
import time
from collections import OrderedDict
from typing import Optional, Tuple, Sequence

try:
    import tkinter as tk
except Exception as e:
    print("Error importing tkinter:", e)
    sys.exit(1)

try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk, ImageOps, BdfFontFile
except Exception as e:
    print("Pillow required. Install with: pip install pillow\n", e)
    sys.exit(1)


WHITE = 255
BLACK = 0


class _LRUCache:
    """Tiny LRU cache for processed monochrome bitmaps."""
    def __init__(self, max_items: int = 64):
        self.max_items = max(1, int(max_items))
        self._d = OrderedDict()  # key -> PIL.Image in mode '1'

    def get(self, key):
        if key in self._d:
            self._d.move_to_end(key)
            return self._d[key]
        return None

    def put(self, key, value):
        self._d[key] = value
        self._d.move_to_end(key)
        while len(self._d) > self.max_items:
            self._d.popitem(last=False)

    def clear(self):
        self._d.clear()


class U8G2SimLCD:
    """u8g2-like LCD with 8-bit framebuffer, Tk rendering, drawing/bitmap helpers, and a file-bitmap cache."""
    def __init__(self, width: int = 128, height: int = 64, scale: float = 6.0,
                 title: str = "u8g2 Live Exec", aspect: Optional[float] = None, invert: bool = False,
                 cache_size: int = 64,
                 u8g2_dir: str = "",):
        self.width = int(width)
        self.height = int(height)
        self.scale_x = float(scale)
        self.scale_y = float(scale if aspect is None else scale * float(aspect))
        self.title = title
        self.inverse = bool(invert)
        if u8g2_dir:
            self.u8g2_font_dir = os.path.join(u8g2_dir, "tools", "font", "bdf")
        else:
            self.u8g2_font_dir = None

        # 8-bit framebuffer and drawing context
        self.img = Image.new("L", (self.width, self.height), BLACK)
        self.draw = ImageDraw.Draw(self.img)

        # Font
        try:
            self.font = ImageFont.load_default()
        except Exception:
            self.font = None

        # State
        self.draw_color = WHITE
        self._frame_times = []
        self._show_fps = True

        # Bitmap cache for file-loaded images
        self._bmp_cache = _LRUCache(max_items=cache_size)

        # Tk setup
        self.root = tk.Tk()
        self.root.title(self.title)
        self.canvas = tk.Canvas(self.root, width=int(self.width*self.scale_x), height=int(self.height*self.scale_y),
                                bd=0, highlightthickness=0, background="#444444")
        self.canvas.pack()
        self.photo = None

        # Bind inverse toggle + cache clear
        self.root.bind("<KeyPress-i>", lambda e: self.setInverse(not self.inverse))
        self.root.bind("<KeyPress-c>", lambda e: self.clearBitmapCache())

        # Initial render
        self._render_to_tk()

    # ---- Aspect/invert control
    def setPixelAspect(self, ratio_y_over_x: float) -> None:
        self.scale_y = self.scale_x * float(ratio_y_over_x)
        self.canvas.config(width=int(self.width*self.scale_x), height=int(self.height*self.scale_y))

    def setInverse(self, on: bool) -> None:
        self.inverse = bool(on)

    # ---- Drawing primitives
    def clearBuffer(self) -> None:
        self.draw.rectangle((0, 0, self.width, self.height), fill=BLACK)

    def sendBuffer(self) -> None:
        self._render_to_tk()

    def setDrawColor(self, color: int) -> None:
        self.draw_color = WHITE if color else BLACK

    def drawPixel(self, x: int, y: int) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            self.img.putpixel((x, y), self.draw_color)

    def drawLine(self, x0: int, y0: int, x1: int, y1: int) -> None:
        self.draw.line((x0, y0, x1, y1), fill=self.draw_color)

    def drawBox(self, x: int, y: int, w: int, h: int) -> None:
        self.draw.rectangle((x, y, x + w - 1, y + h - 1), fill=self.draw_color)

    def drawFrame(self, x: int, y: int, w: int, h: int) -> None:
        self.draw.rectangle((x, y, x + w - 1, y + h - 1), outline=self.draw_color)

    def drawCircle(self, cx: int, cy: int, r: int) -> None:
        x0, y0, x1, y1 = cx - r, cy - r, cx + r, cy + r
        self.draw.ellipse((x0, y0, x1, y1), outline=self.draw_color)

    def drawDisc(self, cx: int, cy: int, r: int) -> None:
        x0, y0, x1, y1 = cx - r, cy - r, cx + r, cy + r
        self.draw.ellipse((x0, y0, x1, y1), fill=self.draw_color)

    def drawHLine(self, x: int, y: int, w: int) -> None:
        self.drawLine(x, y, x + w - 1, y)

    def drawVLine(self, x: int, y: int, h: int) -> None:
        self.drawLine(x, y, x, y + h - 1)

    def drawRFrame(self, x: int, y: int, w: int, h: int, r: int) -> None:
        try:
            self.draw.rounded_rectangle((x, y, x + w - 1, y + h - 1), radius=r, outline=self.draw_color)
        except Exception:
            self.drawFrame(x, y, w, h)

    def drawRBox(self, x: int, y: int, w: int, h: int, r: int) -> None:
        try:
            self.draw.rounded_rectangle((x, y, x + w - 1, y + h - 1), radius=r, fill=self.draw_color)
        except Exception:
            self.drawBox(x, y, w, h)

    def setFont(self, font_path: Optional[str] = None) -> None:
        if font_path:
            # Search order:
            # 1. local folder exactly as written (no extension check)
            # 2. fontcache folder (if exists) for .pil
            # 3. local folder for .pil
            # 4. local folder for .bpf (converted)
            # 5. u8g2 directory (if known)

            font_path_bdf = None

            if os.path.isfile(font_path):
                pass
            elif os.path.isfile(os.path.join("fontcache", font_path + ".pil")):
                font_path = os.path.join("fontcache", font_path + ".pil")
            elif os.path.isfile(font_path + ".pil"):
                font_path = font_path + ".pil"
            elif os.path.isfile(font_path + ".bdf"):
                font_path_bdf = font_path + ".bdf"
            elif self.u8g2_font_dir and os.path.isfile(os.path.join(self.u8g2_font_dir, font_path + ".bdf")):
                font_path_bdf = os.path.join(self.u8g2_font_dir, font_path + ".bdf")
            else:
                #Will error out below, no seperate list
                pass

            if font_path_bdf:
                #Convert font, save in cache
                with open(font_path_bdf,'rb') as fp:
                    p = BdfFontFile.BdfFontFile(fp)
                    os.makedirs("fontcache", exist_ok=True)
                    p.save(os.path.join("fontcache", font_path))

                    #Update path to be PIL
                    font_path = os.path.join("fontcache", font_path + ".pil")

            try:
                self.font = ImageFont.load(font_path)
            except Exception as e:
                print(f"Failed to load font '{font_path}': {e}")
                self.font = ImageFont.load_default()
        else:
            self.font = ImageFont.load_default()

    def getFontAscentDescent(self) -> Tuple[int, int]:
        if self.font is None:
            return (8, 2)
        try:
            return self.font.getmetrics()
        except Exception:
            return (8, 2)

    def drawStr(self, x: int, y: int, s: str) -> None:
        if self.font is None:
            self.font = ImageFont.load_default()
        ascent, _desc = self.getFontAscentDescent()
        self.draw.text((x, y - ascent), s, fill=self.draw_color, font=self.font)

    def drawUTF8(self, x: int, y: int, s: str) -> None:
        self.drawStr(x, y, s)

    # ---- Bitmap blitting (bytes) ----
    def drawBitmap1(self, x: int, y: int, w: int, h: int, data: Sequence[int],
                    stride: Optional[int] = None, invert: bool = False) -> None:
        """Blit a 1-bpp bitmap. Row-major, MSB-first per byte. stride defaults to ceil(w/8)."""
        if stride is None:
            stride = (w + 7) // 8
        if isinstance(data, (bytes, bytearray)):
            buf = data
        else:
            buf = bytes(int(b) & 0xFF for b in data)

        on_color = self.draw_color  # use current draw color for '1' bits
        for row in range(h):
            row_off = row * stride
            for col in range(w):
                b_i = row_off + (col // 8)
                bit = (buf[b_i] >> (7 - (col % 8))) & 1 if b_i < len(buf) else 0
                if invert:
                    bit ^= 1
                if bit:
                    if 0 <= x + col < self.width and 0 <= y + row < self.height:
                        self.img.putpixel((x + col, y + row), on_color)

    # Arduino-style convenience
    def drawBitmap(self, *a, **kw): self.drawBitmap1(*a, **kw)
    def drawXBM(self, x: int, y: int, w: int, h: int, data: Sequence[int]) -> None:
        self.drawBitmap1(x, y, w, h, data, stride=(w + 7)//8, invert=False)

    # ---- File-based blitting with cache ----
    def _load_image_mono_cached(self, path: str, invert: bool = False) -> Optional[Image.Image]:
        """Load and threshold a file to 1-bpp, using LRU cache keyed by (abspath, mtime, invert)."""
        try:
            abspath = os.path.abspath(path)
            st = os.stat(abspath)
            key = (abspath, int(st.st_mtime), bool(invert))
        except Exception:
            # If we can't stat, fall back to path-only key (less robust)
            key = (path, None, bool(invert))

        cached = self._bmp_cache.get(key)
        if cached is not None:
            return cached

        try:
            img = Image.open(path)
        except Exception as e:
            print(f"[BMP] open error: {e}")
            return None

        if img.mode not in ("1", "L"):
            img = img.convert("L")
        if img.mode == "L":
            img = img.point(lambda p: 255 if p >= 128 else 0).convert("1")
        if invert:
            img = ImageOps.invert(img.convert("L")).convert("1")
        self._bmp_cache.put(key, img)
        return img

    def _blit_PIL_image_mono(self, pil_img: Image.Image, x: int, y: int) -> None:
        """Plot '1' bits using current draw color."""
        w, h = pil_img.size
        px = pil_img.load()
        on_color = self.draw_color
        for j in range(h):
            for i in range(w):
                v = 1 if px[i, j] else 0
                if v and 0 <= x + i < self.width and 0 <= y + j < self.height:
                    self.img.putpixel((x + i, y + j), on_color)

    def drawXBMfile(self, path: str, x: int, y: int, invert: bool = False) -> None:
        img = self._load_image_mono_cached(path, invert=invert)
        if img is not None:
            self._blit_PIL_image_mono(img, x, y)

    def drawPBMfile(self, path: str, x: int, y: int, invert: bool = False) -> None:
        img = self._load_image_mono_cached(path, invert=invert)
        if img is not None:
            self._blit_PIL_image_mono(img, x, y)

    def clearBitmapCache(self) -> None:
        self._bmp_cache.clear()
        print("[SIM] Bitmap cache cleared")

    # ---- Render
    def _render_to_tk(self):
        out_w = int(self.width * self.scale_x)
        out_h = int(self.height * self.scale_y)
        img = self.img
        if self.inverse:
            img = ImageOps.invert(img.convert("L"))
        disp = img.resize((out_w, out_h), resample=Image.NEAREST).convert("RGB")
        self.photo = ImageTk.PhotoImage(disp)
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")

        # FPS overlay
        now = time.time()
        self._frame_times.append(now)
        self._frame_times = [t for t in self._frame_times if now - t <= 1.0]
        fps = len(self._frame_times)
        self.canvas.delete("fps_text")
        self.canvas.create_text(4, 4, text=f"{fps} FPS", anchor="nw", fill="#00ff00",
                                font=("Courier", max(8, int(self.scale_y) * 3 // 2)), tags="fps_text")


class LivePythonRenderer:
    """Watches a Python file. Expects it to define draw(lcd) or demo_draw(lcd)."""
    def __init__(self, lcd: U8G2SimLCD, path: str, poll_ms: int = 200):
        self.lcd = lcd
        self.path = path
        self.poll_ms = int(poll_ms)
        self._last_mtime = None
        self._module_env = None  # type: Optional[dict]
        self._func_name = None   # 'draw' or 'demo_draw'

    def _load(self) -> None:
        try:
            st = os.stat(self.path)
        except FileNotFoundError:
            self._show_message(f"Waiting for {os.path.basename(self.path)} ...")
            return
        if self._last_mtime is not None and st.st_mtime == self._last_mtime:
            return  # unchanged
        self._last_mtime = st.st_mtime

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                code = f.read()
        except Exception as e:
            self._show_message(f"Read error: {e}")
            return

        env = {"__name__": "__live_draw__", "__file__": self.path}
        try:
            compiled = compile(code, self.path, "exec")
            exec(compiled, env, env)
        except Exception as e:
            self._show_error("exec", e)
            return

        func = None
        for name in ("draw", "demo_draw"):
            candidate = env.get(name)
            if callable(candidate):
                func = candidate
                self._func_name = name
                break

        if func is None:
            self._show_message("No draw(lcd) or demo_draw(lcd) found")
            self._module_env = None
        else:
            self._module_env = env

    def _show_message(self, msg: str):
        self.lcd.clearBuffer()
        self.lcd.setDrawColor(1)
        y = 12
        for line in msg.splitlines():
            self.lcd.drawStr(2, y, line)
            y += 10
        self.lcd.sendBuffer()

    def _show_error(self, stage: str, e: Exception):
        self.lcd.clearBuffer()
        self.lcd.setDrawColor(1)
        self.lcd.drawStr(2, 12, f"{stage} error: {e.__class__.__name__}")
        self.lcd.drawStr(2, 24, str(e))
        self.lcd.sendBuffer()

    def start(self):
        def pump():
            try:
                self._load()
                if self._module_env:
                    func = self._module_env.get(self._func_name)
                    if callable(func):
                        try:
                            func(self.lcd)
                        except Exception as e:
                            self._show_error("draw", e)
            finally:
                self.lcd.root.after(self.poll_ms, pump)
        self.lcd.root.after(0, pump)


def main():
    ap = argparse.ArgumentParser(description="Live-reloading u8g2-style LCD prototyper (with bitmap cache)")
    ap.add_argument("--file", "-f", type=str, required=True, help="Path to Python file providing draw(lcd) or demo_draw(lcd)")
    ap.add_argument("--width", type=int, default=128, help="LCD width in pixels (default 128)")
    ap.add_argument("--height", type=int, default=64, help="LCD height in pixels (default 64)")
    ap.add_argument("--scale", type=float, default=6.0, help="Base pixel scale (X axis) (default 6.0)")
    ap.add_argument("--aspect", type=float, default=None, help="Pixel aspect ratio Y/X (e.g., 1.116); if omitted, uses 1.0")
    ap.add_argument("--invert", action="store_true", help="Invert the display (white-on-black view)")
    ap.add_argument("--poll", type=int, default=200, help="Polling interval in ms for file changes (default 200)")
    ap.add_argument("--cache-size", type=int, default=64, help="Bitmap cache size (number of images)")
    ap.add_argument("--u8g2-root", type=str, default="u8g2", help="Location of u8g2 root, used to find fonts")
    args = ap.parse_args()

    lcd = U8G2SimLCD(args.width, args.height, scale=args.scale, aspect=args.aspect, invert=args.invert,
                     cache_size=args.cache_size, u8g2_dir=args.u8g2_root)
    renderer = LivePythonRenderer(lcd, args.file, poll_ms=args.poll)
    renderer.start()
    lcd.root.mainloop()


if __name__ == "__main__":
    main()
