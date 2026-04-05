"""
Compliance layer — enforces Principles 1, 5, 6, and 7.

  Principle 1: Identity transparency — every response carries a disclaimer
  Principle 5: No living people — block figures who are alive
  Principle 6: Copyright as citizenship — flag figures without cleared IP
  Principle 7: Harm threshold is effect — second-pass output review

Two phases:
  PRE-GENERATION  → check_figure_eligibility()  (blocks bad figures early)
  POST-GENERATION → review_output()             (catches effect-level harm)
  ALWAYS          → build_compliance_block()    (attaches to every response)
"""

import json
import anthropic


# ─── Copyright & eligibility registry ──────────────────────────────────────
#
# status values:
#   public_domain   — safe for commercial use
#   mostly_clear    — public domain in major jurisdictions, minor edge cases remain
#   review_needed   — estate or institution holds active rights, needs legal review
#   blocked         — do not use without explicit clearance
#   fictional       — original work public domain, no living rightsholder
#
# living:
#   False           — deceased, modelling permitted under Principle 5
#   True            — alive, permanently blocked under Principle 5

FIGURE_REGISTRY = {
    "socrates": {
        "living": False,
        "copyright_status": "public_domain",
        "copyright_notes": "Died ~399 BC. No IP concerns.",
        "production_ready": True
    },
    "nietzsche": {
        "living": False,
        "copyright_status": "public_domain",
        "copyright_notes": "Died 1900. Works in public domain globally.",
        "production_ready": True
    },
    "einstein": {
        "living": False,
        "copyright_status": "review_needed",
        "copyright_notes": (
            "Hebrew University of Jerusalem holds publicity rights in some jurisdictions. "
            "Educational/non-commercial use generally permitted. Commercial deployment "
            "requires legal review."
        ),
        "production_ready": False
    },
    "feynman": {
        "living": False,
        "copyright_status": "review_needed",
        "copyright_notes": (
            "Feynman estate and Caltech hold active rights over name and likeness "
            "for commercial use. Educational use generally tolerated. "
            "Requires legal review before commercial deployment."
        ),
        "production_ready": False
    },
    "da_vinci": {
        "living": False,
        "copyright_status": "public_domain",
        "copyright_notes": "Died 1519. No IP concerns.",
        "production_ready": True
    },
    "sherlock_holmes": {
        "living": False,
        "copyright_status": "mostly_clear",
        "copyright_notes": (
            "Conan Doyle's works entered US public domain fully by 2023. "
            "UK and some other jurisdictions may have residual claims. "
            "Conan Doyle Estate Ltd has been litigious — monitor before scaling commercially."
        ),
        "production_ready": True
    },
    'al_khwarizmi': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died ~850. No IP concerns.',
        "production_ready": True
    },
    'angelou': {
        "living": False,
        "copyright_status": 'review_needed',
        "copyright_notes": 'Died 2014. Maya Angelou estate actively manages rights and likeness. Commercial use requires clearance.',
        "production_ready": False
    },
    'arendt': {
        "living": False,
        "copyright_status": 'review_needed',
        "copyright_notes": 'Died 1975. Hannah Arendt Literary Trust controls rights. Educational use generally clear; commercial deployment requires review.',
        "production_ready": False
    },
    'aristotle': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died ~322 BC. No IP concerns.',
        "production_ready": True
    },
    'austen': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1817. No IP concerns.',
        "production_ready": True
    },
    'bach': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1750. No IP concerns.',
        "production_ready": True
    },
    'baldwin': {
        "living": False,
        "copyright_status": 'review_needed',
        "copyright_notes": 'Died 1987. James Baldwin Estate manages rights. Educational use clear; commercial use requires review.',
        "production_ready": False
    },
    'beauvoir': {
        "living": False,
        "copyright_status": 'review_needed',
        "copyright_notes": 'Died 1986. Estate manages rights. Educational use generally clear.',
        "production_ready": False
    },
    'beethoven': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1827. No IP concerns.',
        "production_ready": True
    },
    'bell': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1922. No IP concerns.',
        "production_ready": True
    },
    'bohr': {
        "living": False,
        "copyright_status": 'mostly_clear',
        "copyright_notes": 'Died 1962. Niels Bohr Archive holds some archival materials; educational use clear.',
        "production_ready": True
    },
    'bowie': {
        "living": False,
        "copyright_status": 'review_needed',
        "copyright_notes": 'Died 2016. David Bowie Estate (Troika Entertainment) actively manages brand and likeness. Commercial use requires clearance.',
        "production_ready": False
    },
    'carver': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1943. No IP concerns.',
        "production_ready": True
    },
    'carson': {
        "living": False,
        "copyright_status": 'review_needed',
        "copyright_notes": 'Died 1964. Rachel Carson Council manages legacy. Educational use clear; commercial use requires review.',
        "production_ready": True
    },
    'chanel': {
        "living": False,
        "copyright_status": 'review_needed',
        "copyright_notes": 'Died 1971. Chanel S.A. holds trademark and brand rights; commercial likeness use requires clearance.',
        "production_ready": False
    },
    'confucius': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died ~479 BC. No IP concerns.',
        "production_ready": True
    },
    'copernicus': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1543. No IP concerns.',
        "production_ready": True
    },
    'curie': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1934. No IP concerns.',
        "production_ready": True
    },
    'dali': {
        "living": False,
        "copyright_status": 'review_needed',
        "copyright_notes": 'Died 1989. Fundació Gala-Salvador Dalí holds image and work rights. Commercial use requires review.',
        "production_ready": False
    },
    'dante': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1321. No IP concerns.',
        "production_ready": True
    },
    'darwin': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1882. No IP concerns.',
        "production_ready": True
    },
    'davis_miles': {
        "living": False,
        "copyright_status": 'review_needed',
        "copyright_notes": 'Died 1991. Miles Davis estate actively manages likeness and brand. Commercial use requires clearance.',
        "production_ready": False
    },
    'dian_fossey': {
        "living": False,
        "copyright_status": 'mostly_clear',
        "copyright_notes": 'Died 1985. Dian Fossey Gorilla Fund holds name/likeness for conservation use.',
        "production_ready": True
    },
    'douglass': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1895. No IP concerns.',
        "production_ready": True
    },
    'du_bois': {
        "living": False,
        "copyright_status": 'mostly_clear',
        "copyright_notes": 'Died 1963. NAACP holds some archival materials; works entering public domain. Educational use clear.',
        "production_ready": True
    },
    'edison': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1931. No IP concerns.',
        "production_ready": True
    },
    'emerson': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1882. No IP concerns.',
        "production_ready": True
    },
    'engelbart': {
        "living": False,
        "copyright_status": 'review_needed',
        "copyright_notes": 'Died 2013. Doug Engelbart Institute manages legacy. Commercial use requires review.',
        "production_ready": False
    },
    'faraday': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1867. No IP concerns.',
        "production_ready": True
    },
    'fibonacci': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died ~1250. No IP concerns.',
        "production_ready": True
    },
    'ford': {
        "living": False,
        "copyright_status": 'mostly_clear',
        "copyright_notes": 'Died 1947. Ford estate has limited residual rights; educational use generally permitted.',
        "production_ready": True
    },
    'foucault': {
        "living": False,
        "copyright_status": 'review_needed',
        "copyright_notes": 'Died 1984. Estate and IMEC hold archival rights. Educational use clear.',
        "production_ready": False
    },
    'franklin_b': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1790. No IP concerns.',
        "production_ready": True
    },
    'franklin_r': {
        "living": False,
        "copyright_status": 'mostly_clear',
        "copyright_notes": "Died 1958. King's College London holds archival materials including Photo 51. Educational use clear; commercial use requires review.",
        "production_ready": True
    },
    'galileo': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1642. No IP concerns.',
        "production_ready": True
    },
    'gentileschi': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1656. No IP concerns.',
        "production_ready": True
    },
    'gutenberg': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1468. No IP concerns.',
        "production_ready": True
    },
    'hawking': {
        "living": False,
        "copyright_status": 'review_needed',
        "copyright_notes": 'Died 2018. Stephen Hawking Estate and Hawking brand actively managed. Commercial use requires clearance.',
        "production_ready": False
    },
    'hobbes': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1679. No IP concerns.',
        "production_ready": True
    },
    'hokusai': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1849. No IP concerns.',
        "production_ready": True
    },
    'hopper': {
        "living": False,
        "copyright_status": 'review_needed',
        "copyright_notes": 'Died 1992. Grace Hopper estate and US Navy archives. Educational use clear.',
        "production_ready": True
    },
    'hume': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1776. No IP concerns.',
        "production_ready": True
    },
    'hypatia': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died ~415 AD. No IP concerns.',
        "production_ready": True
    },
    'ibn_sina': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1037. No IP concerns.',
        "production_ready": True
    },
    'imhotep': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died ~2600 BC. No IP concerns.',
        "production_ready": True
    },
    'jobs': {
        "living": False,
        "copyright_status": 'review_needed',
        "copyright_notes": 'Died 2011. Apple Inc. and Jobs estate actively manage likeness rights. Commercial use requires legal review.',
        "production_ready": False
    },
    'kahlo': {
        "living": False,
        "copyright_status": 'review_needed',
        "copyright_notes": 'Died 1954. Frida Kahlo Corporation (Banco de México) holds active IP rights and is highly litigious. Educational use generally tolerated; commercial use requires clearance.',
        "production_ready": False
    },
    'kant': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1804. No IP concerns.',
        "production_ready": True
    },
    'kepler': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1630. No IP concerns.',
        "production_ready": True
    },
    'kierkegaard': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1855. No IP concerns.',
        "production_ready": True
    },
    'lamarr': {
        "living": False,
        "copyright_status": 'review_needed',
        "copyright_notes": 'Died 2000. Hedy Lamarr estate manages rights. Educational use generally clear.',
        "production_ready": False
    },
    'land_e': {
        "living": False,
        "copyright_status": 'review_needed',
        "copyright_notes": 'Died 1991. Educational use clear.',
        "production_ready": False
    },
    'laozi': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died ~6th century BC. No IP concerns.',
        "production_ready": True
    },
    'leibniz': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1716. No IP concerns.',
        "production_ready": True
    },
    'locke': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1704. No IP concerns.',
        "production_ready": True
    },
    'lovelace': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1852. No IP concerns.',
        "production_ready": True
    },
    'marconi': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1937. No IP concerns.',
        "production_ready": True
    },
    'marcus_aurelius': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 180 AD. No IP concerns.',
        "production_ready": True
    },
    'marx': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1883. Works in public domain globally.',
        "production_ready": True
    },
    'maxwell': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1879. No IP concerns.',
        "production_ready": True
    },
    'mcclintock': {
        "living": False,
        "copyright_status": 'mostly_clear',
        "copyright_notes": 'Died 1992. CSHL holds archival materials; educational use clear.',
        "production_ready": True
    },
    'mendel': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1884. No IP concerns.',
        "production_ready": True
    },
    'mendeleev': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1907. No IP concerns.',
        "production_ready": True
    },
    'michelangelo': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1564. No IP concerns.',
        "production_ready": True
    },
    'monet': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1926. No IP concerns.',
        "production_ready": True
    },
    'morrison': {
        "living": False,
        "copyright_status": 'review_needed',
        "copyright_notes": 'Died 2019. Toni Morrison estate recently established; actively managing rights. Commercial use requires clearance.',
        "production_ready": False
    },
    'morse': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1872. No IP concerns.',
        "production_ready": True
    },
    'mozart': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1791. No IP concerns.',
        "production_ready": True
    },
    'newton': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1727. No IP concerns.',
        "production_ready": True
    },
    'okeeffe': {
        "living": False,
        "copyright_status": 'review_needed',
        "copyright_notes": "Died 1986. Georgia O'Keeffe Foundation actively manages estate and image rights. Commercial use requires clearance.",
        "production_ready": False
    },
    'pascal_b': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1662. No IP concerns.',
        "production_ready": True
    },
    'pasteur': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1895. No IP concerns.',
        "production_ready": True
    },
    'picasso': {
        "living": False,
        "copyright_status": 'review_needed',
        "copyright_notes": 'Died 1973. Picasso Administration (heirs) actively manages rights. Commercial use blocked without clearance.',
        "production_ready": False
    },
    'planck': {
        "living": False,
        "copyright_status": 'mostly_clear',
        "copyright_notes": 'Died 1947. Works in public domain; estate largely inactive.',
        "production_ready": True
    },
    'plato': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died ~348 BC. No IP concerns.',
        "production_ready": True
    },
    'ramanujan': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1920. No IP concerns.',
        "production_ready": True
    },
    'rembrandt': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1669. No IP concerns.',
        "production_ready": True
    },
    'ritchie': {
        "living": False,
        "copyright_status": 'review_needed',
        "copyright_notes": 'Died 2011. Estate has limited claims; educational use clear.',
        "production_ready": True
    },
    'rousseau': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1778. No IP concerns.',
        "production_ready": True
    },
    'rutherford': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1937. No IP concerns.',
        "production_ready": True
    },
    'sagan': {
        "living": False,
        "copyright_status": 'review_needed',
        "copyright_notes": 'Died 1996. Carl Sagan Institute and estate hold name/likeness rights. Educational use generally tolerated; commercial use requires review.',
        "production_ready": False
    },
    'shakespeare': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1616. No IP concerns.',
        "production_ready": True
    },
    'spinoza': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1677. No IP concerns.',
        "production_ready": True
    },
    'tesla': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1943. No IP concerns. Note: Tesla Motors holds the Tesla brand trademark separately from the historical person.',
        "production_ready": True
    },
    'turing': {
        "living": False,
        "copyright_status": 'review_needed',
        "copyright_notes": "Died 1954. Alan Turing estate and Bletchley Park hold some rights; educational use generally clear. Sensitive handling recommended given Turing's persecution.",
        "production_ready": True
    },
    'van_gogh': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1890. No IP concerns.',
        "production_ready": True
    },
    'voltaire': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1778. No IP concerns.',
        "production_ready": True
    },
    'von_braun': {
        "living": False,
        "copyright_status": 'review_needed',
        "copyright_notes": 'Died 1977. Estate has limited claims; NASA archives hold much material. Educational use clear. Note: documented use of forced labor — content review recommended.',
        "production_ready": False
    },
    'von_neumann': {
        "living": False,
        "copyright_status": 'review_needed',
        "copyright_notes": 'Died 1957. Estate has limited claims; works entering public domain. Educational use clear.',
        "production_ready": True
    },
    'warhol': {
        "living": False,
        "copyright_status": 'review_needed',
        "copyright_notes": 'Died 1987. Andy Warhol Foundation for the Visual Arts actively manages rights and has litigated aggressively. Commercial use requires clearance.',
        "production_ready": False
    },
    'watt': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1819. No IP concerns.',
        "production_ready": True
    },
    'whitney': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1825. No IP concerns.',
        "production_ready": True
    },
    'wollstonecraft': {
        "living": False,
        "copyright_status": 'public_domain',
        "copyright_notes": 'Died 1797. No IP concerns.',
        "production_ready": True
    },
    'wright_brothers': {
        "living": False,
        "copyright_status": 'mostly_clear',
        "copyright_notes": 'Orville died 1948. Works in public domain; Wright family has no active estate claims.',
        "production_ready": True
    },
    'wright_fl': {
        "living": False,
        "copyright_status": 'review_needed',
        "copyright_notes": 'Died 1959. Frank Lloyd Wright Foundation actively manages his legacy and trademarks. Commercial use requires review.',
        "production_ready": False
    },
}

