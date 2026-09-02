#!/usr/bin/env python3
"""Render the deployed Strands WebRTC + KVS + Nova Sonic architecture diagram."""

from __future__ import annotations

import math
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH = 2600
HEIGHT = 1600
SCALE = 1

COLORS = {
    "background": "#f7f8fa",
    "ink": "#172333",
    "muted": "#536273",
    "border": "#9aabba",
    "aws_fill": "#e9f4fb",
    "group_fill": "#f4f8ef",
    "vpc_fill": "#edf7ee",
    "private_fill": "#e9f3ff",
    "public_fill": "#fff5df",
    "runtime_fill": "#fffaf0",
    "browser_fill": "#eef7ff",
    "external_fill": "#f5f1f8",
    "blue": "#147eb3",
    "green": "#218739",
    "purple": "#6f42c1",
    "orange": "#e97700",
    "red": "#c9252d",
    "teal": "#008f95",
    "gray": "#697887",
    "white": "#ffffff",
    "shadow": "#d9e0e6",
}

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "deployed-architecture.png"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


F_TITLE = font(46, True)
F_SUBTITLE = font(24)
F_ZONE = font(24, True)
F_GROUP = font(21, True)
F_CARD = font(21, True)
F_BODY = font(18)
F_SMALL = font(15)
F_TINY = font(13)


def rounded(draw: ImageDraw.ImageDraw, box, fill, outline=COLORS["border"], radius=22, width=2, shadow=False):
    x1, y1, x2, y2 = box
    if shadow:
        draw.rounded_rectangle((x1 + 7, y1 + 9, x2 + 7, y2 + 9), radius=radius, fill=COLORS["shadow"])
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def text_center(draw: ImageDraw.ImageDraw, box, value: str, fnt, fill=COLORS["ink"], spacing=4):
    x1, y1, x2, y2 = box
    lines = value.split("\n")
    heights = []
    widths = []
    for line in lines:
        bb = draw.textbbox((0, 0), line, font=fnt)
        widths.append(bb[2] - bb[0])
        heights.append(bb[3] - bb[1])
    total = sum(heights) + spacing * max(0, len(lines) - 1)
    y = y1 + (y2 - y1 - total) / 2
    for line, w, h in zip(lines, widths, heights):
        draw.text((x1 + (x2 - x1 - w) / 2, y), line, font=fnt, fill=fill)
        y += h + spacing


def label(draw: ImageDraw.ImageDraw, xy, value: str, fnt=F_BODY, fill=COLORS["ink"], anchor="la"):
    draw.text(xy, value, font=fnt, fill=fill, anchor=anchor)


def card(draw: ImageDraw.ImageDraw, box, title: str, subtitle: str, color: str, badge: str | None = None):
    rounded(draw, box, COLORS["white"], outline=color, radius=18, width=3, shadow=True)
    x1, y1, x2, y2 = box
    icon_size = min(62, y2 - y1 - 28)
    ix1 = x1 + 16
    iy1 = y1 + (y2 - y1 - icon_size) / 2
    draw.rounded_rectangle((ix1, iy1, ix1 + icon_size, iy1 + icon_size), radius=14, fill=color)
    if badge:
        text_center(draw, (ix1, iy1, ix1 + icon_size, iy1 + icon_size), badge, font(18, True), COLORS["white"])
    tx = ix1 + icon_size + 16
    draw.text((tx, y1 + 18), title, font=F_CARD, fill=COLORS["ink"])
    wrapped = "\n".join(textwrap.wrap(subtitle, width=max(16, int((x2 - tx - 15) / 10))))
    draw.multiline_text((tx, y1 + 51), wrapped, font=F_SMALL, fill=COLORS["muted"], spacing=3)


def arrowhead(draw: ImageDraw.ImageDraw, tip, previous, color, size=14):
    tx, ty = tip
    px, py = previous
    angle = math.atan2(ty - py, tx - px)
    left = (tx - size * math.cos(angle - math.pi / 6), ty - size * math.sin(angle - math.pi / 6))
    right = (tx - size * math.cos(angle + math.pi / 6), ty - size * math.sin(angle + math.pi / 6))
    draw.polygon([tip, left, right], fill=color)


