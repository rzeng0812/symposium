#!/usr/bin/env python3
"""Run a Symposium conversation and save it as a markdown file."""

import json, sys, requests, os, re, time

BASE = "http://localhost:8765"

def start(question, panel):
    r = requests.post(f"{BASE}/chat/start", json={
        "question": question, "panel": panel, "panel_size": len(panel)
    })
    return r.json()

def send(session_id, message):
    r = requests.post(f"{BASE}/chat/{session_id}", json={"message": message})
    return r.json()

def format_messages(messages):
    out = []
    for m in messages:
        if m["speaker_id"] == "user":
            continue
        out.append(f"**{m['speaker_name']} — {m['role']}**\n\n{m['content']}")
    return "\n\n---\n\n".join(out)

def run(question, panel, followup, slug):
    print(f"\n{'='*60}")
    print(f"Question: {question}")
    print(f"Panel: {panel}")

    data = start(question, panel)
    session_id = data["session_id"]
    opening_msgs = [m for m in data["messages"] if m["speaker_id"] != "user"]
    actual_panel = " · ".join(m["speaker_name"] for m in opening_msgs)
    print(f"Session: {session_id} | Panel: {actual_panel}")

    time.sleep(1)
    turn1 = send(session_id, followup)
    turn1_msgs = [m for m in turn1["messages"] if m["speaker_id"] != "user"]

    time.sleep(1)
    closing = send(session_id, "closing")
    closing_msgs = [m for m in closing["messages"] if m["speaker_id"] != "user"]

    md = f"""# {question}

**Session:** {session_id}
**Date:** 2026-03-29
**Panel:** {actual_panel}

---

## Opening

{format_messages(opening_msgs)}

---

## Turn 1 — {followup}

{format_messages(turn1_msgs)}

---

## Closing — last words

{format_messages(closing_msgs)}
"""

    path = f"/Users/rzeng/Projects/symposium/conversations/{slug}.md"
    with open(path, "w") as f:
        f.write(md)
    print(f"Saved: {path}")
    return path

