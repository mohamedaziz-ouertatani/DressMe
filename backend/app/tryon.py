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
    local  our own IDM-VTON service (the idm_service FastAPI app on this PC), at
           TRYON_SERVICE_URL (default http://localhost:8001). The photo never leaves the
           machine and there is no Space quota; about a minute per garment on the GPU.
    off    no try-on: /tryon answers 503 and the app shows its 2D overlay.

Garments are dressed one at a time: "upper" (top, jacket), "lower" (trousers,
skirt) or "overall" (dress). A full outfit is made by chaining: the result of
one garment is the person photo of the next. Only CatVTON knows all three;
OOTDiffusion knows all three too; IDM-VTON's automatic mask is for tops only,
and Kolors was trained mostly on tops (dresses work less well, trousers are
not sent to it). IDM-VTON also reads a short description ("grey hoodie"):
without it a hood lying flat was drawn as a high collar.

PRIVACY: the user's photo of themself is SENT TO THE SPACE (a third party).
The backend never saves it nor the result; the app tells the user before
they pick a photo.

Free Spaces run on shared GPUs ("ZeroGPU"): one garment takes ~20-60 s, the
anonymous quota is a few minutes of GPU a day. HF_TOKEN (a free Hugging Face
account token) raises the quota. When every Space fails, the error is
TryOnBusy (HTTP 502), and the app falls back to the overlay.

The router only needs:

    engine.dress(person, garment, kind, description) -> PIL image   (kind: upper / lower / overall)

Tests use a fake engine with the same method. From your machine (backend/):
    python -m app.tryon --check                          state of every Space in TRYON_SPACES
    python -m app.tryon person.jpg garment.jpg upper     a real try-on -> tryon_result.jpg
"""

import io
import tempfile
from pathlib import Path

from PIL import Image

# which part of the body each category dresses. Shoes and glasses only with an engine that
# can do them (its `kinds`: the local IDM-VTON service, experimental); bags, belts, hats and
# jewellery never.
KIND = {"top": "upper", "outerwear": "upper", "bottom": "lower",
        "dress": "overall", "traditional": "overall", "swimwear": "overall", "shoes": "shoes"}
GLASSES = {"glasses", "sunglasses"}         # accessory sub_categories dressed as "glasses"
EXTRAS = {"shoes", "glasses", "scarf"}       # the local service's experimental kinds
BASIC_KINDS = {"upper", "lower", "overall"}  # what every engine can dress
# chaining order: a dress first, then trousers, then the top, the jacket on top of it,
# then shoes (over the trouser hems), glasses last
ORDER = ["dress", "traditional", "swimwear", "bottom", "top", "outerwear", "shoes", "accessory"]


def kind_of(doc):
    """The body part a wardrobe item dresses (upper / lower / overall / shoes / glasses /
    scarf), or None."""
    if doc.get("category") == "accessory":
        sub = doc.get("sub_category")
        return "glasses" if sub in GLASSES else "scarf" if sub == "scarf" else None
    return KIND.get(doc.get("category"))


class TryOnUnavailable(Exception):
    """Try-on is switched off (HTTP 503)."""


class TryOnBusy(Exception):
    """The Space failed, is asleep, over quota or too slow (HTTP 502)."""

class LocalTryOn:
    """Try-on made by OUR OWN IDM-VTON service (idm_service, a FastAPI app running on the
    lab PC's GPU). Same contract as SpaceTryOn: dress(person, garment, kind, description).
    `kind` (upper / lower / overall) is sent as the service's `category`; the service
    builds the mask from it, so nothing is guessed from the description.

    Settings: tryon_service_url (TRYON_SERVICE_URL, already in config.py), and optionally
    tryon_local_steps (denoising steps, default 10: about 1 minute per garment) and
    tryon_local_timeout (seconds to wait for one garment, default 300), read with defaults.
    """
    private = True                         # the photo stays on this PC (GET /tryon/info)
    can_copy_looks = True                  # "Try this look": a whole outfit from someone's photo

    def __init__(self, settings):
        self.settings = settings
        self.url = (getattr(settings, "tryon_service_url", None) or "http://127.0.0.1:8001").rstrip("/")
        self.steps = getattr(settings, "tryon_local_steps", None) or 10
        self.timeout = getattr(settings, "tryon_local_timeout", None) or 300
        # shoes / glasses: the service's experimental masks, OFF unless listed in
        # TRYON_LOCAL_EXTRAS. First real test (2026-11-02): black running shoes came out as
        # beige slip-ons (IDM-VTON has no shoe training; a pair seen at an angle can't be
        # mapped onto two feet seen from the front)
        extras = getattr(settings, "tryon_local_extras", "") or ""
        self.kinds = BASIC_KINDS | ({k.strip() for k in extras.split(",")} & EXTRAS)
        # for the progress bar: measured on the RTX 2050, ~5 s a step + ~10 s of pose /
        # parsing / DensePose (10 steps: 48-68 s)
        self.seconds_per_garment = 5 * self.steps + 10
        self.last_space = None             # same attributes as SpaceTryOn (the CLI prints them)
        self.last_skipped = []

    @staticmethod
    def _png(img):
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="PNG")
        return buf.getvalue()

    def health(self):
        """The service's /health answer ({"loaded": true} once the models are in memory)."""
        import httpx                        # imported here: only needed when used
        try:
            r = httpx.get(f"{self.url}/health", timeout=10)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError as e:
            raise TryOnBusy(f"local try-on service not reachable at {self.url}: {e}") from e

    def dress(self, person, garment, kind, description=""):
        import httpx
        try:
            r = httpx.post(
                f"{self.url}/generate",
                files={"person_image": ("person.png", self._png(person), "image/png"),
                       "garment_image": ("garment.png", self._png(garment), "image/png")},
                data={"description": description or "a garment", "category": kind,
                      "steps": self.steps},
                timeout=self.timeout)
        except httpx.HTTPError as e:        # service not running, PC asleep, too slow
            raise TryOnBusy(f"local try-on service at {self.url}: {type(e).__name__} {e}") from e
        if r.status_code != 200:
            try:
                detail = r.json().get("detail", r.text)
            except ValueError:
                detail = r.text
            raise TryOnBusy(f"local try-on service answered {r.status_code}: {str(detail)[:300]}")
        try:
            img = Image.open(io.BytesIO(r.content))
            img.load()
        except Exception as e:
            raise TryOnBusy("local try-on service did not return a picture") from e
        self.last_space, self.last_skipped = "local", []
        return img.convert("RGB")


def make_tryon(settings):

    if settings.tryon_engine == "off":
        return None

    if settings.tryon_engine == "space":
        return SpaceTryOn(settings)

    if settings.tryon_engine == "local":
        return LocalTryOn(settings)

    raise ValueError(
        f"Unknown TRYON_ENGINE='{settings.tryon_engine}'"
    )


def plan(docs, kinds=BASIC_KINDS):
    """Split wardrobe documents into (garments in dressing order, skipped ones).
    Skipped = [{"id", "reason"}]: something the engine can't put on (`kinds`: what it can)."""
    garments = [d for d in docs if kind_of(d) in kinds]
    garments.sort(key=lambda d: ORDER.index(d["category"]))
    skipped = [{"id": str(d["_id"]), "reason": "unsupported"} for d in docs if kind_of(d) not in kinds]
    return garments, skipped


# ------------------------------------------------------------------ Space adapters
# Each one sends (person, garment, kind) to one Space's API, using the inputs
# shown on that Space's "Use via API" page, and returns what the Space answers.
# `files` holds the paths of person.png, garment.png and an empty mask.png;
# `description` is a few words such as "grey hoodie" (see describe()).

def catvton(client, files, kind, settings, description):
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


def idm_vton(client, files, kind, settings, description):
    """yisol/IDM-VTON: its automatic mask (is_checked) only covers the upper body."""
    from gradio_client import handle_file
    return client.submit(
        {"background": handle_file(files["person"]), "layers": [], "composite": None},
        handle_file(files["garment"]),
        description or "a garment",   # garment_des: guides the shape (a hood, the length)
        True,                     # is_checked: make the mask automatically
        False,                    # is_checked_crop: the photo is not cropped
        settings.tryon_steps,     # denoise_steps
        42,                       # seed
        api_name="/tryon")


def kolors(client, files, kind, settings, description):
    """Kwai-Kolors/Kolors-Virtual-Try-On: no garment type, mostly trained on tops.
    Answers (picture, seed, message); the picture is empty when it is too busy."""
    from gradio_client import handle_file
    return client.submit(handle_file(files["person"]), handle_file(files["garment"]),
                         42, False,           # seed, randomize_seed
                         api_name="/tryon")


def ootd(client, files, kind, settings, description):
    """levihsu/OOTDiffusion, its "full-body" model: upper body, lower body or
    dress. Answers a gallery (a list of pictures)."""
    from gradio_client import handle_file
    category = {"upper": "Upper-body", "lower": "Lower-body", "overall": "Dress"}[kind]
    return client.submit(handle_file(files["person"]), handle_file(files["garment"]),
                         category,
                         1,                                      # n_samples
                         max(20, min(40, settings.tryon_steps)),  # n_steps (Space allows 20-40)
                         2.0,                                    # image_scale (Space default)
                         42,                                     # seed
                         api_name="/process_dc")


# adapter name -> (function, the kinds of garment it can dress)
ADAPTERS = {
    "catvton": (catvton, {"upper", "lower", "overall"}),
    "idm": (idm_vton, {"upper"}),
    "kolors": (kolors, {"upper", "overall"}),
    "ootd": (ootd, {"upper", "lower", "overall"}),
}


def describe(doc):
    """A few words about a wardrobe item for the models that read text, e.g. "grey hoodie"
    or "red checked scarf" (colour + pattern unless solid + sub_category, or the category
    when it is unknown). The pattern helps: "red plaid scarf" kept the plaid (2026-11-02)."""
    pattern = doc.get("pattern") or ""
    words = [doc.get("colour", ""), "" if pattern == "solid" else pattern,
             doc.get("sub_category") or doc.get("category", "")]
    return " ".join(w for w in words if w)


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
    """The Space's answer -> the path of the picture it made (or None).
    Answers can be a path, several outputs (the picture first), a gallery
    ([{"image": ..., "caption": ...}]) or a file dict ({"path": ...})."""
    while isinstance(out, (list, tuple, dict)):
        if isinstance(out, dict):
            out = out.get("path") or out.get("image")
        else:
            out = out[0] if out else None
    return out


class SpaceTryOn:
    private = False                        # the photo is sent to a Hugging Face Space
    kinds = BASIC_KINDS
    seconds_per_garment = 45               # ~20-60 s on a free shared GPU

    def __init__(self, settings, make_client=None):
        self.settings = settings
        self.spaces = parse_spaces(settings.tryon_spaces)
        self._make_client = make_client or self._gradio_client
        self._clients = {}
        self.last_space = None             # which Space made the last picture
        self.last_skipped = []             # and why the Spaces before it were skipped

    def _gradio_client(self, space):
        from gradio_client import Client   # imported here: only needed when used
        return Client(space, token=self.settings.hf_token or None, verbose=False)

    def dress(self, person, garment, kind, description=""):
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
                    job = call(self._clients[space], files, kind, self.settings, description)
                    path = picture_from(job.result(timeout=self.settings.tryon_timeout))
                    if not path:
                        raise RuntimeError("no picture in the answer (too busy?)")
                    img = Image.open(path)
                    img.load()
                except Exception as e:             # broken, asleep, quota, timeout, API changed
                    self._clients.pop(space, None)  # reconnect next time
                    reasons.append(f"{space}: {str(e).splitlines()[0] if str(e) else type(e).__name__}")
                    continue
                self.last_space, self.last_skipped = space, reasons
                return img.convert("RGB")
        raise TryOnBusy("No try-on Space worked. " + " | ".join(reasons))


def check(settings):
    """Print the state of every Space in TRYON_SPACES (RUNNING, SLEEPING, RUNTIME_ERROR...),
    or, with TRYON_ENGINE=local, of the local service."""
    if settings.tryon_engine == "local":
        engine = LocalTryOn(settings)
        print(f"{engine.url}  ->  {engine.health()}")
        return
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
    engine = make_tryon(settings)
    if engine is None:
        sys.exit("TRYON_ENGINE=off: nothing to run")
    result = engine.dress(Image.open(person_path).convert("RGB"),
                          Image.open(garment_path).convert("RGB"), kind)
    result.save("tryon_result.jpg")
    print(f"saved tryon_result.jpg {result.size}, made by {engine.last_space}")
    for reason in engine.last_skipped:
        print("  skipped", reason)