def flow(draw: ImageDraw.ImageDraw, points, color, width=5, dashed=False, both=False, arrow_size=15):
    if dashed:
        for start, end in zip(points[:-1], points[1:]):
            x1, y1 = start
            x2, y2 = end
            length = math.hypot(x2 - x1, y2 - y1)
            if length == 0:
                continue
            ux = (x2 - x1) / length
            uy = (y2 - y1) / length
            pos = 0
            while pos < length:
                seg_end = min(pos + 13, length)
                draw.line((x1 + ux * pos, y1 + uy * pos, x1 + ux * seg_end, y1 + uy * seg_end), fill=color, width=width)
                pos += 23
    else:
        draw.line(points, fill=color, width=width, joint="curve")
    arrowhead(draw, points[-1], points[-2], color, arrow_size)
    if both:
        arrowhead(draw, points[0], points[1], color, arrow_size)


def flow_label(draw: ImageDraw.ImageDraw, xy, value: str, color, width=None):
    lines = textwrap.wrap(value, width=width or 32)
    text = "\n".join(lines)
    bb = draw.multiline_textbbox((0, 0), text, font=F_SMALL, spacing=2)
    w = bb[2] - bb[0] + 20
    h = bb[3] - bb[1] + 12
    x, y = xy
    draw.rounded_rectangle(
        (x - w / 2, y - h / 2, x + w / 2, y + h / 2), radius=10, fill=COLORS["white"], outline=color, width=2
    )
    draw.multiline_text((x, y), text, font=F_SMALL, fill=color, anchor="mm", align="center", spacing=2)


def service_circle(draw: ImageDraw.ImageDraw, center, radius, color, badge, title, subtitle=""):
    cx, cy = center
    draw.ellipse((cx - radius + 6, cy - radius + 8, cx + radius + 6, cy + radius + 8), fill=COLORS["shadow"])
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=color, outline=COLORS["white"], width=5)
    text_center(draw, (cx - radius, cy - radius, cx + radius, cy + radius), badge, font(23, True), COLORS["white"])
    label(draw, (cx, cy + radius + 16), title, F_CARD, COLORS["ink"], "ma")
    if subtitle:
        label(draw, (cx, cy + radius + 43), subtitle, F_TINY, COLORS["muted"], "ma")


