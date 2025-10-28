# demo_draw.py
# Demonstrates: drawXBMfile, drawPBMfile, drawBitmap1

import time, math, os

# Tiny 16x16 smiley in 1-bpp packed rows (MSB-first), 2 bytes per row
SMILEY_16x16 = [
    0b00000000, 0b00000000,
    0b00011111, 0b11100000,
    0b00100000, 0b00010000,
    0b01000110, 0b01100000,
    0b10001001, 0b00100000,
    0b10000000, 0b00100000,
    0b10000000, 0b00100000,
    0b10010000, 0b00100000,
    0b10001001, 0b00100000,
    0b10000110, 0b01100000,
    0b10000000, 0b00100000,
    0b10010000, 0b00100000,
    0b10001111, 0b11100000,
    0b01000000, 0b00000000,
    0b00100000, 0b00000000,
    0b00011111, 0b11100000,
]

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
