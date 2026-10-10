"""Team vocabulary the app needs that is not translated text (that lives in
frontend/src/i18n/vocab.ts): which pieces are men's, women's or unisex."""

from fastapi import APIRouter, Request

from .. import ml  # noqa: F401  (puts src/ on the import path)
import genders

router = APIRouter(tags=["vocab"])


@router.get("/vocab/sub-category-gender")
def sub_category_gender(request: Request):
    """{sub_category: men / women / unisex} from mappings/gender_sub_categories.csv
    (the label pickers show the user's pieces first)."""
    return genders.load_table(request.app.state.settings.mappings_dir)