def render():
    image = Image.new("RGB", (WIDTH, HEIGHT), COLORS["background"])
    draw = ImageDraw.Draw(image)

    label(
        draw,
        (WIDTH / 2, 55),
        "Strands WebRTC + KVS + Nova Sonic on Amazon Bedrock AgentCore",
        F_TITLE,
        COLORS["ink"],
        "ma",
    )
    label(
        draw,
        (WIDTH / 2, 112),
        "Deployed architecture: signed HTTP signaling, TURN-relayed WebRTC media, and bidirectional model streaming",
        F_SUBTITLE,
        COLORS["muted"],
        "ma",
    )

    # Primary boundaries.
    rounded(draw, (45, 205, 430, 1390), COLORS["browser_fill"], outline="#84a9c4", radius=28, width=3)
    label(draw, (70, 230), "USER DEVICE", F_ZONE, COLORS["blue"])

    rounded(draw, (470, 175, 2370, 1495), COLORS["aws_fill"], outline="#7aa8c2", radius=32, width=3)
    label(draw, (500, 198), "AWS CLOUD  |  us-east-1", F_ZONE, COLORS["blue"])

    rounded(draw, (850, 560, 1785, 1425), COLORS["vpc_fill"], outline="#69a56f", radius=28, width=3)
    label(draw, (880, 585), "VPC 10.0.0.0/16", F_ZONE, COLORS["green"])

    rounded(draw, (880, 630, 1745, 1245), COLORS["private_fill"], outline="#7ea7cf", radius=24, width=2)
    label(draw, (905, 652), "PRIVATE SUBNETS  |  use1-az1 + use1-az2", F_GROUP, COLORS["blue"])

    rounded(draw, (880, 1270, 1745, 1388), COLORS["public_fill"], outline="#d6a343", radius=20, width=2)
    label(draw, (905, 1290), "PUBLIC SUBNET + NAT GATEWAY", F_GROUP, COLORS["orange"])

    # Browser internals.
    card(draw, (75, 285, 400, 410), "React + Vite", "CloudFront-hosted voice UI", COLORS["blue"], "UI")
    card(
        draw,
        (75, 455, 400, 610),
        "Cognito session",
        "User Pool JWT exchanged for temporary AWS credentials",
        COLORS["red"],
        "ID",
    )
    card(
        draw,
        (75, 660, 400, 855),
        "WebRTC peer",
        "getUserMedia microphone, SDP/ICE, RTP/Opus send + receive",
        COLORS["green"],
        "RTC",
    )
    card(
        draw,
        (75, 905, 400, 1060),
        "AgentCore SDK",
        "SigV4 POST /invocations with runtimeSessionId affinity",
        COLORS["blue"],
        "SIG",
    )
    rounded(draw, (75, 1110, 400, 1340), COLORS["white"], outline=COLORS["border"], radius=18, width=2)
    label(draw, (95, 1130), "Browser responsibilities", F_GROUP, COLORS["ink"])
    bullets = [
        "Capture 16 kHz microphone audio",
        "Play 24 kHz assistant audio",
        "Retry failed signaling sessions",
        "Surface connection errors",
    ]
    y = 1170
    for item in bullets:
        draw.ellipse((96, y + 7, 104, y + 15), fill=COLORS["blue"])
        draw.text((116, y), item, font=F_SMALL, fill=COLORS["muted"])
        y += 39

    # Top AWS groups.
    rounded(draw, (510, 245, 1005, 505), COLORS["group_fill"], radius=22, width=2)
    label(draw, (535, 265), "STATIC WEB DELIVERY", F_GROUP, COLORS["green"])
    card(draw, (535, 315, 750, 455), "CloudFront", "HTTPS distribution + SPA rewrite", COLORS["purple"], "CF")
    card(draw, (775, 315, 980, 455), "Amazon S3", "Private frontend origin through OAC", COLORS["green"], "S3")

    rounded(draw, (1030, 245, 1575, 505), COLORS["group_fill"], radius=22, width=2)
    label(draw, (1055, 265), "AUTHENTICATION", F_GROUP, COLORS["red"])
    card(draw, (1055, 315, 1285, 455), "User Pool", "SRP sign-in and ID token", COLORS["red"], "UP")
    card(draw, (1310, 315, 1550, 455), "Identity Pool", "Authenticated IAM role credentials", COLORS["red"], "IP")

    rounded(draw, (1600, 245, 2325, 505), COLORS["group_fill"], radius=22, width=2)
    label(draw, (1625, 265), "DEPLOYMENT + OBSERVABILITY", F_GROUP, COLORS["orange"])
    card(draw, (1625, 315, 1940, 455), "Amazon ECR", "ARM64 Docker V2 image", COLORS["orange"], "ECR")
    card(draw, (1965, 315, 2295, 455), "CloudWatch", "Runtime logs, metrics, and traces", COLORS["blue"], "LOG")

    # KVS managed service outside VPC.
    rounded(draw, (520, 640, 805, 900), COLORS["white"], outline=COLORS["teal"], radius=22, width=3, shadow=True)
    service_circle(
        draw, (662, 725), 54, COLORS["teal"], "TURN", "Kinesis Video Streams", "signaling channel + ICE servers"
    )
    label(draw, (662, 845), "Managed service outside the VPC", F_TINY, COLORS["muted"], "ma")

    # AgentCore runtime.
    rounded(
        draw, (925, 700, 1705, 1215), COLORS["runtime_fill"], outline=COLORS["orange"], radius=26, width=4, shadow=True
    )
    label(draw, (950, 723), "AMAZON BEDROCK AGENTCORE RUNTIME", F_GROUP, COLORS["orange"])
    label(draw, (1680, 725), "HTTP + VPC mode  |  MMDSv2", F_TINY, COLORS["muted"], "ra")

    card(draw, (955, 780, 1125, 925), "FastAPI", "POST /invocations\nSDP + ICE actions", COLORS["blue"], "API")
    card(draw, (1145, 780, 1315, 925), "aiortc", "PeerConnection\nICE + SRTP/RTP", COLORS["green"], "RTC")
    card(draw, (1335, 780, 1505, 925), "Audio bridge", "16 kHz input\n24 kHz output", COLORS["teal"], "PCM")
    card(draw, (1525, 780, 1680, 925), "BidiAgent", "Streaming + tools\n+ interruption", COLORS["purple"], "BA")

    label(draw, (950, 965), "KITCHEN TOOLS", F_GROUP, COLORS["purple"])
    tool_boxes = [
        ((955, 1005, 1120, 1125), "search_recipes", "Bedrock KB"),
        ((1135, 1005, 1300, 1125), "set_timer", "local async"),
        ((1315, 1005, 1480, 1125), "nutrition_lookup", "USDA API"),
        ((1495, 1005, 1660, 1125), "convert_units", "local logic"),
    ]
    for box, title, subtitle in tool_boxes:
        rounded(draw, box, COLORS["external_fill"], outline="#9c84b5", radius=14, width=2)
        text_center(draw, (box[0], box[1] + 8, box[2], box[1] + 62), title, F_SMALL, COLORS["ink"])
        text_center(draw, (box[0], box[1] + 62, box[2], box[3] - 5), subtitle, F_TINY, COLORS["muted"])

    rounded(draw, (955, 1150, 1660, 1195), "#fff2d9", outline="#d8a044", radius=12, width=2)
    text_center(
        draw,
        (955, 1150, 1660, 1195),
        "Execution role: Nova, Knowledge Base, KVS, ECR, logs, and VPC networking",
        F_SMALL,
        COLORS["muted"],
    )

    # NAT content.
    card(draw, (930, 1307, 1190, 1372), "NAT Gateway", "Outbound AWS + internet access", COLORS["orange"], "NAT")
    label(draw, (1230, 1338), "Private route tables: 0.0.0.0/0 → NAT", F_SMALL, COLORS["muted"], "lm")

    # AWS managed services to the right of VPC.
    rounded(draw, (1825, 565, 2325, 1395), COLORS["group_fill"], radius=24, width=2)
    label(draw, (1850, 588), "AWS MANAGED SERVICES", F_GROUP, COLORS["green"])
    card(
        draw,
        (1855, 640, 2295, 795),
        "Amazon Nova Sonic 2",
        "Bidirectional speech-to-speech model stream",
        COLORS["teal"],
        "NOVA",
    )
    card(
        draw,
        (1855, 845, 2295, 1000),
        "Bedrock Knowledge Base",
        "Recipe retrieval: vector or managed search",
        COLORS["teal"],
        "KB",
    )
    card(
        draw,
        (1855, 1050, 2295, 1205),
        "KVS control APIs",
        "TURN credentials and signaling-channel lifecycle",
        COLORS["teal"],
        "KVS",
    )
    card(
        draw,
        (1855, 1255, 2295, 1365),
        "AWS APIs",
        "ECR layers, CloudWatch, and service endpoints",
        COLORS["blue"],
        "AWS",
    )

    # External API.
    rounded(draw, (2400, 920, 2570, 1195), COLORS["external_fill"], outline="#9c84b5", radius=22, width=2)
    text_center(draw, (2410, 945, 2560, 1025), "EXTERNAL", F_GROUP, COLORS["purple"])
    service_circle(draw, (2485, 1080), 45, COLORS["purple"], "API", "USDA FoodData", "nutrition lookup")

    # Internal runtime pipeline.
    flow(draw, [(1125, 850), (1145, 850)], COLORS["green"], width=5, both=True)
    flow(draw, [(1315, 850), (1335, 850)], COLORS["teal"], width=5, both=True)
    flow(draw, [(1505, 850), (1525, 850)], COLORS["purple"], width=5, both=True)

    # Static hosting and authentication.
    flow(draw, [(400, 335), (535, 365)], COLORS["purple"], width=4)
    flow_label(draw, (466, 315), "HTTPS", COLORS["purple"])
    flow(draw, [(750, 385), (775, 385)], COLORS["green"], width=4)
    flow_label(draw, (763, 355), "OAC", COLORS["green"])

    flow(draw, [(400, 500), (1055, 385)], COLORS["red"], width=4)
    flow_label(draw, (735, 475), "SRP sign-in + JWT", COLORS["red"])
    flow(draw, [(1285, 385), (1310, 385)], COLORS["red"], width=4)
    flow(draw, [(1430, 455), (1430, 525), (300, 525), (300, 610)], COLORS["red"], width=3)
    flow_label(draw, (860, 525), "temporary AWS credentials", COLORS["red"])

    # Signed HTTP signaling.
    flow(draw, [(400, 980), (700, 980), (700, 740), (955, 845)], COLORS["blue"], width=6)
    flow_label(
        draw, (685, 930), "SigV4 HTTPS POST /invocations\nSDP offer/answer + ICE candidates", COLORS["blue"], width=34
    )

    # TURN credentials (control) and WebRTC media.
    flow(
        draw,
        [(955, 875), (840, 875), (840, 810), (805, 810)],
        COLORS["teal"],
        width=3,
        dashed=True,
        both=True,
        arrow_size=12,
    )
    flow_label(draw, (860, 845), "TURN config", COLORS["teal"])

    flow(draw, [(400, 760), (520, 760)], COLORS["green"], width=10, both=True, arrow_size=20)
    flow(
        draw,
        [(805, 760), (830, 760), (830, 680), (1230, 680), (1230, 780)],
        COLORS["green"],
        width=10,
        both=True,
        arrow_size=20,
    )
    # The media route is intentionally unlabeled here; the legend identifies the
    # thick bidirectional green path without obscuring the subnet/runtime headers.

    # Model and tool traffic.
    flow(draw, [(1680, 850), (1855, 720)], COLORS["purple"], width=7, both=True, arrow_size=18)
    flow_label(draw, (1775, 760), "bidirectional model stream", COLORS["purple"], width=26)
    flow(draw, [(1037, 1005), (1037, 945), (1780, 945), (1780, 925), (1855, 925)], COLORS["teal"], width=4)
    flow_label(draw, (1730, 915), "Retrieve", COLORS["teal"])
    flow(
        draw,
        [(1397, 1125), (1397, 1230), (2370, 1230), (2370, 1080), (2400, 1080)],
        COLORS["purple"],
        width=4,
    )
    flow_label(draw, (2100, 1230), "HTTPS nutrition query", COLORS["purple"])

    # Deployment, logs, and egress.
    flow(draw, [(1775, 455), (1775, 620), (1450, 620), (1450, 700)], COLORS["orange"], width=4, dashed=True)
    flow_label(draw, (1630, 620), "image pull", COLORS["orange"])
    flow(draw, [(1650, 700), (2130, 455)], COLORS["gray"], width=3, dashed=True)
    flow_label(draw, (1940, 545), "logs + traces", COLORS["gray"])
    flow(draw, [(1100, 1215), (1050, 1307)], COLORS["orange"], width=4)
    flow(draw, [(1190, 1340), (1800, 1340), (1855, 1310)], COLORS["orange"], width=4, dashed=True)
    flow_label(draw, (1510, 1340), "outbound egress", COLORS["orange"])

    # Legend.
    rounded(draw, (500, 1520, 2330, 1580), COLORS["white"], outline=COLORS["border"], radius=16, width=2)
    label(draw, (525, 1538), "FLOW LEGEND", F_GROUP, COLORS["ink"])
    legend = [
        (COLORS["blue"], "signed HTTP signaling", False, False),
        (COLORS["green"], "WebRTC media", False, True),
        (COLORS["purple"], "model + tool traffic", False, True),
        (COLORS["teal"], "KVS / AWS control", True, False),
        (COLORS["orange"], "deployment + egress", True, False),
        (COLORS["gray"], "observability", True, False),
    ]
    x = 710
    for color, name, dashed, both in legend:
        flow(draw, [(x, 1550), (x + 90, 1550)], color, width=4, dashed=dashed, both=both, arrow_size=11)
        label(draw, (x + 105, 1550), name, F_SMALL, COLORS["muted"], "lm")
        x += 285

    image.save(OUTPUT, format="PNG", optimize=True)
    print(f"Rendered {OUTPUT} ({WIDTH}x{HEIGHT})")


if __name__ == "__main__":
    render()