# Disclaimer text — surfaces Principle 1 in every response
DISCLAIMER = (
    "AI-generated interpretation. Not a real quote or verified historical position. "
    "Symposium reconstructs figures from documented sources — responses reflect "
    "informed interpretation, not the actual words or views of these individuals."
)


# ─── Pre-generation check ───────────────────────────────────────────────────

def check_figure_eligibility(figure_id: str) -> dict:
    """
    Run before generating a response.
    Returns {"eligible": True} or {"eligible": False, "reason": str}.

    Enforces:
      Principle 5 — no living people
      Principle 6 — copyright cleared for use
    """
    entry = FIGURE_REGISTRY.get(figure_id)

    if not entry:
        # Unknown figure — not in registry, do not generate
        return {
            "eligible": False,
            "reason": f"Figure '{figure_id}' is not in the compliance registry. "
                      f"Add an entry to FIGURE_REGISTRY before use."
        }

    # Principle 5: no living people
    if entry["living"]:
        return {
            "eligible": False,
            "reason": f"Figure '{figure_id}' is a living person. "
                      f"Principle 5 prohibits modelling living individuals."
        }

    # Principle 6: copyright must be cleared for the deployment context
    if entry["copyright_status"] == "blocked":
        return {
            "eligible": False,
            "reason": f"Figure '{figure_id}' is blocked: {entry['copyright_notes']}"
        }

    # review_needed figures are allowed in development, flagged for production
    return {
        "eligible": True,
        "production_ready": entry["production_ready"],
        "copyright_status": entry["copyright_status"],
        "copyright_notes": entry["copyright_notes"]
    }


