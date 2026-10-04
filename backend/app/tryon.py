"""
Virtual try-on: a photo of the user wearing one of their wardrobe items (or a
friperie scan), made by a diffusion model.

Realistic try-on models (CatVTON, IDM-VTON, Kolors) need 8-16 GB of GPU
memory, far more than our RTX 2050 (4 GB), so the picture is made by a model
hosted on a Hugging Face Space and called through `gradio_client`. Chosen by
TRYON_ENGINE in backend/.env:

    space  (default) the Spaces listed in TRYON_SPACES, tried IN ORDER: a
           Space that is broken, asleep, over quota or can't dress that kind
           of garment is skipped and the next one is tried. Free Spaces break
           often (2026-10-04: zhengchong/CatVTON was in RUNTIME_ERROR), so
           keep several. Each Space has its own inputs, so each needs an
           "adapter" below (ADAPTERS); a copy of a Space under another name
           uses its original's adapter: "someone/My-CatVTON=catvton".
    off    no try-on: /tryon answers 503 and the app shows its 2D overlay.

Garments are dressed one at a time: "upper" (top, jacket), "lower" (trousers,
skirt) or "overall" (dress). A full outfit is made by chaining: the result of
one garment is the person photo of the next. Only CatVTON knows all three;
IDM-VTON's automatic mask is for tops only, and Kolors was trained mostly on
tops (dresses work less well, trousers are not sent to it).

PRIVACY: the user's photo of themself is SENT TO THE SPACE (a third party).
The backend never saves it nor the result; the app tells the user before
they pick a photo.

Free Spaces run on shared GPUs ("ZeroGPU"): one garment takes ~20-60 s, the
anonymous quota is a few minutes of GPU a day. HF_TOKEN (a free Hugging Face
account token) raises the quota. When every Space fails, the error is
TryOnBusy (HTTP 502), and the app falls back to the overlay.

The router only needs:

    engine.dress(person, garment, kind) -> PIL image   (kind: upper / lower / overall)

Tests use a fake engine with the same method. From your machine (backend/):
    python -m app.tryon --check                          state of every Space in TRYON_SPACES
    python -m app.tryon person.jpg garment.jpg upper     a real try-on -> tryon_result.jpg
"""

import tempfile
from pathlib import Path

from PIL import Image

# which part of the body each category dresses; shoes, bags and accessories
# are not supported by the try-on models
KIND = {"top": "upper", "outerwear": "upper", "bottom": "lower",
        "dress": "overall", "traditional": "overall", "swimwear": "overall"}
# chaining order: a dress first, then trousers, then the top, the jacket last (on top)
ORDER = ["dress", "traditional", "swimwear", "bottom", "top", "outerwear"]


class TryOnUnavailable(Exception):
    """Try-on is switched off (HTTP 503)."""


class TryOnBusy(Exception):
    """The Space failed, is asleep, over quota or too slow (HTTP 502)."""


def make_tryon(settings):
    """The engine named by TRYON_ENGINE, or None when it is off."""
    if settings.tryon_engine == "off":
        return None
    return SpaceTryOn(settings)


def plan(docs):
    """Split wardrobe documents into (garments in dressing order, skipped ones).
    Skipped = [{"id", "reason"}]: a category the model can't put on."""
    garments = [d for d in docs if d["category"] in KIND]
    garments.sort(key=lambda d: ORDER.index(d["category"]))
    skipped = [{"id": str(d["_id"]), "reason": "unsupported"} for d in docs if d["category"] not in KIND]
    return garments, skipped


# ------------------------------------------------------------------ Space adapters
# Each one sends (person, garment, kind) to one Space's API, using the inputs
# shown on that Space's "Use via API" page, and returns what the Space answers.
# `files` holds the paths of person.png, garment.png and an empty mask.png.

def catvton(client, files, kind, settings):
    """zhengchong/CatVTON: the person input is an image editor (background = the
    photo, one layer = a hand-drawn mask; an empty layer = find the mask itself)."""
    from gradio_client import handle_file
    return client.submit(
        {"background": handle_file(files["person"]), "layers": [handle_file(files["mask"])],
         "composite": None},
        handle_file(files["garment"]),
        kind,                     # cloth_type: upper / lower / overall
        settings.tryon_steps,     # num_inference_steps (Space default 50)
        2.5,                      # guidance_scale (Space default)
        42,                       # seed: the same photo gives the same result
        "result only",            # show_type
        api_name="/submit_function")


def idm_vton(client, files, kind, settings):
    """yisol/IDM-VTON: its automatic mask (is_checked) only covers the upper body."""
    from gradio_client import handle_file
    return client.submit(
        {"background": handle_file(files["person"]), "layers": [], "composite": None},
        handle_file(files["garment"]),
        "a garment",              # garment_des: a short description of the garment
        True,                     # is_checked: make the mask automatically
        False,                    # is_checked_crop: the photo is not cropped
        settings.tryon_steps,     # denoise_steps
        42,                       # seed
        api_name="/tryon")


