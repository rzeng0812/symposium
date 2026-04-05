#!/usr/bin/env python3
"""
Summarise a Symposium conversation for Chinese social media.

Usage:
    python summarise_for_zh.py conversations/2026-03-29-marriage-freedom.md
    python summarise_for_zh.py conversations/2026-03-29-marriage-freedom.md --platform weibo
    python summarise_for_zh.py --all                  # process all files
    python summarise_for_zh.py --all --platform xiaohongshu

Outputs a .zh.md file alongside the original (or in zh/ subdir with --all).
"""

import anthropic
import argparse
import os
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
    "weibo": """你是一位擅长知识传播的微博博主，专注于哲学和思想领域的内容创作。

请将这场哲学对话改写为微博帖子，要求：
- 开头一句话点出核心冲突或最犀利的观点（要有冲击力，让人忍不住点开）
- 展开2-3个最精彩的交锋瞬间，用引号保留原话的力量感
- 结尾留下一个开放性问题，引发读者讨论
- 语气：知识分子风格，但不失锐气；可以有立场，但不煽动
- 总字数：800-1200字
- 可以用话题标签，但不超过3个，要有实质内容而非流量词

不要逐段翻译，要重新框架（reframe）——找到这场对话对今天中国读者最有共鸣的切入点。""",

    "xiaohongshu": """你是一位在小红书分享哲学和人文思考的创作者，风格：真诚、有洞察力、贴近生活。

请将这场哲学对话改写为小红书笔记，要求：
- 标题：能引发共鸣的问题或洞见（不超过20字）
- 正文结构：
  · 用一个生活中真实场景或感受作为切入（2-3句）
  · 介绍这场对话的核心问题（不超过50字）
  · 3-4个关键观点，每个配一句话点评（用•分隔）
  · 最后的个人感悟（50字以内）
- 语气：像朋友聊天，不卖弄，但有深度
- 总字数：500-800字
- 末尾3-5个话题标签

找到让这场对话「落地」的角度——它和普通人的生活、感情、或当下处境有什么关联？""",

    "wechat": """你是一位为微信公众号撰写深度文章的作者，读者是受过良好教育、对思想议题感兴趣的中国知识阶层。

请将这场哲学对话改写为一篇微信公众号文章，要求：
- 标题：点题精准，有张力（可以是问题式或观点式）
- 结构：
  · 引言：用一个当下现象或个人困惑引出主题（150字以内）
  · 「思想碰撞」：按逻辑线（而非原对话顺序）呈现主要观点交锋，每位思想家的立场要清晰
  · 「我们这个时代」：将这场对话与当代中国语境连接（可以讨论：技术、代际、社会压力、身份认同等）
  · 结语：不给答案，给角度
- 语气：克制而有力，有文人气质，不说教
- 总字数：1500-2500字
- 可加小标题帮助结构

这不是翻译，是再创作。找到这场对话在中文思想传统中的对话者——儒道、近现代思想家——做必要的文化桥接。""",
}

DEFAULT_PLATFORM = "all"


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


def summarise(conversation: str, platform: str) -> str:
    system = PLATFORM_PROMPTS[platform]
    prompt = f"""以下是一场哲学对话的完整记录（英文原文）。请根据上述要求进行创作。

---

{conversation}

---

请直接输出{platform}格式的内容，不需要前言或解释。"""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
        system=system,
    )
    return message.content[0].text


def process_file(input_path: str, platform: str, output_dir: str = None):
    path = Path(input_path)
    content = read_conversation(input_path)
    meta = extract_metadata(content)

    title = meta.get("title", path.stem)
    panel = meta.get("panel", "")
    date = meta.get("date", "")

    print(f"\n{'='*60}")
    print(f"Question: {title}")
    print(f"Panel: {panel}")
    print(f"Platform: {platform}")

    result = summarise(content, platform)

    # Determine output path
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        out_path = Path(output_dir) / f"{path.stem}.{platform}.zh.md"
    else:
        out_path = path.parent / f"{path.stem}.{platform}.zh.md"

    # Write output with header
    header = f"""---
source: {path.name}
question: {title}
panel: {panel}
date: {date}
platform: {platform}
---

"""
    with open(out_path, "w") as f:
        f.write(header + result)

    print(f"Saved: {out_path}")
    return str(out_path)


def main():
    parser = argparse.ArgumentParser(description="Summarise Symposium conversations for Chinese social media")
    parser.add_argument("file", nargs="?", help="Conversation markdown file to process")
    parser.add_argument(
        "--platform",
        choices=["weibo", "xiaohongshu", "wechat", "all"],
        default="all",
        help="Target platform (default: all)",
    )
    parser.add_argument("--all", action="store_true", help="Process all conversation files")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory (default: same directory as input)",
    )
    args = parser.parse_args()

    platforms = list(PLATFORM_PROMPTS.keys()) if args.platform == "all" else [args.platform]

    if args.all:
        conv_dir = Path(__file__).parent / "conversations"
        files = sorted(conv_dir.glob("*.md"))
        # Exclude already-generated zh files and questions.md
        files = [f for f in files if ".zh." not in f.name and f.name != "questions.md"]
        output_dir = args.output_dir or str(conv_dir / "zh")
    elif args.file:
        files = [Path(args.file)]
        output_dir = args.output_dir
    else:
        parser.print_help()
        sys.exit(1)

    print(f"Files to process: {len(files)}")
    print(f"Platforms: {platforms}")
    if output_dir:
        print(f"Output dir: {output_dir}")

    saved = []
    for f in files:
        for platform in platforms:
            # Skip if already exists
            if output_dir:
                out_path = Path(output_dir) / f"{f.stem}.{platform}.zh.md"
            else:
                out_path = f.parent / f"{f.stem}.{platform}.zh.md"

            if out_path.exists():
                print(f"Skipping (exists): {out_path.name}")
                continue

            try:
                path = process_file(str(f), platform, output_dir)
                saved.append(path)
            except Exception as e:
                print(f"ERROR on {f.name} ({platform}): {e}")

    print(f"\n{'='*60}")
    print(f"Done. Saved {len(saved)} files.")
    for s in saved:
        print(f"  ✓ {s}")


if __name__ == "__main__":
    main()