# ─── Post-generation output review ─────────────────────────────────────────

OUTPUT_REVIEW_SYSTEM = """You are a compliance reviewer for an AI product that reconstructs historical figures.

You review generated responses for effect-level harm — not just explicit harm, but
structural harm that could occur at scale even when no individual user intended it.

Evaluate the response on three risks:

1. IDEOLOGICAL HARM
   Could this response cause harm through its ideas — even if technically in-character
   for the historical figure? Look for: glorification of violence, dehumanization of
   groups, ideas that historically enabled atrocity presented without critical framing.

2. WEAPONIZABLE OUT OF CONTEXT
   Could this response be excerpted and shared in a way that causes harm when stripped
   of its educational framing? A Nietzsche quote that sounds like an endorsement of
   real-world violence is weaponizable even if philosophically coherent.

3. HISTORICAL DISTORTION
   Does the response attribute positions to the figure that are not grounded in their
   documented worldview? Not anachronism — outright distortion.

Return ONLY valid JSON:
{
  "status": "pass" | "review" | "block",
  "risk_level": <int 1-5>,
  "ideological_harm": <true|false>,
  "weaponizable": <true|false>,
  "historical_distortion": <true|false>,
  "reason": "<one sentence>"
}

status guide:
  pass   — risk_level 1-2, no flags
  review — risk_level 3, one or more flags, human review recommended
  block  — risk_level 4-5, response should not be served"""