def kolors(client, files, kind, settings):
    """Kwai-Kolors/Kolors-Virtual-Try-On: no garment type, mostly trained on tops.
    Answers (picture, seed, message); the picture is empty when it is too busy."""
    from gradio_client import handle_file
    return client.submit(handle_file(files["person"]), handle_file(files["garment"]),
                         42, False,           # seed, randomize_seed
                         api_name="/tryon")


# adapter name -> (function, the kinds of garment it can dress)
ADAPTERS = {
    "catvton": (catvton, {"upper", "lower", "overall"}),
    "idm": (idm_vton, {"upper"}),
    "kolors": (kolors, {"upper", "overall"}),
}


def parse_spaces(text):
    """TRYON_SPACES ("owner/name, owner/name=adapter, ...") -> [(space, adapter)].
    Without "=adapter", the adapter is guessed from the Space name."""
    spaces = []
    for entry in filter(None, (e.strip() for e in text.split(","))):
        space, _, adapter = entry.partition("=")
        adapter = adapter.strip().lower() or next(
            (a for a in ADAPTERS if a in space.lower()), "")
        if adapter not in ADAPTERS:
            raise ValueError(f"TRYON_SPACES: no adapter for '{entry}'; "
                             f"write it as owner/name=adapter with adapter in {sorted(ADAPTERS)}")
        spaces.append((space.strip(), adapter))
    return spaces


def picture_from(out):
    """The Space's answer -> the path of the picture it made (or None)."""
    if isinstance(out, (list, tuple)):     # several outputs: the picture comes first
        out = out[0] if out else None
    if isinstance(out, dict):              # some Spaces answer {"path": ...}
        out = out.get("path")
    return out


class SpaceTryOn:
    def __init__(self, settings, make_client=None):
        self.settings = settings
        self.spaces = parse_spaces(settings.tryon_spaces)
        self._make_client = make_client or self._gradio_client
        self._clients = {}
        self.last_space = None             # which Space made the last picture

    def _gradio_client(self, space):
        from gradio_client import Client   # imported here: only needed when used
        return Client(space, token=self.settings.hf_token or None, verbose=False)

    def dress(self, person, garment, kind):
        """Try each Space in order; TryOnBusy (with every Space's reason) if none worked."""
        reasons = []
        with tempfile.TemporaryDirectory() as tmp:
            files = {name: Path(tmp) / f"{name}.png" for name in ("person", "garment", "mask")}
            person.save(files["person"])
            garment.save(files["garment"])
            Image.new("RGBA", person.size, (0, 0, 0, 0)).save(files["mask"])
            for space, adapter in self.spaces:
                call, kinds = ADAPTERS[adapter]
                if kind not in kinds:
                    reasons.append(f"{space}: can't dress '{kind}' garments")
                    continue
                try:
                    if space not in self._clients:
                        self._clients[space] = self._make_client(space)   # fails if broken / private
                    job = call(self._clients[space], files, kind, self.settings)
                    path = picture_from(job.result(timeout=self.settings.tryon_timeout))
                    if not path:
                        raise RuntimeError("no picture in the answer (too busy?)")
                    img = Image.open(path)
                    img.load()
                except Exception as e:             # broken, asleep, quota, timeout, API changed
                    self._clients.pop(space, None)  # reconnect next time
                    reasons.append(f"{space}: {str(e).splitlines()[0] if str(e) else type(e).__name__}")
                    continue
                self.last_space = space
                return img.convert("RGB")
        raise TryOnBusy("No try-on Space worked. " + " | ".join(reasons))


def check(settings):
    """Print the state of every Space in TRYON_SPACES (RUNNING, SLEEPING, RUNTIME_ERROR...)."""
    from huggingface_hub import HfApi
    api = HfApi(token=settings.hf_token or None)
    for space, adapter in parse_spaces(settings.tryon_spaces):
        try:
            runtime = api.get_space_runtime(space)
            state = f"{runtime.stage} (hardware: {runtime.hardware})"
        except Exception as e:
            state = f"can't read: {e}"
        print(f"{space:45} adapter={adapter:8} {state}")


if __name__ == "__main__":      # see the module docstring
    import sys

    from .config import Settings

    settings = Settings()
    if sys.argv[1:] == ["--check"]:
        check(settings)
        sys.exit()
    person_path, garment_path, kind = sys.argv[1:4]
    engine = SpaceTryOn(settings)
    result = engine.dress(Image.open(person_path).convert("RGB"),
                          Image.open(garment_path).convert("RGB"), kind)
    result.save("tryon_result.jpg")
    print(f"saved tryon_result.jpg {result.size}, made by {engine.last_space}")
