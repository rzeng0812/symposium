#!/usr/bin/env python3
"""
Summarise a Symposium conversation for social media in any language.

Usage:
    python summarise.py conversations/2026-03-29-truth-vs-power.md
    python summarise.py conversations/2026-03-29-truth-vs-power.md --lang French --platform long_form
    python summarise.py --all --lang Japanese
    python summarise.py --all --lang "Chinese (Simplified)" --platform short_form

Platforms:
    social      Short social post (~800–1200 words). Hook, key exchanges, open question.
    short_form  Mid-length personal note (~500–800 words). Relatable angle, bullet insights.
    long_form   Deep-read article (~1500–2500 words). Full intellectual treatment.

Outputs a .<lang_code>.<platform>.md file alongside the original (or in a subdir with --all).
"""

import anthropic
import argparse
import os
import re
import sys
from pathlib import Path

# Load .env if present
_env = Path(__file__).parent / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        if line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip().strip('"').strip("'")

client = anthropic.Anthropic()

PLATFORM_PROMPTS = {
    "social": """You are a thoughtful writer who shares philosophy and intellectual history for a general educated audience on social media.

Rewrite this philosophical dialogue as a social post in {lang}, following these rules:
- Open with one sentence that captures the sharpest conflict or most striking idea — make it impossible to scroll past
- Develop 2–3 of the most compelling exchanges, using quoted speech to preserve the force of each position
- Close with an open question that invites the reader to respond
- Tone: intellectually serious but not academic; a point of view is permitted, moralising is not
- Length: 800–1200 words
- Hashtags: at most 3, substantive (not engagement-bait)

Do not translate line by line. Reframe — find the angle that will resonate most with {lang}-speaking readers today.
Find the natural cultural entry points and intellectual traditions that {lang}-speaking readers bring to these questions.""",

    "short_form": """You are a writer who shares philosophy and human insight on short-form platforms in {lang}, with a style that is genuine, perceptive, and grounded in lived experience.

Rewrite this philosophical dialogue as a short-form post in {lang}, following this structure:
- Title: a resonant question or insight (under 20 words)
- Body:
  · Open with a real everyday scene or feeling that connects to the theme (2–3 sentences)
  · State the core question of this dialogue (under 50 words)
  · 3–4 key positions, each with a one-line commentary (use bullet points)
  · A brief personal reflection to close (under 50 words)
- Tone: like talking to a thoughtful friend — no showing off, but real depth
- Length: 500–800 words
- End with 3–5 hashtags

Find the angle that makes this dialogue land in real life — what does it have to do with ordinary people's relationships, feelings, or current circumstances in the {lang}-speaking world?""",

    "long_form": """You are a writer crafting long-form essays in {lang} for an educated readership with serious interest in ideas.

Rewrite this philosophical dialogue as a long-form article in {lang}, following this structure:
- Title: precise and charged (question form or thesis form both work)
- Structure:
  · Introduction: open with a contemporary phenomenon or personal puzzle that draws out the theme (under 200 words)
  · "The Collision of Ideas": present the main positions in logical order (not the order of the dialogue), making each thinker's stance clear and fair
  · "For Our Moment": connect this dialogue to contemporary questions — technology, generational change, social pressure, identity, political life — as they appear in {lang}-speaking societies
  · Closing: offer an angle, not an answer
- Tone: restrained but forceful; literary without being ornate; no lecturing
- Length: 1500–2500 words
- Subheadings are encouraged

This is not a translation — it is a recreation. Find the resonances between this dialogue and the intellectual traditions {lang}-speaking readers carry: their philosophical inheritance, their contemporary debates, their cultural tensions. Build those bridges explicitly.""",
}

DEFAULT_PLATFORM = "all"


def lang_to_code(lang: str) -> str:
    """Convert a language name to a short file-safe code."""
    mapping = {
        "chinese": "zh",
        "chinese (simplified)": "zh",
        "chinese (traditional)": "zh-tw",
        "mandarin": "zh",
        "japanese": "ja",
        "korean": "ko",
        "french": "fr",
        "german": "de",
        "spanish": "es",
        "portuguese": "pt",
        "italian": "it",
        "arabic": "ar",
        "russian": "ru",
        "hindi": "hi",
        "english": "en",
    }
    return mapping.get(lang.lower(), re.sub(r"[^a-z0-9]", "", lang.lower())[:6])