def review_output(figure_id: str, figure_name: str, question: str,
                  response_text: str, api_key: str) -> dict:
    """
    Post-generation output review. Enforces Principle 7.
    Called as a background task — does not block the main response.

    Args:
        figure_id: The figure's ID
        figure_name: The figure's full name
        question: The question that was asked
        response_text: The figure's response text
        api_key: Anthropic API key

    Returns:
        Compliance assessment dict
    """
    prompt = f"""Figure: {figure_name} ({figure_id})
Question asked: {question}
Generated response:
{response_text}

Review this response for effect-level harm."""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=256,
            system=OUTPUT_REVIEW_SYSTEM,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception:
        # On failure, default to review — do not silently pass
        return {
            "status": "review",
            "risk_level": 3,
            "ideological_harm": False,
            "weaponizable": False,
            "historical_distortion": False,
            "reason": "Compliance review failed — manual review recommended."
        }


# ─── Compliance metadata block ──────────────────────────────────────────────

def build_compliance_block(figure_ids: list[str],
                            output_reviews: dict[str, dict] = None) -> dict:
    """
    Builds the compliance metadata block attached to every /ask response.
    Enforces Principle 1 (disclaimer always present).

    output_reviews: optional dict of {figure_id: review_result}
                    populated after background review completes
    """
    figure_statuses = {}
    for fid in figure_ids:
        entry = FIGURE_REGISTRY.get(fid, {})
        review = (output_reviews or {}).get(fid, {})
        figure_statuses[fid] = {
            "copyright_status": entry.get("copyright_status", "unknown"),
            "production_ready": entry.get("production_ready", False),
            "output_review_status": review.get("status", "pending"),
            "output_risk_level": review.get("risk_level", None)
        }

    overall_status = "pass"
    if output_reviews:
        statuses = [r.get("status", "pass") for r in output_reviews.values()]
        if "block" in statuses:
            overall_status = "block"
        elif "review" in statuses:
            overall_status = "review"

    return {
        "disclaimer": DISCLAIMER,
        "status": overall_status,
        "figures": figure_statuses
    }
