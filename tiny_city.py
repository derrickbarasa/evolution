#!/usr/bin/env python3
"""TINY CITY - an idle screen where civilisation evolves while you're away. See README.md."""
import argparse
import glob
import json
import math
import os
import pickle
import platform
import random
import subprocess
import sys
import time

try:
    import pygame
    from pygame._sdl2.video import Renderer, Texture, Window
except ImportError:
    sys.exit("Tiny City needs pygame 2:  pip install pygame")

# ----------------------------------------------------------------- layout
LH = 270            # pixel-art resolution height (width follows the screen shape)
LW = 480
GROUND = 206        # buildings stand on this line
ROAD_TOP, ROAD_BOT = 210, 226
LANE_R, LANE_L = 217, 225   # road lanes (vehicle bottoms)
WALK_Y = 209
RAIL_Y = 236
WATER_Y = 240
DAY_LEN = 160.0     # seconds for one day/night cycle

ERAS = ["Wilderness", "Stone Age", "Farming Village", "Medieval Town",
        "Industrial Age", "Modern City", "Metropolis", "Green Future"]
ERA_LINES = [
    "Nothing here yet but trees and deer...",
    "The first people arrive and light their fires.",
    "Fields are planted and wooden houses go up.",
    "Stone walls, windmills and a castle tower.",
    "Smokestacks rise. The first steam train arrives!",
    "Cars, apartment blocks and street lights.",
    "Skyscrapers scrape the sky.",
    "Electric cars, drones, solar towers and maglev trains.",
]
YEARS = [-10000, -8000, -3000, 1100, 1800, 1930, 2000, 2060, 2150]
DENSITY = [0.0, 0.30, 0.55, 0.68, 0.78, 0.84, 0.88, 0.90]   # share of land built on
SMOG = [0, 0, 0, 0.05, 0.40, 0.22, 0.15, 0.0]
POP = {"hut": 4, "house": 6, "field": 1, "stonehouse": 12, "tower": 20, "windmill": 3,
       "brick": 40, "factory": 25, "apartment": 160, "shop": 20, "skyscraper": 900,
       "stepped": 700, "glass": 1100, "forest": 800, "solar": 30}

TRAFFIC = {0: [], 1: [], 2: ["oxcart"], 3: ["horsecart"],
           4: ["carriage", "carriage", "bicycle"],
           5: ["vintage", "vintage", "vintage", "oldbus", "bicycle"],
           6: ["car", "car", "car", "car", "truck", "bus"],
           7: ["ev", "ev", "ev", "ebus", "bicycle", "scooter"]}
TRAFFIC_RATE = [0, 0, 0.12, 0.2, 0.35, 0.6, 1.0, 0.9]
WALK_RATE = [0, 0.08, 0.15, 0.2, 0.25, 0.35, 0.45, 0.45]
SPEED = {"oxcart": 10, "horsecart": 14, "carriage": 16, "bicycle": 12, "vintage": 22,
         "oldbus": 20, "car": 30, "truck": 26, "bus": 25, "ev": 32, "ebus": 26,
         "scooter": 13, "deer": 9, "walker": 8}
LENGTH = {"oxcart": 15, "horsecart": 15, "carriage": 15, "bicycle": 5, "vintage": 10,
          "oldbus": 18, "car": 11, "truck": 17, "bus": 20, "ev": 12, "ebus": 22,
          "scooter": 4, "deer": 5, "walker": 2}
CAR_COLORS = [(200, 50, 50), (50, 90, 190), (235, 235, 235), (240, 190, 40),
              (40, 40, 45), (60, 150, 90), (230, 120, 40), (150, 155, 165)]
OLD_COLORS = [(30, 30, 35), (40, 60, 45), (90, 30, 30), (40, 45, 70)]
EV_COLORS = [(240, 245, 250), (90, 200, 220), (120, 220, 150), (200, 205, 215), (250, 120, 160)]

SEASON_LEN = DAY_LEN * 3    # a year is 12 days
WEATHER = [         # chance of each kind of weather in spring, summer, autumn, winter
    {"clear": 0.45, "cloudy": 0.2, "rain": 0.3, "storm": 0.05},
    {"clear": 0.6, "cloudy": 0.15, "rain": 0.1, "storm": 0.15},
    {"clear": 0.35, "cloudy": 0.3, "rain": 0.3, "storm": 0.05},
    {"clear": 0.35, "cloudy": 0.25, "snow": 0.4},
]
CLOUD = {"clear": 0.0, "cloudy": 0.6, "rain": 0.8, "storm": 1.0, "snow": 0.7}
PRECIP = {"clear": 0.0, "cloudy": 0.0, "rain": 0.6, "storm": 1.0, "snow": 0.7}
AUTUMN_COLORS = [(215, 120, 40), (190, 65, 40), (225, 180, 60)]
FIREWORK_COLORS = [(255, 90, 90), (255, 220, 90), (120, 200, 255), (150, 255, 150), (240, 130, 255), (255, 255, 255)]
BUNTING_COLORS = [(220, 60, 60), (240, 200, 60), (60, 120, 210), (70, 170, 90), (230, 230, 230)]
BALLOON_COLORS = [(220, 60, 60), (240, 190, 40), (60, 120, 200), (80, 170, 90), (230, 120, 40)]
SNOW_COLOR = (232, 237, 243)

NIGHT = 0.0         # 0 = full day, 1 = full night (set every frame)
SHADED = {}         # sh() results for this frame's NIGHT
SNOW = 0.0          # how much snow lies on the ground, 0..1 (set every frame)
AUTUMN = 0.0        # how autumn-coloured the leaves are, 0..1 (set every frame)
BLOSSOM = 0.0       # spring blossom, 0..1 (set every frame)


# ----------------------------------------------------------------- helpers
def clamp(v, a=0.0, b=1.0):
    return a if v < a else b if v > b else v


def mix(c1, c2, t):
    t = 0.0 if t < 0.0 else 1.0 if t > 1.0 else t
    return (int(c1[0] + (c2[0] - c1[0]) * t),
            int(c1[1] + (c2[1] - c1[1]) * t),
            int(c1[2] + (c2[2] - c1[2]) * t))


def smooth(e0, e1, x):
    t = clamp((x - e0) / (e1 - e0))
    return t * t * (3 - 2 * t)


def sh(c, k=0.78):
    """Darken a colour as night falls."""
    key = (c, k)
    out = SHADED.get(key)
    if out is None:
        out = SHADED[key] = mix(c, (c[0] * 0.2, c[1] * 0.22, c[2] * 0.36), NIGHT * k)
    return out


def window_grid(s, x, top, w, h, R, day=(70, 90, 120), lit=(255, 214, 120),
                cw=4, ch=5, ww=2, wh=2, mx=2, my=3, chance=0.55):
    off = sh(day)
    on = mix(off, lit, NIGHT)
    y = top + my
    while y + wh <= top + h - 3:
        xx = x + mx
        while xx + ww <= x + w - mx:
            s.fill(on if R.random() < chance else off, (xx, y, ww, wh))
            xx += cw
        y += ch


def part(s, x, base, d, dx, dy, w, h, c):
    """Draw a rectangle relative to a moving thing: dx from its back, dy above its base."""
    rx = x + dx if d > 0 else x - dx - w
    s.fill(c, (int(rx), int(base - dy - h), w, h))


def fmt_year(y):
    y = int(y)
    if y < 0:
        return f"{-y:,} BC"
    if y < 1500:
        return f"{y} AD"
    return str(y)


# ----------------------------------------------------------------- buildings
def pick_building(level, w, rng):
    r = rng.random()
    if level == 1:
        return "hut", rng.randint(7, 10), int(r < 0.5)
    if level == 2:
        if r < 0.25:
            return "field", 5, 0
        return "house", rng.randint(11, 16), rng.randint(0, 1)
    if level == 3:
        if r < 0.15 and w <= 24:
            return "tower", rng.randint(32, 44), 0
        if r < 0.32:
            return "windmill", rng.randint(20, 26), 0
        return "stonehouse", rng.randint(14, 24), rng.randint(0, 2)
    if level == 4:
        if r < 0.35:
            return "factory", rng.randint(16, 24), rng.randint(40, 56)   # variant = chimney height
        return "brick", rng.randint(20, 38), rng.randint(0, 2)
    if level == 5:
        if r < 0.25:
            return "shop", rng.randint(14, 18), rng.randint(0, 3)
        return "apartment", rng.randint(30, 64), rng.randint(0, 3)
    if level == 6:
        if r < 0.35:
            return "stepped", rng.randint(70, 130), rng.randint(0, 2)
        return "skyscraper", rng.randint(55, 150), rng.randint(0, 3)
    if r < 0.14:
        return "solar", rng.randint(16, 24), 0
    if r < 0.42:
        return "forest", rng.randint(60, 120), 0
    return "glass", rng.randint(80, 175), rng.randint(0, 2)


class Plot:
    def __init__(self, x, w, rng):
        self.x, self.w = x, w
        self.rank = rng.random()
        self.kind, self.h, self.variant, self.level = "nature", 0, 0, 0
        self.seed = rng.randrange(1 << 30)
        self.tree_seed = rng.randrange(1 << 30)
        self.building, self.progress, self.build_time = False, 1.0, 1.0

    def start(self, era, rng, build_time):
        self.level = era
        self.kind, self.h, self.variant = pick_building(era, self.w, rng)
        self.seed = rng.randrange(1 << 30)
        self.building, self.progress, self.build_time = True, 0.0, build_time

    def full_height(self):
        if self.kind == "factory":
            return max(self.h, self.variant) + 4
        return self.h + 14


def leaf(c, x):
    """Leaf colour for the season: pink blossom in spring, orange in autumn, snowy in winter."""
    if BLOSSOM and x % 3 == 0:
        c = mix(c, (240, 170, 200), BLOSSOM)
    if AUTUMN:
        c = mix(c, AUTUMN_COLORS[x % 3], AUTUMN)
    if SNOW:
        c = mix(c, SNOW_COLOR, SNOW * 0.6)
    return c