def read_conversation(path: str) -> str:
    with open(path, "r") as f:
        return f.read()


def extract_metadata(content: str) -> dict:
    """Pull title, date, panel from markdown header."""
    lines = content.split("\n")
    meta = {}
    for line in lines[:10]:
        if line.startswith("# "):
            meta["title"] = line[2:].strip()
        elif line.startswith("**Panel:**"):
            meta["panel"] = line.replace("**Panel:**", "").strip()
        elif line.startswith("**Date:**"):
            meta["date"] = line.replace("**Date:**", "").strip()
    return meta


def summarise(conversation: str, platform: str, lang: str) -> str:
    system = PLATFORM_PROMPTS[platform].format(lang=lang)
    prompt = f"""Below is the full transcript of a philosophical dialogue (original English). Please create the {platform} content as instructed above.

---

{conversation}

---

Output the {lang} content directly. No preamble or explanation."""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
        system=system,
    )
    return message.content[0].text


def process_file(input_path: str, platform: str, lang: str, output_dir: str = None):
    path = Path(input_path)
    content = read_conversation(input_path)
    meta = extract_metadata(content)

    title = meta.get("title", path.stem)
    panel = meta.get("panel", "")
    date = meta.get("date", "")
    lang_code = lang_to_code(lang)

    print(f"\n{'='*60}")
    print(f"Question: {title}")
    print(f"Panel:    {panel}")
    print(f"Language: {lang} ({lang_code})")
    print(f"Platform: {platform}")

    result = summarise(content, platform, lang)

    stem = f"{path.stem}.{lang_code}.{platform}"
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        out_path = Path(output_dir) / f"{stem}.md"
    else:
        out_path = path.parent / f"{stem}.md"

    header = f"""---
source: {path.name}
question: {title}
panel: {panel}
date: {date}
language: {lang}
platform: {platform}
---

"""
    with open(out_path, "w") as f:
        f.write(header + result)

    print(f"Saved: {out_path}")
    return str(out_path)


def main():
    parser = argparse.ArgumentParser(
        description="Summarise Symposium conversations for social media in any language"
    )
    parser.add_argument("file", nargs="?", help="Conversation markdown file to process")
    parser.add_argument(
        "--lang",
        default="Chinese (Simplified)",
        help='Target language (default: "Chinese (Simplified)")',
    )
    parser.add_argument(
        "--platform",
        choices=["social", "short_form", "long_form", "all"],
        default="all",
        help="Target platform format (default: all)",
    )
    parser.add_argument("--all", action="store_true", help="Process all conversation files")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory (default: same directory as input)",
    )
    args = parser.parse_args()

    platforms = list(PLATFORM_PROMPTS.keys()) if args.platform == "all" else [args.platform]
    lang_code = lang_to_code(args.lang)

    if args.all:
        conv_dir = Path(__file__).parent / "conversations"
        files = sorted(conv_dir.glob("*.md"))
        # Exclude already-generated output files and index files
        files = [
            f for f in files
            if not re.search(r"\.[a-z]{2,6}\.(social|short_form|long_form)\.md$", f.name)
            and f.name != "questions.md"
        ]
        output_dir = args.output_dir or str(conv_dir / lang_code)
    elif args.file:
        files = [Path(args.file)]
        output_dir = args.output_dir
    else:
        parser.print_help()
        sys.exit(1)

    print(f"Files to process: {len(files)}")
    print(f"Language: {args.lang} ({lang_code})")
    print(f"Platforms: {platforms}")
    if output_dir:
        print(f"Output dir: {output_dir}")

    saved = []
    for f in files:
        for platform in platforms:
            stem = f"{f.stem}.{lang_code}.{platform}"
            if output_dir:
                out_path = Path(output_dir) / f"{stem}.md"
            else:
                out_path = f.parent / f"{stem}.md"

            if out_path.exists():
                print(f"Skipping (exists): {out_path.name}")
                continue

            try:
                path = process_file(str(f), platform, args.lang, output_dir)
                saved.append(path)
            except Exception as e:
                print(f"ERROR on {f.name} ({platform}): {e}")

    print(f"\n{'='*60}")
    print(f"Done. Saved {len(saved)} files.")
    for s in saved:
        print(f"  ✓ {s}")


if __name__ == "__main__":
    main()
