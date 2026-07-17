from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


BG = "#07101f"
PANEL = "#111d31"
BORDER = "#31425f"
TEXT = "#f4f7fb"
MUTED = "#a7b2c7"
TEAL = "#5eead4"
BLUE = "#60a5fa"
PURPLE = "#a78bfa"
AMBER = "#fbbf24"


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], title: str, lines: list[str], accent: str) -> None:
    draw.rounded_rectangle(box, radius=24, fill=PANEL, outline=BORDER, width=2)
    x1, y1, x2, _ = box
    draw.rounded_rectangle((x1 + 2, y1 + 2, x2 - 2, y1 + 10), radius=8, fill=accent)
    draw.text((x1 + 24, y1 + 28), title, fill=TEXT, font=font(24, True))
    y = y1 + 70
    for line in lines:
        draw.text((x1 + 24, y), line, fill=MUTED, font=font(17))
        y += 30


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color: str = BLUE) -> None:
    draw.line((start, end), fill=color, width=4)
    x, y = end
    draw.polygon([(x, y), (x - 13, y - 8), (x - 13, y + 8)], fill=color)


def architecture() -> None:
    image = Image.new("RGB", (1600, 980), BG)
    draw = ImageDraw.Draw(image)
    draw.text((70, 46), "OpenAgent Studio - Agent Architecture", fill=TEXT, font=font(38, True))
    draw.text((70, 96), "GLM 5.1 / OpenAI-compatible providers · FastAPI · React · SQLite", fill=MUTED, font=font(20))

    rounded(draw, (70, 180, 400, 430), "React Workbench", ["Conversation + Chat", "Model / Agent selector", "Compare cards", "Execution timeline"], TEAL)
    rounded(draw, (500, 180, 850, 430), "FastAPI Runtime", ["POST AgentRun", "GET SSE stream", "Event normalizer", "Persistence services"], BLUE)
    rounded(draw, (950, 150, 1510, 460), "Agents SDK", ["TriageRouteAgent -> RouteDecision", "TriageAgent (manager)", "Tech / Ecommerce / Image tools", "Compare fan-out + JudgeAgent"], PURPLE)
    rounded(draw, (500, 590, 850, 850), "SQLite Audit", ["conversations / messages", "agent_runs / run_events", "tool_calls", "model_compares / results"], AMBER)
    rounded(draw, (950, 590, 1510, 850), "Model Providers", ["GLM 5.1", "Qwen / DeepSeek", "OpenAIChatCompletionsModel", "Keys only from environment"], TEAL)

    arrow(draw, (400, 305), (500, 305))
    arrow(draw, (850, 305), (950, 305))
    arrow(draw, (675, 430), (675, 590), AMBER)
    arrow(draw, (1230, 460), (1230, 590), TEAL)
    image.save(DOCS / "agent-architecture.png", quality=95)


def sequence() -> None:
    image = Image.new("RGB", (1600, 980), BG)
    draw = ImageDraw.Draw(image)
    draw.text((70, 46), "Auto / Compare Runtime Sequence", fill=TEXT, font=font(38, True))
    actors = [(130, "React"), (450, "FastAPI"), (780, "Triage / Experts"), (1110, "Models / Judge"), (1430, "SQLite")]
    for x, label in actors:
        draw.rounded_rectangle((x - 85, 130, x + 85, 185), radius=16, fill=PANEL, outline=BORDER, width=2)
        bbox = draw.textbbox((0, 0), label, font=font(18, True))
        draw.text((x - (bbox[2] - bbox[0]) / 2, 147), label, fill=TEXT, font=font(18, True))
        draw.line((x, 185, x, 900), fill=BORDER, width=2)

    steps = [
        (130, 450, 240, "POST /agent-runs"),
        (450, 1430, 310, "save user + run"),
        (130, 450, 380, "GET SSE stream"),
        (450, 780, 450, "RouteDecision"),
        (780, 450, 520, "route.decision"),
        (450, 780, 590, "Agent.as_tool"),
        (780, 1110, 660, "model / tools"),
        (1110, 780, 730, "answers"),
        (450, 1110, 800, "compare + judge"),
        (450, 1430, 870, "events + final output"),
    ]
    for x1, x2, y, label in steps:
        color = TEAL if x2 > x1 else BLUE
        draw.line((x1, y, x2, y), fill=color, width=3)
        direction = 1 if x2 > x1 else -1
        draw.polygon([(x2, y), (x2 - 12 * direction, y - 7), (x2 - 12 * direction, y + 7)], fill=color)
        midpoint = (x1 + x2) // 2
        bbox = draw.textbbox((0, 0), label, font=font(16))
        draw.rounded_rectangle((midpoint - (bbox[2] - bbox[0]) / 2 - 8, y - 28, midpoint + (bbox[2] - bbox[0]) / 2 + 8, y - 4), radius=8, fill=BG)
        draw.text((midpoint - (bbox[2] - bbox[0]) / 2, y - 27), label, fill=MUTED, font=font(16))
    image.save(DOCS / "agent-sequence.png", quality=95)


if __name__ == "__main__":
    DOCS.mkdir(parents=True, exist_ok=True)
    architecture()
    sequence()
    print("Generated diagram PNGs in", DOCS)
