from typing import Dict, Any

FIGURES: Dict[str, Dict[str, Any]] = {
}

# ─── Extended figure sets ───────────────────────────────────────────────────
# Each module adds a separate category dict that gets merged in here.

try:
    from figures.figures_philosophy import FIGURES_PHILOSOPHY
    FIGURES.update(FIGURES_PHILOSOPHY)
except ImportError:
    pass

try:
    from figures.figures_writers import FIGURES_WRITERS
    FIGURES.update(FIGURES_WRITERS)
except ImportError:
    pass

try:
    from figures.figures_social_science import FIGURES_SOCIAL_SCIENCE
    FIGURES.update(FIGURES_SOCIAL_SCIENCE)
except ImportError:
    pass

try:
    from figures.figures_computing import FIGURES_COMPUTING
    FIGURES.update(FIGURES_COMPUTING)
except ImportError:
    pass

try:
    from figures.figures_music import FIGURES_MUSIC
    FIGURES.update(FIGURES_MUSIC)
except ImportError:
    pass

try:
    from figures.figures_physics import FIGURES_PHYSICS
    FIGURES.update(FIGURES_PHYSICS)
except ImportError:
    pass

try:
    from figures.figures_art import FIGURES_ART
    FIGURES.update(FIGURES_ART)
except ImportError:
    pass

try:
    from figures.staging.film_configs import FIGURES_FILM
    FIGURES.update(FIGURES_FILM)
except ImportError:
    pass

DEFAULT_PANEL = list(FIGURES.keys())