def pine(s, x, base, h):
    s.fill(sh((90, 60, 40)), (x, base - 3, 1, 3))
    col = sh(mix((40, 110, 60), SNOW_COLOR, SNOW * 0.5))
    for i in range(3):
        top = base - h + i * h // 4
        bw = 2 + i * 2
        pygame.draw.polygon(s, col, [(x, top), (x - bw, top + h // 3), (x + bw, top + h // 3)])


def round_tree(s, x, base, r, col=(60, 140, 70)):
    col = leaf(col, x)
    s.fill(sh((100, 70, 45)), (x, base - 4, 1, 4))
    pygame.draw.circle(s, sh(col), (x, base - 3 - r), r)
    s.set_at((x - r // 2, base - 4 - r - r // 2), sh(mix(col, (255, 255, 200), 0.3)))


def draw_nature(s, p, era, t):
    R = random.Random(p.tree_seed)
    if era >= 5:   # tidy city park
        n = max(1, p.w // 11)
        for i in range(n):
            tx = p.x + 4 + (i * (p.w - 8)) // max(1, n - 1) if n > 1 else p.x + p.w // 2
            round_tree(s, tx, GROUND, R.randint(3, 5))
        bx = p.x + p.w // 2 - 2
        s.fill(sh((120, 80, 50)), (bx, GROUND - 2, 5, 1))
        s.fill(sh((90, 60, 40)), (bx, GROUND - 1, 1, 1))
        s.fill(sh((90, 60, 40)), (bx + 4, GROUND - 1, 1, 1))
        if era >= 7:
            for _ in range(p.w // 3):
                s.set_at((p.x + R.randrange(p.w), GROUND - 1),
                         sh(R.choice([(240, 90, 120), (250, 220, 80), (180, 120, 240)])))
    else:
        for _ in range(max(1, p.w // 7)):
            tx = p.x + 3 + R.randint(0, max(0, p.w - 6))
            if R.random() < 0.55:
                pine(s, tx, GROUND, R.randint(10, 19))
            else:
                round_tree(s, tx, GROUND, R.randint(3, 6), (70, 135, 60))


def draw_building(s, p, t):
    R = random.Random(p.seed)
    k, x, w, h, v, g = p.kind, p.x, p.w, p.h, p.variant, GROUND
    top = g - h

    if k == "hut":
        hw = min(w - 4, 14)
        cx = x + hw // 2 + 1
        if v:
            fx = min(x + w - 2, cx + hw // 2 + 3)
            f = abs(math.sin(t * 9 + p.seed))
            if NIGHT > 0.2:
                pygame.draw.circle(s, mix(sh((80, 120, 60)), (255, 160, 70), 0.4 * NIGHT), (fx, g - 1), 5)
        pygame.draw.polygon(s, sh((150, 110, 70)), [(cx - hw // 2, g), (cx, g - h), (cx + hw // 2, g)])
        pygame.draw.line(s, sh((110, 80, 50)), (cx, g - h), (cx - hw // 4, g - 1))
        pygame.draw.line(s, sh((110, 80, 50)), (cx, g - h), (cx + hw // 4, g - 1))
        pygame.draw.line(s, sh((100, 70, 45)), (cx - 2, g - h - 2), (cx + 2, g - h + 2))
        s.fill(sh((50, 35, 25)), (cx - 1, g - 3, 3, 3))
        if v:
            s.fill((255, int(110 + 120 * f), 40), (fx, g - 2 - int(f * 2), 1, 2 + int(f * 2)))
            s.fill((255, 80, 30), (fx - 1, g - 1, 3, 1))

    elif k == "house":
        bw = min(w - 4, 18)
        bx = x + (w - bw) // 2
        s.fill(sh((165, 115, 72)), (bx, top + 5, bw, h - 5))
        for yy in range(top + 7, g, 3):
            s.fill(sh((140, 95, 60)), (bx, yy, bw, 1))
        roof = sh((175, 70, 45)) if v else sh((205, 175, 90))
        pygame.draw.polygon(s, roof, [(bx - 2, top + 6), (bx + bw // 2, top), (bx + bw + 1, top + 6)])
        s.fill(sh((70, 45, 30)), (bx + 2, g - 5, 3, 5))
        s.fill(mix(sh((60, 50, 40)), (255, 190, 100), NIGHT), (bx + bw - 6, top + 8, 3, 2))

    elif k == "field":
        crop = mix((205, 175, 70) if R.random() < 0.5 else (95, 165, 60), SNOW_COLOR, SNOW)
        s.fill(sh((120, 90, 55)), (x, g - 2, w, 2))
        for xx in range(x + 1, x + w - 1, 2):
            sway = round(math.sin(t * 2 + xx * 0.5) * 0.7)
            s.fill(sh(crop), (xx + sway, g - 6, 1, 4))
        for xx in range(x, x + w, 4):
            s.fill(sh((120, 85, 50)), (xx, g - 4, 1, 4))
        s.fill(sh((120, 85, 50)), (x, g - 3, w, 1))

    elif k == "stonehouse":
        bw = min(w - 2, 22)
        bx = x + (w - bw) // 2
        wall = sh([(150, 145, 135), (135, 130, 125), (160, 150, 130)][v])
        s.fill(wall, (bx, top + 6, bw, h - 6))
        for _ in range(bw * h // 12):
            s.set_at((bx + R.randrange(bw), top + 6 + R.randrange(h - 6)), sh((115, 110, 105)))
        if v == 2:
            s.fill(wall, (bx, top + 3, bw, 3))
            for xx in range(bx, bx + bw, 3):
                s.fill(wall, (xx, top + 1, 2, 2))
        else:
            roof = sh((95, 60, 55)) if v == 0 else sh((70, 70, 95))
            pygame.draw.polygon(s, roof, [(bx - 1, top + 7), (bx + bw // 2, top), (bx + bw, top + 7)])
        window_grid(s, bx, top + 6, bw, h - 6, R, day=(60, 55, 50), lit=(255, 180, 90), cw=5, ch=6, chance=0.45)
        s.fill(sh((80, 55, 35)), (bx + bw // 2 - 1, g - 5, 3, 5))

    elif k == "tower":
        tw = min(w - 4, 12)
        bx = x + (w - tw) // 2
        wall = sh((150, 145, 140))
        s.fill(wall, (bx, top + 3, tw, h - 3))
        for xx in range(bx, bx + tw, 3):
            s.fill(wall, (xx, top, 2, 3))
        for yy in range(top + 8, g - 6, 7):
            s.fill(mix(sh((40, 35, 35)), (255, 180, 90), NIGHT), (bx + tw // 2, yy, 1, 3))
        fx = bx + tw // 2
        s.fill(sh((90, 80, 70)), (fx, top - 8, 1, 8))
        wave = round(math.sin(t * 4 + p.seed))
        pygame.draw.polygon(s, sh((200, 40, 40)), [(fx + 1, top - 8), (fx + 6, top - 7 + wave), (fx + 1, top - 5)])
        s.fill(sh((70, 50, 35)), (fx - 1, g - 5, 3, 5))

    elif k == "windmill":
        cx = x + w // 2
        pygame.draw.polygon(s, sh((225, 215, 195)), [(cx - 5, g), (cx - 3, top + 3), (cx + 3, top + 3), (cx + 5, g)])
        pygame.draw.polygon(s, sh((120, 70, 50)), [(cx - 4, top + 4), (cx, top - 1), (cx + 4, top + 4)])
        s.fill(sh((90, 60, 40)), (cx - 1, g - 4, 2, 4))
        hub = (cx, top + 2)
        for i in range(4):
            a = t * 1.2 + p.seed + i * math.pi / 2
            pygame.draw.line(s, sh((235, 228, 210)), hub, (hub[0] + math.cos(a) * 11, hub[1] + math.sin(a) * 11), 2)
        s.set_at(hub, sh((80, 60, 40)))

    elif k == "brick":
        col = [(155, 72, 52), (135, 62, 48), (170, 95, 65)][v]
        s.fill(sh(col), (x + 1, top, w - 2, h))
        s.fill(sh(mix(col, (40, 30, 30), 0.4)), (x, top, w, 2))
        window_grid(s, x + 1, top + 2, w - 2, h - 2, R, day=(70, 80, 100), lit=(255, 200, 110), chance=0.5)
        s.fill(sh((60, 40, 30)), (x + w // 2 - 1, g - 5, 3, 5))
        if R.random() < 0.6:
            s.fill(sh(mix(col, (0, 0, 0), 0.3)), (x + 4, top - 4, 2, 4))

    elif k == "factory":
        bx, bw = x + 1, w - 2
        s.fill(sh((120, 95, 85)), (bx, top, bw, h))
        for xx in range(bx, bx + bw - 7, 6):
            pygame.draw.polygon(s, sh((95, 80, 75)), [(xx, top), (xx + 5, top - 4), (xx + 5, top)])
        glow = mix(sh((70, 80, 90)), (255, 190, 90), NIGHT)
        s.fill(glow, (bx + 2, top + 4, bw - 8, 2))
        if h > 18:
            s.fill(glow, (bx + 2, top + 9, bw - 8, 2))
        s.fill(sh((80, 70, 65)), (bx + 3, g - 7, 6, 7))
        chx, ch_top = x + w - 6, g - v
        s.fill(sh((150, 70, 50)), (chx, ch_top, 4, v))
        s.fill(sh((225, 225, 225)), (chx, ch_top + 3, 4, 2))
        s.fill(sh((90, 60, 50)), (chx - 1, ch_top, 6, 1))

    elif k == "apartment":
        bx, bw = x + 1, w - 2
        col = [(220, 200, 165), (185, 195, 205), (205, 165, 145), (175, 195, 165)][v]
        s.fill(sh(col), (bx, top, bw, h))
        s.fill(sh(mix(col, (60, 60, 60), 0.35)), (bx - 1, top, bw + 2, 2))
        window_grid(s, bx, top, bw, h, R, day=(80, 100, 125), lit=(255, 215, 140),
                    cw=5, ch=6, ww=3, wh=3, mx=2, my=4)
        for yy in range(top + 8, g - 6, 6):
            s.fill(sh(mix(col, (90, 90, 90), 0.4)), (bx + 1, yy, bw - 2, 1))
        s.fill(sh((70, 60, 55)), (bx + bw // 2 - 2, g - 5, 4, 5))
        if v % 2 == 0:
            s.fill(sh((120, 90, 70)), (bx + 3, top - 5, 4, 3))
            s.fill(sh((80, 70, 60)), (bx + 3, top - 2, 1, 2))
            s.fill(sh((80, 70, 60)), (bx + 6, top - 2, 1, 2))
        else:
            s.fill(sh((90, 90, 95)), (bx + bw - 4, top - 6, 1, 6))
            s.fill(sh((90, 90, 95)), (bx + bw - 6, top - 5, 5, 1))

    elif k == "shop":
        bx, bw = x + 1, w - 2
        s.fill(sh([(230, 225, 210), (210, 200, 190), (220, 215, 200), (200, 210, 215)][v]), (bx, top, bw, h))
        aw = [(200, 60, 60), (60, 110, 200), (60, 160, 90), (225, 160, 40)][v]
        for i, xx in enumerate(range(bx - 1, bx + bw + 1, 2)):
            s.fill(sh(aw) if i % 2 == 0 else sh((240, 240, 240)), (xx, g - 9, 2, 3))
        s.fill(mix(sh((120, 160, 190)), (255, 220, 150), NIGHT), (bx + 2, g - 6, bw - 8, 5))
        s.fill(sh((80, 60, 50)), (bx + bw - 5, g - 6, 3, 6))
        neon = 0.3 + 0.6 * NIGHT * (math.sin(t * 3 + p.seed) > -0.3)
        s.fill(mix(sh(aw), (255, 255, 255), neon), (bx + 2, top + 1, bw - 4, 2))

    elif k == "skyscraper":
        bx, bw = x + 1, w - 2
        col = [(110, 125, 145), (90, 100, 122), (145, 152, 165), (80, 110, 140)][v]
        s.fill(sh(col), (bx, top, bw, h))
        s.fill(sh(mix(col, (255, 255, 255), 0.25)), (bx, top, 1, h))
        window_grid(s, bx, top + 2, bw, h - 2, R, day=mix(col, (170, 200, 230), 0.5), lit=(255, 240, 175),
                    cw=3, ch=4, mx=2, my=2, chance=0.6)
        s.fill(sh(mix(col, (30, 30, 40), 0.4)), (bx, top, bw, 3))
        ax = bx + bw // 2
        s.fill(sh((160, 160, 170)), (ax, top - 10, 1, 10))
        if (t + p.seed % 7) % 2 < 0.35:
            s.set_at((ax, top - 11), (255, 40, 40))
        s.fill(mix(sh((60, 70, 80)), (255, 230, 170), NIGHT * 0.8), (bx + 2, g - 4, bw - 4, 4))

    elif k == "stepped":
        bx, bw = x + 1, w - 2
        col = [(170, 160, 140), (150, 150, 160), (125, 140, 150)][v]
        tiers = [(bw, int(h * 0.5)), (bw - 6, int(h * 0.3)), (bw - 12, h - int(h * 0.5) - int(h * 0.3))]
        y = g
        for tw, th in tiers:
            if tw < 4:
                break
            tx = bx + (bw - tw) // 2
            y -= th
            s.fill(sh(col), (tx, y, tw, th))
            s.fill(sh(mix(col, (40, 40, 50), 0.35)), (tx, y, tw, 1))
            window_grid(s, tx, y, tw, th, R, day=(90, 110, 130), lit=(255, 225, 150), cw=3, ch=4, mx=1, my=2)
        ax = bx + bw // 2
        s.fill(sh((200, 200, 205)), (ax, y - 12, 1, 12))
        if (t + p.seed % 5) % 2.4 < 0.4:
            s.set_at((ax, y - 13), (255, 40, 40))

    elif k == "glass":
        bx, bw = x + 1, w - 2
        base = (85, 175, 195) if v != 1 else (110, 150, 210)
        c = sh(base, 0.6)
        if v == 0:
            pygame.draw.polygon(s, c, [(bx, top), (bx + bw - 1, top - 10), (bx + bw - 1, top)])
        elif v == 2:
            pygame.draw.ellipse(s, c, (bx, top - 7, bw, 14))
        s.fill(c, (bx, top, bw, h))
        s.fill(sh(mix(base, (255, 255, 255), 0.45), 0.6), (bx + 1, top, 2, h))
        s.fill(sh(mix(base, (255, 255, 255), 0.25), 0.6), (bx + bw // 2, top, 1, h))
        dim = sh(mix(base, (20, 40, 60), 0.3), 0.6)
        for yy in range(top + 3, g - 4, 4):
            s.fill(mix(dim, (170, 245, 255), NIGHT * (0.9 if R.random() < 0.7 else 0.15)), (bx + 3, yy, bw - 4, 1))
        if v == 1:
            for xx in range(bx, bx + bw - 1, 2):
                s.fill(sh((60, 170, 80)), (xx, top - 2 - R.randint(0, 1), 2, 3))
        s.fill(mix(sh((60, 90, 100)), (150, 255, 200), NIGHT * 0.8), (bx + 2, g - 4, bw - 4, 4))

    elif k == "forest":
        bx, bw = x + 1, w - 2
        s.fill(sh((215, 215, 205)), (bx, top, bw, h))
        window_grid(s, bx, top, bw, h, R, day=(120, 140, 150), lit=(255, 220, 150), cw=4, ch=6, mx=2, my=2)
        for i, yy in enumerate(range(top + 5, g - 4, 6)):
            s.fill(sh((170, 170, 165)), (bx - 1, yy, bw + 2, 1))
            for xx in range(bx + (i % 2) * 2, bx + bw, 4):
                pygame.draw.circle(s, sh(mix((45, 140, 65), (100, 195, 85), R.random())), (xx + 1, yy - 1), 2)
        for xx in range(bx + 2, bx + bw - 1, 4):
            pygame.draw.circle(s, sh((60, 160, 70)), (xx, top - 2), 3)

    elif k == "solar":
        bx, bw = x + 1, w - 2
        s.fill(sh((235, 235, 230)), (bx, top + 3, bw, h - 3))
        for xx in range(bx, bx + bw - 4, 5):
            pygame.draw.polygon(s, sh((40, 70, 150), 0.5), [(xx, top + 3), (xx + 4, top), (xx + 5, top), (xx + 1, top + 3)])
        s.fill(mix(sh((120, 170, 190)), (255, 230, 170), NIGHT), (bx + 2, top + 6, bw - 4, 3))
        s.fill(sh((80, 80, 85)), (bx + 3, g - 5, 3, 5))
        px = bx + bw - 3
        s.fill(sh((60, 180, 110)), (px, g - 6, 2, 6))
        s.set_at((px, g - 4), (190, 255, 130) if int(t * 2) % 2 else (40, 120, 70))


def draw_construction(s, p, t):
    s.fill(sh((120, 95, 70)), (p.x, GROUND - 1, p.w, 1))
    full = p.full_height()
    cur = int(full * p.progress)
    s.set_clip(pygame.Rect(p.x - 12, GROUND - cur, p.w + 24, cur + 1))
    draw_building(s, p, t)
    s.set_clip(None)
    pole = sh((150, 120, 80)) if p.level < 5 else sh((170, 170, 175))
    stop = GROUND - min(p.h, cur) - 3
    for xx in (p.x, p.x + p.w - 1):
        s.fill(pole, (xx, stop, 1, GROUND - stop))
    for yy in range(GROUND - 4, stop, -5):
        s.fill(pole, (p.x, yy, p.w, 1))
    if p.level >= 5:     # tower crane
        mx = p.x + p.w + 1
        ctop = GROUND - p.h - 16
        yel = sh((240, 190, 40))
        s.fill(yel, (mx, ctop, 1, GROUND - ctop))
        s.fill(yel, (p.x - 6, ctop, p.w + 10, 1))
        s.fill(sh((90, 90, 90)), (mx + 1, ctop, 3, 2))
        hx = int(p.x + p.w / 2 + math.sin(t * 0.8 + p.seed) * p.w / 3)
        hook_y = max(ctop + 2, GROUND - cur - 4)
        s.fill(sh((60, 60, 60)), (hx, ctop + 1, 1, hook_y - ctop))
        s.fill(sh((200, 80, 40)), (hx - 1, hook_y, 3, 2))
        if NIGHT > 0.3 and int(t * 1.5) % 2:
            s.set_at((mx, ctop - 1), (255, 40, 40))


# ----------------------------------------------------------------- moving things
def draw_mover(s, m, t):
    k, x, b, d = m["kind"], m["x"], m["base"], m["dir"]
    c = sh(m["color"])
    dark = sh((25, 25, 30))
    glass = mix(sh((150, 190, 210)), (255, 230, 160), NIGHT * 0.6)
    lamp = mix(dark, (255, 245, 180), NIGHT)
    step = int(t * 7 + m["seed"]) % 2

    def P(dx, dy, w, h, col):
        part(s, x, b, d, dx, dy, w, h, col)

    if k == "walker":
        P(step, 0, 1, 1, sh((40, 40, 60)))
        P(1 - step, 0, 1, 1, sh((40, 40, 60)))
        P(0, 1, 1, 2, c)
        P(0, 3, 1, 1, sh(m["skin"]))
        if m.get("dog"):
            P(-4, 0, 2, 1, sh((140, 100, 60)))
    elif k == "deer":
        brown = sh((150, 100, 60))
        P(0, 1 + step, 1, 1, brown)
        P(3, 1 + (1 - step), 1, 1, brown)
        P(0, 0, 1, 1, brown)
        P(3, 0, 1, 1, brown)
        P(0, 2, 4, 2, brown)
        P(4, 3, 1, 2, brown)
        P(4, 5, 1, 1, sh((90, 60, 40)))
    elif k == "oxcart":
        P(0, 1, 7, 3, sh((150, 110, 70)))
        P(2, 0, 2, 2, dark)
        P(1, 4, 1, 2, sh((170, 90, 60)))
        P(7, 2, 2, 1, sh((100, 80, 60)))
        P(9, 1, 5, 3, sh((120, 90, 70)))
        P(13, 3, 2, 2, sh((120, 90, 70)))
        P(9 + step, 0, 1, 1, sh((90, 70, 55)))
        P(12 - step, 0, 1, 1, sh((90, 70, 55)))
    elif k in ("horsecart", "carriage"):
        body = sh((140, 100, 60)) if k == "horsecart" else sh((30, 30, 35))
        P(0, 1, 8, 4 if k == "carriage" else 3, body)
        if k == "horsecart":
            P(0, 4, 8, 1, sh((220, 210, 190)))
        else:
            P(2, 3, 3, 1, glass)
        P(1, 0, 2, 2, dark)
        P(5, 0, 2, 2, dark)
        P(8, 2, 2, 1, sh((90, 70, 50)))
        P(10, 2, 4, 2, sh((110, 70, 40)))
        P(13, 3, 2, 3, sh((110, 70, 40)))
        P(10 + step, 0, 1, 2, sh((90, 60, 35)))
        P(13 - step, 0, 1, 2, sh((90, 60, 35)))
    elif k == "bicycle":
        P(0, 0, 1, 1, dark)
        P(4, 0, 1, 1, dark)
        P(1, 1, 3, 1, c)
        P(2, 2, 1, 2, sh(m["skin2"]))
        P(2, 4, 1, 1, sh(m["skin"]))
    elif k == "scooter":
        P(0, 0, 4, 1, dark)
        P(3, 1, 1, 3, dark)
        P(1, 1, 1, 3, c)
        P(1, 4, 1, 1, sh(m["skin"]))
    elif k == "vintage":
        P(0, 1, 10, 3, c)
        P(2, 4, 6, 3, c)
        P(3, 5, 4, 1, glass)
        P(1, 0, 2, 2, dark)
        P(7, 0, 2, 2, dark)
        P(9, 2, 1, 1, lamp)
    elif k == "oldbus":
        P(0, 1, 18, 7, c)
        P(0, 3, 18, 1, sh((230, 220, 190)))
        P(2, 5, 14, 2, glass)
        P(2, 0, 2, 2, dark)
        P(13, 0, 2, 2, dark)
        P(17, 2, 1, 1, lamp)
    elif k == "car":
        P(0, 1, 11, 3, c)
        P(2, 4, 6, 2, c)
        P(3, 4, 4, 1, glass)
        P(1, 0, 2, 2, dark)
        P(8, 0, 2, 2, dark)
        P(10, 2, 1, 1, lamp)
        P(0, 2, 1, 1, mix(sh((120, 30, 30)), (255, 40, 40), NIGHT))
    elif k == "truck":
        P(0, 1, 12, 8, sh(mix(m["color"], (255, 255, 255), 0.5)))
        P(12, 1, 5, 6, c)
        P(14, 4, 2, 2, glass)
        P(1, 0, 2, 2, dark)
        P(9, 0, 2, 2, dark)
        P(14, 0, 2, 2, dark)
        P(16, 2, 1, 1, lamp)
    elif k == "bus":
        P(0, 1, 20, 8, c)
        P(2, 5, 16, 2, glass)
        P(2, 0, 2, 2, dark)
        P(15, 0, 2, 2, dark)
        P(19, 2, 1, 1, lamp)
    elif k == "ev":
        glow = mix(dark, (80, 255, 170), 0.3 + 0.7 * NIGHT)
        P(1, 0, 10, 1, glow)
        P(0, 1, 12, 2, c)
        P(2, 3, 7, 2, glass)
        P(1, 3, 1, 1, c)
        P(9, 3, 1, 1, c)
        P(2, 0, 2, 1, dark)
        P(8, 0, 2, 1, dark)
        P(11, 1, 1, 1, mix(dark, (180, 255, 255), 0.5 + 0.5 * NIGHT))
    elif k == "ebus":
        P(0, 1, 22, 7, sh((240, 245, 245)))
        P(0, 2, 22, 1, sh((60, 200, 140)))
        P(2, 5, 18, 2, glass)
        P(4, 8, 12, 1, sh((40, 70, 150)))
        P(3, 0, 2, 2, dark)
        P(16, 0, 2, 2, dark)
        P(21, 2, 1, 1, mix(dark, (180, 255, 255), 0.5 + 0.5 * NIGHT))


def draw_train(s, tr, t):
    k, x, d, n = tr["kind"], tr["x"], tr["dir"], tr["cars"]
    b = RAIL_Y
    dark = sh((30, 30, 35))
    win = mix(sh((150, 180, 200)), (255, 225, 150), NIGHT)

    def P(dx, dy, w, h, col):
        part(s, x, b, d, dx, dy, w, h, col)

    L = n * 17
    if k == "maglev":
        P(0, 0, L + 16, 1, mix(dark, (100, 240, 255), 0.4 + 0.6 * NIGHT))
    for i in range(n):
        cx = i * 17
        if k == "steam":
            P(cx, 1, 16, 6, sh((130, 40, 35)))
            P(cx + 2, 4, 12, 2, win)
        elif k == "diesel":
            P(cx, 1, 16, 7, sh((200, 120, 40)))
            P(cx + 2, 5, 12, 2, win)
        elif k == "commuter":
            P(cx, 1, 16, 7, sh((190, 195, 200)))
            P(cx, 3, 16, 1, sh((50, 90, 180)))
            P(cx + 2, 5, 12, 2, win)
        else:
            P(cx, 2, 16, 6, sh((240, 245, 248)))
            P(cx, 3, 16, 1, sh((60, 200, 200)))
            P(cx + 1, 5, 14, 2, win)
        if k != "maglev":
            P(cx + 2, 0, 2, 1, dark)
            P(cx + 12, 0, 2, 1, dark)
    if k == "steam":
        P(L, 1, 5, 9, sh((40, 40, 45)))
        P(L + 1, 6, 3, 2, win)
        P(L + 5, 1, 10, 6, sh((30, 30, 35)))
        P(L + 11, 7, 2, 4, sh((30, 30, 35)))
        P(L + 15, 1, 1, 2, sh((180, 40, 40)))
        P(L + 2, 0, 2, 1, dark)
        P(L + 7, 0, 3, 1, dark)
        P(L + 11, 0, 3, 1, dark)
        P(L + 14, 4, 1, 1, mix(dark, (255, 230, 150), NIGHT))
    elif k in ("diesel", "commuter"):
        col = sh((200, 120, 40)) if k == "diesel" else sh((190, 195, 200))
        P(L, 1, 16, 8, col)
        P(L + 12, 5, 3, 2, win)
        P(L + 2, 0, 2, 1, dark)
        P(L + 12, 0, 2, 1, dark)
        P(L + 15, 2, 1, 1, mix(dark, (255, 240, 180), NIGHT))
    else:
        P(L, 2, 12, 6, sh((240, 245, 248)))
        P(L + 12, 2, 3, 4, sh((240, 245, 248)))
        P(L + 10, 5, 3, 2, win)
        P(L, 3, 15, 1, sh((60, 200, 200)))


def draw_boat(s, bt, t):
    k, x, b, d = bt["kind"], bt["x"], bt["base"], bt["dir"]

    def P(dx, dy, w, h, col):
        part(s, x, b, d, dx, dy, w, h, col)

    if k == "canoe":
        P(0, 0, 8, 2, sh((130, 85, 50)))
        P(4, 2, 1, 2, sh((170, 90, 60)))
    elif k == "sailboat":
        P(0, 0, 10, 2, sh((150, 100, 60)))
        P(5, 2, 1, 9, sh((90, 70, 50)))
        for i, w in enumerate((4, 3, 2, 1)):
            P(6, 3 + i * 2, w, 2, sh((240, 235, 220)))
    elif k == "steamboat":
        P(0, 0, 16, 3, sh((60, 40, 40)))
        P(3, 3, 9, 3, sh((235, 230, 220)))
        P(4, 4, 7, 1, mix(sh((100, 100, 110)), (255, 220, 140), NIGHT))
        P(9, 6, 2, 4, sh((170, 50, 40)))
    elif k == "motorboat":
        P(-3, 0, 3, 1, sh((230, 240, 250)))
        P(0, 0, 10, 2, sh((240, 240, 240)))
        P(0, 1, 10, 1, sh((200, 50, 50)))
        P(4, 2, 4, 2, mix(sh((120, 160, 190)), (255, 220, 150), NIGHT * 0.5))
    else:
        P(0, 0, 22, 3, sh((240, 245, 245)))
        P(0, 1, 22, 1, sh((60, 200, 160)))
        P(3, 3, 16, 3, mix(sh((130, 180, 200)), (200, 255, 240), NIGHT * 0.7))
        P(4, 6, 14, 1, sh((40, 70, 150)))


def draw_flyer(s, f, t):
    k, x, y, d = f["kind"], int(f["x"]), int(f["y"] + math.sin(t * 2 + f["seed"]) * 1.5), f["dir"]

    def P(dx, dy, w, h, col):
        part(s, x, y, d, dx, dy, w, h, col)

    if k == "bird":
        flap = int(t * 6 + f["seed"]) % 2
        col = sh((40, 40, 50))
        s.set_at((x, y), col)
        s.set_at((x - 1, y - flap), col)
        s.set_at((x + 1, y - flap), col)
    elif k == "biplane":
        P(0, 0, 7, 2, sh((190, 50, 40)))
        P(2, 3, 4, 1, sh((230, 220, 200)))
        P(2, -2, 4, 1, sh((230, 220, 200)))
        P(0, 2, 1, 2, sh((190, 50, 40)))
        P(7, 0, 1, 2, sh((60, 60, 60)) if int(t * 20) % 2 else sh((200, 200, 200)))
    elif k == "plane":
        P(0, 0, 9, 1, sh((230, 232, 238)))
        P(0, 1, 1, 2, sh((230, 232, 238)))
        P(4, -1, 2, 1, sh((200, 205, 215)))
        if int(t * 2 + f["seed"]) % 2:
            P(4, 0, 1, 1, (255, 50, 50))
    elif k == "drone":
        P(0, 0, 3, 1, sh((50, 55, 60)))
        P(-1, 1, 1, 1, sh((120, 120, 130)))
        P(3, 1, 1, 1, sh((120, 120, 130)))
        if int(t * 3 + f["seed"]) % 2:
            P(1, -1, 1, 1, (90, 255, 140))
        P(1, -2, 1, 1, sh((240, 160, 60)))
    elif k == "flycar":
        P(1, -1, 2, 1, mix((60, 160, 255), (160, 240, 255), (t * 5) % 1))
        P(8, -1, 2, 1, mix((60, 160, 255), (160, 240, 255), (t * 5 + 0.5) % 1))
        P(0, 0, 11, 2, sh(f["color"]))
        P(2, 2, 6, 2, mix(sh((150, 190, 210)), (255, 230, 160), NIGHT * 0.6))
    elif k == "balloon":
        i = int(f["seed"])
        a, b = BALLOON_COLORS[i % 5], BALLOON_COLORS[(i + 2) % 5]
        pygame.draw.circle(s, sh(a), (x, y - 10), 6)
        for dx in (-3, 0, 3):
            s.fill(sh(b) if dx else sh(a), (x + dx, y - 15, 1, 10))
        s.fill(sh(a), (x - 2, y - 5, 5, 2))
        rope = sh((90, 70, 50))
        s.set_at((x - 2, y - 2), rope)
        s.set_at((x + 2, y - 2), rope)
        s.fill(sh((130, 90, 50)), (x - 2, y - 1, 5, 3))
        if NIGHT > 0.3 and int(t * 5 + f["seed"]) % 3:
            s.set_at((x, y - 4), (255, 190, 80))


# ----------------------------------------------------------------- the world
class World:
    def __init__(self, era_seconds, seed=None):
        self.rng = random.Random(seed)
        self.era_seconds = era_seconds
        self.t = 0.0
        rng = self.rng
        self.plots = []
        x = rng.randint(0, 4)
        while x < LW - 14:
            w = min(rng.randint(16, 32), LW - x - 2)
            if w < 14:
                break
            self.plots.append(Plot(x, w, rng))
            x += w + rng.randint(2, 5)
        self.movers, self.trains, self.boats, self.flyers, self.smoke = [], [], [], [], []
        self.stars = [(rng.randrange(LW), rng.randrange(140), rng.uniform(0.4, 1.0)) for _ in range(110)]
        self.clouds = [[rng.uniform(0, LW), rng.uniform(15, 80), rng.randint(3, 6), rng.uniform(2, 6)] for _ in range(6)]
        self.far = self.ridge(110, 150, 10)
        self.near = self.ridge(150, 180, 16)
        self.turbines = list(range(rng.randint(8, 20), LW - 8, 34))
        rng.shuffle(self.turbines)
        self.pop_shown = 0.0
        self.banner_t = 7.0
        self.last_era = 0
        self.train_timer = 6.0
        self.init_weather()
        self.init_events()

    def init_weather(self):
        self.weather, self.weather_timer = "clear", 30.0
        self.cloud = self.precip = self.snow = self.flash = 0.0
        self.drops, self.bolt = [], []      # drop: [x, y, vx, vy, kind, seed, lands_at_y]

    def init_events(self):
        self.show = 0.0                     # seconds of fireworks left
        self.festival, self.festival_timer = 0.0, 300.0
        self.rockets, self.sparks = [], []  # rocket: [x, y, vy, colour]; spark: [x, y, vx, vy, age, life, colour]

    def __setstate__(self, state):      # cities saved before there was weather or events
        self.init_weather()
        self.init_events()
        self.__dict__.update(state)

    @property
    def season_f(self):
        """0 spring, 1 summer, 2 autumn, 3 winter; the fraction blends into the next."""
        return (self.t / SEASON_LEN + 0.3) % 4

    def ridge(self, lo, hi, step):
        pts, y = [], self.rng.uniform(lo, hi)
        for x in range(-step, LW + 2 * step, step):
            y = clamp(y + self.rng.uniform(-11, 11), lo, hi)
            pts.append((x, y))
        return pts

    @staticmethod
    def ridge_y(pts, x):
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if x0 <= x <= x1:
                return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
        return pts[-1][1]

    @property
    def era_f(self):
        return min(self.t / self.era_seconds, len(ERAS) - 0.001)

    def year(self):
        ef = self.era_f
        e = int(ef)
        return YEARS[e] + (YEARS[e + 1] - YEARS[e]) * (ef - e)

    def population(self):
        n = sum(POP.get(p.kind, 0) for p in self.plots if p.kind != "nature" and not p.building)
        return n * 10 + sum(1 for m in self.movers if m["kind"] != "deer")

    def puff(self, x, y, size=1.0, dark=False):
        if len(self.smoke) < 450:
            r = self.rng
            self.smoke.append([x + r.uniform(-1, 1), y, r.uniform(2, 6), r.uniform(-9, -5) * size,
                               0.0, r.uniform(2.5, 4.5) * size, dark])

    def spawn_side(self, length, speed):
        d = 1 if self.rng.random() < 0.5 else -1
        x = -length - 2 if d > 0 else LW + length + 2
        return d, x, speed * self.rng.uniform(0.8, 1.2)

    def update(self, dt):
        self.t += dt
        t, rng = self.t, self.rng
        era = int(self.era_f)
        if era != self.last_era:
            self.last_era = era
            self.banner_t = 7.0
            self.show = 12.0        # fireworks for the new era
        self.banner_t = max(0.0, self.banner_t - dt)

        # ---- the city grows
        rate = 6.0 / self.era_seconds
        for p in self.plots:
            if p.building:
                p.progress += dt / p.build_time
                if p.progress >= 1.0:
                    p.progress, p.building = 1.0, False
            elif (p.kind == "nature" and p.rank < DENSITY[era]) or (p.kind != "nature" and p.level < era):
                if rng.random() < dt * rate:
                    p.start(era, rng, clamp(self.era_seconds * rng.uniform(0.05, 0.1), 2.0, 14.0))
            if not p.building:
                if p.kind == "factory" and rng.random() < dt * 5:
                    self.puff(p.x + p.w - 4, GROUND - p.variant - 1, 1.3, dark=True)
                elif p.kind == "hut" and p.variant and rng.random() < dt * 1.2:
                    self.puff(min(p.x + p.w - 2, p.x + min(p.w - 4, 14) + 4), GROUND - 4, 0.6)

        # ---- traffic, walkers and wildlife
        if rng.random() < dt * WALK_RATE[era] * (4 if self.festival > 0 else 1):
            d, x, v = self.spawn_side(2, SPEED["walker"])
            shirts = [(130, 90, 60), (110, 80, 50)] if era <= 2 else \
                     [(200, 60, 60), (60, 90, 200), (240, 200, 60), (80, 160, 90), (230, 230, 230), (160, 80, 180)]
            self.movers.append(dict(kind="walker", x=x, base=WALK_Y, dir=d, v=v, color=rng.choice(shirts),
                                    skin=rng.choice([(240, 200, 160), (200, 150, 110), (150, 100, 70), (100, 70, 50)]),
                                    seed=rng.random() * 10, dog=era >= 5 and rng.random() < 0.15))
        if TRAFFIC[era] and rng.random() < dt * TRAFFIC_RATE[era]:
            kind = rng.choice(TRAFFIC[era])
            d, x, v = self.spawn_side(LENGTH[kind], SPEED[kind])
            col = rng.choice(EV_COLORS if era >= 7 else OLD_COLORS if era <= 5 else CAR_COLORS)
            if kind == "bus":
                col = rng.choice([(240, 190, 40), (200, 50, 50), (60, 120, 200)])
            if kind == "oldbus":
                col = rng.choice([(60, 110, 70), (150, 40, 40)])
            base = WALK_Y if kind in ("bicycle", "scooter") else LANE_R if d > 0 else LANE_L
            entry_clear = all(abs(m["x"] - x) > LENGTH[m["kind"]] + LENGTH[kind] + 6
                              for m in self.movers if m["base"] == base and m["dir"] == d)
            if entry_clear:
                self.movers.append(dict(kind=kind, x=x, base=base, dir=d, v=v, color=col,
                                        skin=(230, 190, 150), skin2=rng.choice(CAR_COLORS), seed=rng.random() * 10))
        if era <= 1 and rng.random() < dt * 0.04:
            d, x, v = self.spawn_side(5, SPEED["deer"])
            self.movers.append(dict(kind="deer", x=x, base=rng.choice((LANE_R, LANE_L)), dir=d, v=v,
                                    color=(0, 0, 0), seed=rng.random() * 10))

        for lane in (LANE_R, LANE_L):
            cars = sorted([m for m in self.movers if m["base"] == lane], key=lambda m: m["x"] * m["dir"], reverse=True)
            for i, m in enumerate(cars):
                v = m["v"]
                if i > 0:
                    ahead = cars[i - 1]
                    gap = (ahead["x"] - m["x"]) * m["dir"] - LENGTH[m["kind"]]
                    if gap < 4:
                        v = min(v, ahead.get("cur", ahead["v"]))
                        if gap < 1:
                            v = 0
                m["cur"] = v
        for m in self.movers:
            m["x"] += m.get("cur", m["v"]) * m["dir"] * dt
        self.movers = [m for m in self.movers if -40 < m["x"] < LW + 40]

        # ---- trains
        if era >= 4:
            self.train_timer -= dt
            if self.train_timer <= 0 and not self.trains:
                kind = ["steam", "diesel", "commuter", "maglev"][era - 4]
                d = 1 if rng.random() < 0.5 else -1
                cars = rng.randint(3, 5)
                total = cars * 17 + 16
                self.trains.append(dict(kind=kind, x=-total if d > 0 else LW + total, dir=d, cars=cars,
                                        v=[28, 40, 50, 90][era - 4]))
                self.train_timer = rng.uniform(14, 30)
        for tr in self.trains:
            tr["x"] += tr["v"] * tr["dir"] * dt
            if tr["kind"] == "steam" and rng.random() < dt * 9:
                L = tr["cars"] * 17
                fx = tr["x"] + (L + 12) * tr["dir"]
                self.puff(fx, RAIL_Y - 12, 1.2)
        self.trains = [tr for tr in self.trains if (tr["x"] < LW + 2 if tr["dir"] > 0 else tr["x"] > -2)]

        # ---- boats
        if era >= 1 and rng.random() < dt * 0.04 and len(self.boats) < 4:
            kind = {1: "canoe", 2: "canoe", 3: "sailboat", 4: "steamboat", 5: "motorboat",
                    6: "motorboat", 7: "eferry"}[era]
            if era in (5, 6) and rng.random() < 0.3:
                kind = "sailboat"
            d, x, v = self.spawn_side(20, {"canoe": 5, "sailboat": 8, "steamboat": 9,
                                           "motorboat": 18, "eferry": 10}[kind])
            self.boats.append(dict(kind=kind, x=x, dir=d, v=v, base=rng.randint(WATER_Y + 9, LH - 5)))
        for bt in self.boats:
            bt["x"] += bt["v"] * bt["dir"] * dt
            if bt["kind"] == "steamboat" and rng.random() < dt * 3:
                self.puff(bt["x"] + 10 * bt["dir"], bt["base"] - 10, 0.9)
        self.boats = [b for b in self.boats if -40 < b["x"] < LW + 40]

        # ---- things in the sky
        options = []
        if era <= 4:
            options += [("bird", 0.12)]
        if era == 5:
            options += [("biplane", 0.02)]
        if era == 6:
            options += [("plane", 0.04)]
        if era == 7:
            options += [("drone", 0.15), ("flycar", 0.05), ("plane", 0.02)]
        if era >= 4 and self.cloud < 0.4 and not any(f["kind"] == "balloon" for f in self.flyers):
            options += [("balloon", 0.012)]
        for kind, r in options:
            if rng.random() < dt * r:
                d, x, v = self.spawn_side(10, {"bird": 14, "biplane": 18, "plane": 30, "drone": 12, "flycar": 26,
                                               "balloon": 4}[kind])
                y = {"bird": rng.uniform(40, 110), "biplane": rng.uniform(40, 80), "plane": rng.uniform(15, 45),
                     "drone": rng.uniform(60, 150), "flycar": rng.uniform(55, 115),
                     "balloon": rng.uniform(55, 110)}[kind]
                n = rng.randint(3, 6) if kind == "bird" else 1
                for i in range(n):
                    self.flyers.append(dict(kind=kind, x=x - i * 5 * d, y=y + (i % 2) * 3 + i, dir=d, v=v,
                                            seed=rng.random() * 10, color=rng.choice(EV_COLORS)))
        for f in self.flyers:
            f["x"] += f["v"] * f["dir"] * dt
        self.flyers = [f for f in self.flyers if -30 < f["x"] < LW + 30]

        # ---- smoke and clouds
        for pf in self.smoke:
            pf[0] += pf[2] * dt
            pf[1] += pf[3] * dt
            pf[4] += dt
        self.smoke = [pf for pf in self.smoke if pf[4] < pf[5]]
        for c in self.clouds:
            c[0] += c[3] * dt
            if c[0] > LW + 40:
                c[0], c[1] = -40, self.rng.uniform(15, 80)

        self.update_weather(dt)
        self.update_events(dt, era)
        self.pop_shown += (self.population() - self.pop_shown) * clamp(dt * 1.5)

    def update_events(self, dt, era):
        rng = self.rng
        # ---- a town festival every so often, if the weather is fine
        self.festival_timer -= dt
        if self.festival > 0:
            self.festival = max(0.0, self.festival - dt)
        elif self.festival_timer <= 0:
            if era >= 2 and self.weather in ("clear", "cloudy"):
                self.festival = 50.0
            self.festival_timer = rng.uniform(400, 800)

        # ---- fireworks: a show for each new era, and festival nights from medieval times on
        launch = 0.0
        if self.show > 0:
            self.show -= dt
            launch = 2.5
        elif self.festival > 0 and era >= 3 and NIGHT > 0.5:
            launch = 0.6
        if rng.random() < dt * launch:
            self.rockets.append([rng.uniform(20, LW - 20), GROUND, rng.uniform(-115, -85), rng.choice(FIREWORK_COLORS)])
        for r in self.rockets:
            r[1] += r[2] * dt
            r[2] += 45 * dt
            if r[2] > -20:      # slowing down: burst
                for _ in range(rng.randint(36, 56)):
                    a, v = rng.uniform(0, math.tau), rng.uniform(20, 40)
                    if len(self.sparks) < 800:
                        self.sparks.append([r[0], r[1], math.cos(a) * v, math.sin(a) * v, 0.0,
                                            rng.uniform(1.2, 2.0), r[3]])
        self.rockets = [r for r in self.rockets if r[2] <= -20]
        for sp in self.sparks:
            sp[0] += sp[2] * dt
            sp[1] += sp[3] * dt
            sp[2] *= 1 - dt
            sp[3] = sp[3] * (1 - dt) + 14 * dt
            sp[4] += dt
        self.sparks = [sp for sp in self.sparks if sp[4] < sp[5]]

    def update_weather(self, dt):
        rng, sf = self.rng, self.season_f
        self.weather_timer -= dt
        if self.weather_timer <= 0:
            chances = WEATHER[int(sf)]
            self.weather = rng.choices(list(chances), weights=list(chances.values()))[0]
            self.weather_timer = rng.uniform(40, 120)
        k = clamp(dt * 0.15)
        self.cloud += (CLOUD[self.weather] - self.cloud) * k
        self.precip += (PRECIP[self.weather] - self.precip) * k
        snowing = self.weather == "snow"
        if snowing:
            self.snow = min(1.0, self.snow + dt * self.precip / 40)
        elif sf < 2.9:      # thaw once winter is over
            self.snow = max(0.0, self.snow - dt / 30)

        # ---- rain, snowflakes and falling leaves
        n = self.precip * (40 if snowing else 160) * LW / 480 * dt
        while n > 0 and self.precip > 0.05 and len(self.drops) < 700:
            if n < 1 and rng.random() > n:
                break
            n -= 1
            x, lands = rng.uniform(-20, LW + 20), rng.uniform(GROUND, LH)
            if snowing:
                self.drops.append([x, -2, rng.uniform(-4, 4), rng.uniform(12, 22), "snow", rng.random() * 6, lands])
            else:
                self.drops.append([x, -4, -25, rng.uniform(190, 240), "rain", 0, lands])
        leaf_fall = smooth(2.2, 2.5, sf) * (1 - smooth(2.9, 3.1, sf))
        if leaf_fall and rng.random() < dt * leaf_fall * 4:
            trees = [p for p in self.plots if p.kind == "nature"]
            if trees:
                p = rng.choice(trees)
                self.drops.append([p.x + rng.uniform(0, p.w), GROUND - rng.uniform(6, 14), rng.uniform(-6, 6),
                                   rng.uniform(5, 9), "leaf", rng.random() * 6, GROUND + rng.uniform(0, 3)])
        for d in self.drops:
            d[0] += d[2] * dt
            if d[4] != "rain":
                d[0] += math.sin(self.t * 2 + d[5]) * 6 * dt
            d[1] += d[3] * dt
        self.drops = [d for d in self.drops if d[1] < d[6]]

        # ---- lightning
        self.flash = max(0.0, self.flash - dt * 3)
        if self.weather == "storm" and self.cloud > 0.8 and rng.random() < dt * 0.1:
            self.flash = 1.0
            x, y = rng.uniform(20, LW - 20), rng.uniform(20, 50)
            end = rng.uniform(120, GROUND - 20)
            self.bolt = [(x, y)]
            while y < end:
                x += rng.uniform(-8, 8)
                y += rng.uniform(6, 14)
                self.bolt.append((x, y))

    # ------------------------------------------------------------- drawing
    def draw(self, s, phase=None):
        global NIGHT, SNOW, AUTUMN, BLOSSOM
        t = self.t
        ef = self.era_f
        era = int(ef)
        if phase is None:
            phase = (t / DAY_LEN + 0.28) % 1.0
        sun = math.sin(phase * math.tau)
        day = smooth(-0.12, 0.22, sun)
        NIGHT = max(1.0 - day, self.cloud * 0.35)     # storms dim the town and some lights come on
        SHADED.clear()
        sf = self.season_f
        SNOW = self.snow
        AUTUMN = smooth(1.8, 2.3, sf) * (1 - smooth(3.75, 3.98, sf))
        BLOSSOM = smooth(0.0, 0.25, sf) * (1 - smooth(0.7, 1.0, sf))
        dusk = clamp(1 - abs(sun) / 0.28)
        e0 = min(era + 1, len(SMOG) - 1)
        smog = SMOG[era] + (SMOG[e0] - SMOG[era]) * (ef - era)

        # sky
        top = mix((12, 14, 40), (70, 145, 228), day)
        bot = mix((35, 38, 80), (175, 215, 242), day)
        bot = mix(bot, (245, 150, 95), dusk * 0.65)
        top = mix(top, (110, 90, 150), dusk * 0.35)
        top = mix(top, (150, 140, 120), smog * day)
        bot = mix(bot, (185, 170, 145), smog * day)
        grey = mix((135, 140, 150), (25, 27, 36), 1.0 - day)
        top = mix(top, grey, self.cloud * 0.8)
        bot = mix(bot, mix(grey, (255, 255, 255), 0.15), self.cloud * 0.7)
        for y in range(GROUND):
            s.fill(mix(top, bot, y / GROUND), (0, y, LW, 1))

        if NIGHT > 0.25:
            k = (NIGHT - 0.25) / 0.75 * (1 - smog) * (1 - self.cloud)
            for sx, sy, b in self.stars:
                tw = 0.6 + 0.4 * math.sin(t * 2 + sx)
                s.set_at((sx, sy), mix(mix(top, bot, sy / GROUND), (255, 255, 235), k * b * tw))

        if phase < 0.56 and self.cloud < 0.65:
            sx, sy = LW * phase / 0.5, 150 - sun * 125
            pygame.draw.circle(s, mix((255, 245, 190), (255, 170, 90), dusk), (int(sx), int(sy)), 7)
        mp = (phase + 0.5) % 1.0
        if mp < 0.56 and self.cloud < 0.65:
            mx, my =LW * mp / 0.5, 150 - math.sin(mp * math.tau) * 125
            pygame.draw.circle(s, (230, 230, 215), (int(mx), int(my)), 5)
            s.set_at((int(mx) + 1, int(my) - 1), (200, 200, 190))
            s.set_at((int(mx) - 2, int(my) + 1), (205, 205, 195))

        cloud = mix(mix((255, 255, 255), (250, 190, 170), dusk * 0.6), (55, 58, 85), NIGHT)
        cloud = mix(cloud, (170, 160, 145), smog)
        cloud = mix(cloud, mix((110, 115, 125), (35, 37, 48), 1.0 - day), self.cloud * 0.8)
        puff = int(self.cloud * 3)
        for cx, cy, size, _ in self.clouds:
            for i in range(size):
                pygame.draw.circle(s, cloud, (int(cx + i * 5), int(cy + (i % 2) * 2)), 4 + (i % 3) + puff)

        far_col = sh(mix(bot, (80, 100, 130), 0.55), 0.6)
        far_col = mix(far_col, sh((215, 222, 230), 0.6), SNOW * 0.6)
        pygame.draw.polygon(s, far_col, self.far + [(LW + 40, GROUND), (-40, GROUND)])
        if self.flash > 0.5 and self.bolt:
            pygame.draw.lines(s, (255, 255, 225), False, self.bolt)
        if ef > 6.8:
            n = int(len(self.turbines) * clamp((ef - 6.8) * 2.5))
            for tx in self.turbines[:n]:
                ty = int(self.ridge_y(self.far, tx))
                pole = sh((235, 238, 240), 0.6)
                s.fill(pole, (tx, ty - 16, 1, 16))
                for i in range(3):
                    a = t * 2 + tx + i * math.tau / 3
                    pygame.draw.line(s, pole, (tx, ty - 16), (tx + math.cos(a) * 7, ty - 16 + math.sin(a) * 7))
                if NIGHT > 0.4 and int(t + tx) % 2:
                    s.set_at((tx, ty - 17), (255, 50, 50))
        near_col = mix((80, 135, 75), (110, 120, 105), min(1, era / 7) * 0.5)
        near_col = mix(near_col, (145, 125, 65), AUTUMN * 0.35)
        near_col = mix(sh(near_col, 0.75), sh((225, 230, 235), 0.75), SNOW * 0.85)
        pygame.draw.polygon(s, near_col, self.near + [(LW + 40, GROUND), (-40, GROUND)])

        # buildings
        for p in self.plots:
            if p.kind == "nature":
                draw_nature(s, p, era, t)
            elif p.building:
                draw_construction(s, p, t)
            else:
                draw_building(s, p, t)

        # sidewalk and road
        grass = mix(sh(mix((95, 150, 70), (150, 145, 70), AUTUMN * 0.4)), sh(SNOW_COLOR), SNOW)
        if era <= 3:
            s.fill(grass, (0, GROUND, LW, ROAD_TOP - GROUND))
        else:
            walk = sh((150, 140, 125) if era == 4 else (175, 175, 172))
            s.fill(mix(walk, sh(SNOW_COLOR), SNOW * 0.5), (0, GROUND, LW, ROAD_TOP - GROUND))
            s.fill(sh((120, 115, 110)), (0, ROAD_TOP - 1, LW, 1))
        road_h = ROAD_BOT - ROAD_TOP
        if era == 0:
            s.fill(grass, (0, ROAD_TOP, LW, road_h))
            R = random.Random(5)
            for _ in range(LW // 6):
                s.set_at((R.randrange(LW), ROAD_TOP + R.randrange(road_h)),
                         sh(R.choice([(240, 230, 90), (240, 240, 240), (200, 120, 200)])))
        elif era == 1:
            s.fill(grass, (0, ROAD_TOP, LW, road_h))
            s.fill(mix(sh((150, 125, 85)), sh(SNOW_COLOR), SNOW * 0.6), (0, ROAD_TOP + 6, LW, 5))
        elif era <= 3:
            s.fill(mix(sh((145, 115, 78)), sh(SNOW_COLOR), SNOW * 0.6), (0, ROAD_TOP, LW, road_h))
            s.fill(sh((125, 98, 65)), (0, ROAD_TOP + 5, LW, 1))
            s.fill(sh((125, 98, 65)), (0, ROAD_BOT - 5, LW, 1))
        elif era == 4:
            s.fill(sh((120, 112, 102)), (0, ROAD_TOP, LW, road_h))
            cobble = sh((100, 94, 88))
            for yy in range(ROAD_TOP + 1, ROAD_BOT, 3):
                for xx in range((yy % 2) * 2, LW, 4):
                    s.set_at((xx, yy), cobble)
        else:
            s.fill(sh((72, 72, 78) if era == 5 else (55, 56, 62)), (0, ROAD_TOP, LW, road_h))
            line = sh((230, 200, 80) if era == 5 else (235, 235, 235))
            for xx in range(0, LW, 10):
                s.fill(line, (xx, ROAD_TOP + 8, 5, 1))
            if era >= 7:
                s.fill(sh((70, 160, 95)), (0, ROAD_BOT - 2, LW, 2))

        # rail / grass strip / water
        s.fill(grass, (0, ROAD_BOT, LW, WATER_Y - ROAD_BOT))
        if era >= 4:
            for xx in range(0, LW, 4):
                s.fill(sh((110, 80, 55)), (xx, RAIL_Y, 2, 2))
            s.fill(sh((150, 150, 160) if era < 7 else (190, 200, 210)), (0, RAIL_Y, LW, 1))
        water = mix(sh(mix(bot, (30, 90, 130), 0.55), 0.5), (130, 115, 90), smog * 0.5)
        for y in range(WATER_Y, LH):
            s.fill(mix(water, mix(water, (5, 10, 25), 0.6), (y - WATER_Y) / (LH - WATER_Y)), (0, y, LW, 1))
        s.fill(sh((170, 160, 130) if era < 5 else (160, 160, 165)), (0, WATER_Y, LW, 2))
        for i in range(30):
            sx = int((i * 53 + t * 6 * (1 + i % 3)) % LW)
            sy = WATER_Y + 4 + (i * 7) % (LH - WATER_Y - 6)
            s.fill(mix(water, (255, 255, 255), 0.25 * (1 - NIGHT * 0.6)), (sx, sy, 3, 1))
        if NIGHT > 0.2:
            for p in self.plots:
                if p.kind != "nature" and p.level >= 4 and not p.building:
                    for k in range(5):
                        rx = p.x + p.w // 2 + int(math.sin(t * 3 + k * 1.7 + p.x) * 2)
                        ry = WATER_Y + 4 + k * 5 + int(math.sin(t * 2 + k) * 1)
                        s.fill(mix(water, (255, 210, 130), 0.45 * NIGHT), (rx - 1, ry, 3, 1))

        # street lamps
        if era >= 4:
            for lx in range(8, LW, 30):
                pole = sh((60, 60, 65))
                if NIGHT > 0.2:
                    pygame.draw.ellipse(s, mix(s.get_at((lx, ROAD_TOP + 2))[:3], (255, 230, 170), 0.4 * NIGHT),
                                        (lx - 6, ROAD_TOP - 1, 13, 5))
                s.fill(pole, (lx, ROAD_TOP - 11, 1, 11))
                s.fill(pole, (lx, ROAD_TOP - 11, 3, 1))
                s.fill(mix(sh((200, 200, 190)), (255, 230, 150), NIGHT), (lx + 2, ROAD_TOP - 10, 1, 1))

        # festival bunting over the street, with lanterns at night
        if self.festival > 0:
            pole = sh((120, 90, 60) if era < 4 else (90, 90, 95))
            string = sh((70, 60, 50))
            for px in range(20, LW, 40):
                s.fill(pole, (px, ROAD_TOP - 15, 1, 15))
                for i in range(1, 40):
                    xx = px + i
                    yy = ROAD_TOP - 14 + int(math.sin(math.pi * i / 40) * 4)
                    s.set_at((xx, yy), string)
                    if i % 4 == 2:
                        c = sh(BUNTING_COLORS[(xx // 4) % len(BUNTING_COLORS)])
                        s.fill(c, (xx - 1, yy + 1, 3, 1))
                        s.set_at((xx, yy + 2), c)
                    elif i % 8 == 0 and NIGHT > 0.3:
                        s.fill(mix(sh((200, 120, 60)), (255, 200, 110), NIGHT), (xx, yy + 1, 1, 2))

        for m in self.movers:
            draw_mover(s, m, t)
        for tr in self.trains:
            draw_train(s, tr, t)
        for bt in self.boats:
            draw_boat(s, bt, t)
        for pf in self.smoke:
            age = pf[4] / pf[5]
            base = (70, 65, 65) if pf[6] else (200, 200, 200)
            col = mix(sh(base, 0.6), mix(top, bot, clamp(pf[1] / GROUND)), age)
            pygame.draw.circle(s, col, (int(pf[0]), int(pf[1])), int(1 + age * 3))
        for f in self.flyers:
            draw_flyer(s, f, t)
        for x, y, _, _ in self.rockets:
            s.fill((255, 235, 180), (int(x), int(y), 1, 2))
        for x, y, vx, vy, age, life, col in self.sparks:
            fade = age / life
            if fade < 0.7 or int(t * 20 + x) % 2:       # twinkle as they die away
                sky = mix(top, bot, clamp(y / GROUND))
                s.set_at((int(x - vx * 0.06), int(y - vy * 0.06)), mix(col, sky, 0.5 + fade * 0.5))
                s.set_at((int(x), int(y)), mix(col, sky, fade * fade))

        # weather on top of everything
        rain = mix((175, 190, 210), (70, 80, 100), NIGHT * 0.7)
        flake = sh((245, 248, 252), 0.5)
        for x, y, _, _, kind, seed, _ in self.drops:
            if kind == "rain":
                s.fill(rain, (int(x), int(y), 1, 3))
            elif kind == "snow":
                s.set_at((int(x), int(y)), flake)
            else:
                s.set_at((int(x), int(y)), sh(AUTUMN_COLORS[int(seed) % 3]))
        if self.flash > 0:
            v = int(self.flash * 60)
            s.fill((v, v, v), special_flags=pygame.BLEND_RGB_ADD)


# ----------------------------------------------------------------- saving
def save_path(name="city.sav"):
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "TinyCity", name)


def city_saves():
    """Saved cities, newest first. Each screen setup (one screen, two screens...) keeps its own."""
    paths = glob.glob(os.path.join(os.path.dirname(save_path()), "city*.sav"))
    return sorted(paths, key=os.path.getmtime, reverse=True)


def save_world(world):
    """Write the city to disk so the next idle session carries on from here."""
    path = save_path(f"city-{LW}.sav")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path + ".tmp", "wb") as f:
            pickle.dump({"version": 1, "lw": LW, "world": world}, f)
        os.replace(path + ".tmp", path)
    except Exception:
        pass


def load_world(lw, era_seconds):
    """The newest saved city that fits this screen shape (within 15%), else None."""
    best = None
    for path in city_saves():
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
        except Exception:
            continue
        if data.get("version") == 1 and abs(data["lw"] - lw) <= lw * 0.15:
            if best is None or abs(data["lw"] - lw) < abs(best["lw"] - lw):
                best = data
    if best is None:
        return None
    world, saved_lw = best["world"], best["lw"]
    world.t = world.era_f * era_seconds     # keep the same era if --era-minutes changed
    world.era_seconds = era_seconds
    return world, saved_lw


def saved_city_summary():
    """One line about the most recent saved city, or None if there isn't one."""
    try:
        with open(city_saves()[0], "rb") as f:
            world = pickle.load(f)["world"]
    except Exception:
        return None
    return f"{ERAS[int(world.era_f)]}, year {fmt_year(world.year())}"


def load_settings():
    try:
        with open(save_path("settings.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_settings(settings):
    path = save_path("settings.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


# ----------------------------------------------------------------- settings window
ERA_CHOICES = [("15 seconds", 0.25), ("30 seconds", 0.5), ("1 minute", 1), ("1.5 minutes", 1.5),
               ("3 minutes", 3), ("5 minutes", 5), ("10 minutes", 10), ("30 minutes", 30),
               ("1 hour", 60), ("3 hours", 180)]


def fmt_minutes(m):
    if m < 1:
        return f"{round(m * 60)} seconds"
    if m < 90:
        return f"{m:g} minutes"
    return f"{m / 60:g} hours"


def configure():
    """The window behind the Settings button in Windows' screen saver dialog."""
    import tkinter as tk
    from tkinter import messagebox, ttk

    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)     # crisp text on high-DPI screens
    except Exception:
        pass

    settings = load_settings()
    current = settings.get("era_minutes", 1.5)
    labels = [label for label, _ in ERA_CHOICES]
    minutes = dict(ERA_CHOICES)
    closest = min(ERA_CHOICES, key=lambda c: abs(c[1] - current))[0]

    root = tk.Tk()
    root.title("Tiny City Settings")
    root.resizable(False, False)
    frame = ttk.Frame(root, padding=18)
    frame.grid(sticky="nsew")
    frame.columnconfigure(1, weight=1)

    ttk.Label(frame, text="Tiny City", font=("Segoe UI", 15, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
    ttk.Label(frame, text="Civilisation grows while you're away.").grid(row=1, column=0, columnspan=2,
                                                                         sticky="w", pady=(0, 14))

    ttk.Label(frame, text="Each era lasts").grid(row=2, column=0, sticky="w")
    era = tk.StringVar(value=closest)
    ttk.Combobox(frame, textvariable=era, values=labels, state="readonly", width=14).grid(
        row=2, column=1, sticky="e", padx=(16, 0))
    total = ttk.Label(frame, foreground="#666")
    total.grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 14))

    def show_total(*_):
        total.config(text=f"Green Future after about {fmt_minutes(minutes[era.get()] * (len(ERAS) - 1))} of idle time.")
    era.trace_add("write", show_total)
    show_total()

    city_box = ttk.LabelFrame(frame, text="Your city", padding=10)
    city_box.grid(row=4, column=0, columnspan=2, sticky="ew")
    city_box.columnconfigure(0, weight=1)
    city = ttk.Label(city_box)
    city.grid(row=0, column=0, sticky="w")

    def show_city():
        city.config(text=saved_city_summary() or "Wilderness. Nothing built yet.")

    def new_city():
        if messagebox.askyesno("Start a new city", "Forget your city and start again from wilderness?", parent=root):
            for path in city_saves():
                try:
                    os.remove(path)
                except OSError:
                    pass
            show_city()
    ttk.Button(city_box, text="Start a new city", command=new_city).grid(row=0, column=1, padx=(16, 0))
    show_city()

    def ok(*_):
        settings["era_minutes"] = minutes[era.get()]
        try:
            save_settings(settings)
        except OSError as e:
            messagebox.showerror("Tiny City", f"Couldn't save settings:\n{e}", parent=root)
            return
        root.destroy()

    buttons = ttk.Frame(frame)
    buttons.grid(row=5, column=0, columnspan=2, sticky="e", pady=(16, 0))
    ttk.Button(buttons, text="OK", command=ok, default="active").grid(row=0, column=0)
    ttk.Button(buttons, text="Cancel", command=root.destroy).grid(row=0, column=1, padx=(8, 0))
    root.bind("<Return>", ok)
    root.bind("<Escape>", lambda e: root.destroy())

    root.update_idletasks()
    x = (root.winfo_screenwidth() - root.winfo_width()) // 2
    y = (root.winfo_screenheight() - root.winfo_height()) // 3
    root.geometry(f"+{x}+{y}")
    root.mainloop()


# ----------------------------------------------------------------- run modes
def monitor_rects():
    """Each monitor's (x, y, w, h) on the desktop in pixels, left to right. None if unknown."""
    if platform.system() != "Windows":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        rects = []

        def found(hmon, hdc, r, data):
            r = r.contents
            rects.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
            return 1
        proc = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HMONITOR, wintypes.HDC,
                                  ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)(found)
        ctypes.windll.user32.EnumDisplayMonitors(None, None, proc, 0)
        return sorted(rects) or None
    except Exception:
        return None


def on_battery():
    """True when a laptop is running on battery (Windows only)."""
    if platform.system() != "Windows":
        return False
    try:
        import ctypes

        class SYSTEM_POWER_STATUS(ctypes.Structure):
            _fields_ = [("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte),
                        ("BatteryLifePercent", ctypes.c_ubyte), ("SystemStatusFlag", ctypes.c_ubyte),
                        ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]
        status = SYSTEM_POWER_STATUS()
        if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
            return False
        return status.ACLineStatus == 0
    except Exception:
        return False


def split_views(rects, lw=None):
    """One wide city across all screens: each screen shows the next slice, left to right.
    Returns the city width and a list of (slice of the canvas, place on the window)."""
    widths = [LH * w / h for _, _, w, h in rects]
    if lw is None:
        lw = max(320, int(round(sum(widths))))
    scale = lw / sum(widths)
    views, x = [], 0
    for i, (rx, ry, w, h) in enumerate(rects):
        sw = lw - x if i == len(rects) - 1 else int(round(widths[i] * scale))
        views.append((pygame.Rect(x, 0, sw, LH), pygame.Rect(rx, ry, w, h)))
        x += sw
    return lw, views


def run(args):
    global LW
    if platform.system() == "Windows":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)     # real pixels, so the art stays sharp
        except Exception:
            pass
    rects = None if args.window else monitor_rects()
    if rects and len(rects) > 1:     # one borderless window over every screen
        vx, vy = min(r[0] for r in rects), min(r[1] for r in rects)
        vw = max(r[0] + r[2] for r in rects) - vx
        vh = max(r[1] + r[3] for r in rects) - vy
        rects = [(x - vx, y - vy, w, h) for x, y, w, h in rects]
    pygame.init()
    # The graphics card scales the small pixel canvas up to the screen, which keeps the CPU (and battery) quiet.
    if args.window:
        win = Window("Tiny City", size=(1280, 720))
    elif rects and len(rects) > 1:
        win = Window("Tiny City", size=(vw, vh), position=(vx, vy), borderless=True)
    else:
        win = Window("Tiny City", fullscreen_desktop=True)
    if not args.window:
        pygame.mouse.set_visible(False)
    renderer = Renderer(win)
    if not rects or len(rects) == 1:
        rects = [tuple(renderer.get_viewport())]
    LW, views = split_views(rects)
    saved = None if args.new else load_world(LW, args.era_minutes * 60)
    if saved:
        world, LW = saved
        LW, views = split_views(rects, LW)
    else:
        world = World(args.era_minutes * 60)
    canvas = pygame.Surface((LW, LH))
    texture = Texture(renderer, (LW, LH), streaming=True)
    texture.blend_mode = 0      # the canvas has no alpha; copy it as is
    clock = pygame.time.Clock()
    started = time.time()
    last_save = started
    fps = 20 if on_battery() else 30
    pygame.event.clear()
    start_mouse = pygame.mouse.get_pos()

    running = True
    while running:
        dt = min(clock.tick(fps) / 1000.0, 0.1)
        if time.time() - last_save > 30:
            save_world(world)
            last_save = time.time()
            fps = 20 if on_battery() else 30
        settled = time.time() - started > 1.5
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if not args.window or e.key == pygame.K_ESCAPE:
                    running = False
                elif e.key == pygame.K_RIGHT:
                    world.t = (int(world.era_f) + 1) * world.era_seconds
            elif not args.window and settled:
                if e.type == pygame.MOUSEBUTTONDOWN:
                    running = False
                elif e.type == pygame.MOUSEMOTION:
                    if abs(e.pos[0] - start_mouse[0]) + abs(e.pos[1] - start_mouse[1]) > 12:
                        running = False
            elif e.type == pygame.MOUSEMOTION:
                start_mouse = e.pos
        world.update(dt)
        world.draw(canvas)
        texture.update(canvas)
        renderer.draw_color = (0, 0, 0, 255)
        renderer.clear()
        for src, dst in views:
            texture.draw(srcrect=src, dstrect=dst)
        renderer.present()
    save_world(world)
    win.destroy()
    pygame.quit()


def idle_seconds():
    """Seconds since the last keyboard/mouse input, or None if unknown."""
    system = platform.system()
    try:
        if system == "Windows":
            import ctypes

            class LASTINPUTINFO(ctypes.Structure):
                _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
            info = LASTINPUTINFO()
            info.cbSize = ctypes.sizeof(info)
            ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info))
            return ((ctypes.windll.kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF) / 1000.0
        if system == "Darwin":
            out = subprocess.run(["ioreg", "-c", "IOHIDSystem"], capture_output=True, text=True).stdout
            for line in out.splitlines():
                if "HIDIdleTime" in line:
                    return int(line.split("=")[-1].strip()) / 1e9
            return None
        out = subprocess.run(["xprintidle"], capture_output=True, text=True).stdout.strip()
        return int(out) / 1000.0
    except Exception:
        return None


def watch(args):
    if idle_seconds() is None:
        sys.exit("Couldn't read the idle time on this system. On Linux, install xprintidle (sudo apt install xprintidle).")
    limit = args.idle_minutes * 60
    print(f"Tiny City is watching. It will appear after {args.idle_minutes:g} idle minutes. Ctrl+C to stop.")
    if getattr(sys, "frozen", False):
        cmd = [sys.executable]
    else:
        cmd = [sys.executable, os.path.abspath(__file__)]
    try:
        while True:
            time.sleep(2)
            idle = idle_seconds() or 0
            if idle >= limit:
                subprocess.run(cmd + ["--era-minutes", str(args.era_minutes), "--away-offset", str(int(idle))])
                time.sleep(3)
    except KeyboardInterrupt:
        print("\nBye!")


def main():
    argv = sys.argv[1:]
    # Windows screensaver (.scr) arguments
    if argv and argv[0][:2].lower() == "/p":
        return
    if argv and argv[0][:2].lower() == "/c":
        argv = ["--settings"]
    if argv and argv[0][:2].lower() == "/s":
        argv = []
    ap = argparse.ArgumentParser(description="Tiny City: an idle screen where civilisation evolves while you're away.")
    ap.add_argument("--watch", action="store_true", help="wait in the background and start when the computer is idle")
    ap.add_argument("--idle-minutes", type=float, default=5, help="idle minutes before starting (with --watch)")
    ap.add_argument("--era-minutes", type=float, default=load_settings().get("era_minutes", 1.5),
                    help="how long each era lasts (default: from the settings window, else 1.5)")
    ap.add_argument("--settings", action="store_true", help="open the settings window")
    ap.add_argument("--fast", action="store_true", help="demo speed: 15 seconds per era")
    ap.add_argument("--window", action="store_true", help="run in a window for testing")
    ap.add_argument("--new", action="store_true", help="forget the saved city and start from wilderness")
    ap.add_argument("--away-offset", type=float, default=0, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.fast:
        args.era_minutes = 0.25
    if args.settings:
        configure()
    elif args.watch:
        watch(args)
    else:
        run(args)


if __name__ == "__main__":
    main()