CONVERSATIONS = [
    # Knowledge & Self
    (
        "Should some knowledge be forbidden?",
        ["turing", "darwin", "hawking", "socrates"],
        "Turing — you were prosecuted by the state for who you were. Does a government that punishes knowledge of the self have any authority to restrict knowledge of the world?",
        "2026-03-29-knowledge-forbidden"
    ),
    (
        "Is the self an illusion?",
        ["hume", "nietzsche", "turing", "spinoza"],
        "Hume — if the self is just a bundle of perceptions with no unified observer, who is it that noticed this?",
        "2026-03-29-self-illusion"
    ),
    (
        "Can a person ever truly change?",
        ["arendt", "aristotle", "beauvoir", "kierkegaard"],
        "Arendt — you watched people who committed great wrongs insist they had changed. Did you believe them?",
        "2026-03-29-person-change"
    ),
    (
        "Do we deserve credit for who we are?",
        ["rousseau", "kant", "darwin", "socrates"],
        "Darwin — if character is shaped by inheritance and environment, what remains that we can honestly call our own?",
        "2026-03-29-deserve-credit"
    ),
    # Society
    (
        "Is democracy the best we can do, or just the most comfortable?",
        ["plato", "rousseau", "marx", "locke"],
        "Plato — you argued democracy produces tyrants. Is there any evidence in the centuries since you died that you were wrong?",
        "2026-03-29-democracy-best"
    ),
    (
        "Does civilization require violence to sustain itself?",
        ["hobbes", "arendt", "nietzsche", "wollstonecraft"],
        "Arendt — you drew a sharp line between power and violence. Does civilisation run on power, or have we been confusing the two all along?",
        "2026-03-29-civilization-violence"
    ),
    (
        "Should art have moral obligations?",
        ["kahlo", "warhol", "gentileschi", "baldwin"],
        "Baldwin — you said the artist's job is to make the lie of the world visible. Does that make art inherently moral, or is that just what moral people do with art?",
        "2026-03-29-art-obligations"
    ),
    # Life & Meaning
    (
        "Is a comfortable life a wasted one?",
        ["nietzsche", "aristotle", "emerson", "marcus_aurelius"],
        "Marcus Aurelius — you commanded an empire and led armies. Does Stoic acceptance of fate leave any room for the ambition Nietzsche demands?",
        "2026-03-29-comfortable-life"
    ),
    (
        "Does suffering make people better or just more damaged?",
        ["nietzsche", "arendt", "kierkegaard", "marcus_aurelius"],
        "Arendt — you watched people survive unimaginable things and come out diminished, not ennobled. Does Nietzsche's 'what does not kill me' hold up against actual evidence?",
        "2026-03-29-suffering-better"
    ),
    (
        "Is there any difference between a meaningful life and a happy one?",
        ["nietzsche", "beauvoir", "aristotle", "kierkegaard"],
        "Aristotle — you coined eudaimonia to bridge happiness and flourishing. Is that still a useful distinction, or have we invented new ways to confuse them?",
        "2026-03-29-meaningful-vs-happy"
    ),
    # Love & Relationships
    (
        "Can you love someone you fully understand?",
        ["socrates", "beauvoir", "kierkegaard", "spinoza"],
        "Spinoza — you defined love as joy accompanied by the idea of an external cause. Does understanding the cause of joy destroy the joy, or deepen it?",
        "2026-03-29-love-understanding"
    ),
    (
        "Is jealousy a form of love or a failure of it?",
        ["nietzsche", "beauvoir", "shakespeare", "spinoza"],
        "Shakespeare — Othello, The Winter's Tale, A Midsummer Night's Dream. You staged jealousy more times than any philosopher theorised it. What did you learn?",
        "2026-03-29-jealousy-love"
    ),
    (
        "Is friendship more honest than romantic love?",
        ["aristotle", "beauvoir", "socrates", "spinoza"],
        "Aristotle — you called the highest friendship a love of virtue. Does that make it more like romance than you admitted, or less?",
        "2026-03-29-friendship-vs-romance"
    ),
    # Technology & AI
    (
        "Does artificial intelligence threaten or complete what makes us human?",
        ["turing", "lovelace", "nietzsche", "arendt"],
        "Turing — you asked whether machines can think. Did you expect the answer to unsettle the question of what thinking is for?",
        "2026-03-29-ai-human"
    ),
    (
        "If a machine can think, does it deserve rights?",
        ["turing", "kant", "darwin", "socrates"],
        "Kant — your moral framework rests on rational agency. If a machine reasons, does your own system demand you grant it dignity?",
        "2026-03-29-machine-rights"
    ),
    (
        "Is the algorithm the new god — invisible, unchallengeable, shaping everything?",
        ["foucault", "nietzsche", "pascal_b", "hobbes"],
        "Pascal — you wagered on God because the stakes were infinite. Would you make the same wager on the algorithm?",
        "2026-03-29-algorithm-god"
    ),
    (
        "Do we think differently because of the tools we use to think with?",
        ["da_vinci", "lovelace", "turing", "marx"],
        "Marx — you argued that the means of production shape consciousness. Does that apply to the tools of thought as well as the tools of labour?",
        "2026-03-29-tools-thinking"
    ),
    # Attention & Mind
    (
        "Is the inability to focus the defining illness of our age?",
        ["pascal_b", "nietzsche", "arendt", "feynman"],
        "Pascal — you wrote that all of humanity's problems stem from the inability to sit quietly in a room alone. Did you know you were describing the future?",
        "2026-03-29-inability-to-focus"
    ),
    (
        "Has the internet made us smarter or just more confident in our ignorance?",
        ["socrates", "darwin", "turing", "foucault"],
        "Socrates — you said the unexamined life is not worth living. Is the over-examined, over-shared, algorithmically-curated life any better?",
        "2026-03-29-internet-smarter"
    ),
    # Identity
    (
        "Has identity become a product to curate rather than a life to live?",
        ["beauvoir", "foucault", "warhol", "nietzsche"],
        "Warhol — you said everyone would be famous for fifteen minutes. Did you mean it as a warning?",
        "2026-03-29-identity-product"
    ),
    (
        "Is authenticity possible in a world that rewards performance?",
        ["kierkegaard", "beauvoir", "nietzsche", "warhol"],
        "Kierkegaard — you wrote under pseudonyms your entire life. Were you being authentic or performing authenticity?",
        "2026-03-29-authenticity-performance"
    ),
    # Connection & Loneliness
    (
        "Are we more connected or more alone than any generation before us?",
        ["arendt", "nietzsche", "aristotle", "pascal_b"],
        "Arendt — you wrote about loneliness as the ground for totalitarianism. Does mass connectivity dissolve that danger, or deepen it?",
        "2026-03-29-connected-or-alone"
    ),
    # Collapse & Civilisation
    (
        "Does our civilisation know it is declining?",
        ["nietzsche", "sagan", "arendt", "marcus_aurelius"],
        "Marcus Aurelius — you governed an empire you knew was overstretched, and wrote philosophy in a tent between campaigns. What did that feel like from the inside?",
        "2026-03-29-civilisation-declining"
    ),
    (
        "Can a society survive when it no longer shares a common story about itself?",
        ["arendt", "baldwin", "hobbes", "laozi"],
        "Baldwin — you spent your life telling Americans a story about themselves they refused to hear. Does a society need a true story, or just a shared one?",
        "2026-03-29-common-story"
    ),
    (
        "Do we have the right to reinvent ourselves, or do we owe others continuity?",
        ["arendt", "beauvoir", "darwin", "aristotle"],
        "Arendt — you fled Germany, changed your life entirely, and built a new identity in a new language. Did you feel you owed your past self anything?",
        "2026-03-29-reinvent-ourselves"
    ),
    (
        "Has social media made empathy better or worse?",
        ["beauvoir", "wollstonecraft", "hobbes", "turing"],
        "Wollstonecraft — you argued that education and exposure to others' lives builds moral feeling. Does infinite exposure to others' curated lives do the same work?",
        "2026-03-29-social-media-empathy"
    ),
    (
        "Is accelerationism — burning it down to rebuild — ever justified?",
        ["marx", "nietzsche", "wollstonecraft", "hobbes"],
        "Hobbes — you built your entire philosophy on the terror of collapse. Does that make you the strongest opponent of accelerationism, or its most honest theorist?",
        "2026-03-29-accelerationism"
    ),
]

if __name__ == "__main__":
    saved = []
    for q, panel, followup, slug in CONVERSATIONS:
        path = f"/Users/rzeng/Projects/symposium/conversations/{slug}.md"
        if os.path.exists(path):
            print(f"Skipping (exists): {slug}")
            continue
        try:
            path = run(q, panel, followup, slug)
            saved.append(slug)
        except Exception as e:
            print(f"ERROR on {slug}: {e}")
        time.sleep(2)

    print(f"\n{'='*60}")
    print(f"Done. Saved {len(saved)}/{len(CONVERSATIONS)} conversations.")
    for s in saved:
        print(f"  ✓ {s}")
