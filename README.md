# U8G2 Python Simulator

This is a work in progress - many features untested, and API may change without warning!

A simple GUI simulator for the u8g2lib, useful when experimenting with LCD development. Rather than reflashing
your embedded system, you just get a window like this on screen:

![](doc/demo_screenshot.gif)

That window is generated from this Python source code:

```
def draw(lcd):
    t = time.time()
    W, H = lcd.width, lcd.height
    lcd.clearBuffer()

    lcd.setFont("b10")

    # Header
    lcd.setDrawColor(1)
    lcd.drawBox(0, 0, W, 12)
    lcd.setDrawColor(0)
    lcd.drawStr(2, 10, "u8g2 Simulator")
    lcd.setDrawColor(1)

    # drawBitmap1 demo (packed 1-bpp)
    lcd.drawBitmap1(2, 16, 16, 16, SMILEY_16x16)

    # Change fonts
    lcd.setFont("lubB18")
    lcd.drawStr(20, 16, "big boy")

    # Default font
    lcd.setFont(None)

    # Optional file-based icon example
    lcd.setDrawColor(0)
    here = os.path.dirname(__file__)
    wifi_xbm = os.path.join(here, "small_wifi.xbm")
    if os.path.isfile(wifi_xbm):
        lcd.drawXBMfile(wifi_xbm, 100, 2)

    lcd.setDrawColor(1)

    # Sine wave animation
    mid = H//2 + 12
    prev = None
    for x in range(W):
        y = int(mid + 10*math.sin((x + t*60)*math.pi/32))
        if prev: lcd.drawLine(prev[0], prev[1], x, y)
        prev = (x, y)

    # Status text
    lcd.drawStr(10, H - 2, time.strftime("%H:%M:%S"))
    lcd.sendBuffer()
```

Features:

* Similar API to Arduino (or C/C++) for easy copying
* Converts BPF fonts automatically, just need copy of u8g2 repository. Copies to local cache.
* Automatically reloads source file for real-time development
* Can save screenshot or animated GIF
* Adjustable aspect ratios
* tkinter based, minimal Python3 requirements

## Usage

* `git clone` repository
* Install Pillow with `pip install pillow`
* (Optional) Clone u8g2 somewhere
* Run the demo with `u8g2_sim.py -f demo/demo_draw.py`

I suggest to point to your u8g2 root directory with the ` --u8g2-root` option, like:
```u8g2_sim.py --u8g2-root ../u8g2 -f demo/demo_draw.py```

This will get you the required font files. I haven't yet converted the font names, so you
need to look at the font filenames and use that instead of the real u8g2 font names.

## Font Conversion/Caching

Fonts will be cached into a folder called `fontcache`. This will be relative to where you launch
the program from.