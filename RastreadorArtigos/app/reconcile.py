from __future__ import annotations

from difflib import SequenceMatcher

from .models import Article, clean_text, normalize_title


CORE_FIELDS = (
    "authors", "authors_main", "first_author", "short_name", "year", "title", "journal",
    "doi", "pmid", "pmcid", "openalex_id", "landing_url", "pdf_url", "xml_url", "json_url",
    "license", "source",
)


def merge_articles(base: Article, incoming: Article, incoming_source: str = "") -> Article:
    source = incoming_source or incoming.source or "importação"
    for field in CORE_FIELDS:
        new_value = clean_text(getattr(incoming, field))
        if not new_value:
            continue
        old_value = clean_text(getattr(base, field))
        if field in base.manual_fields:
            if old_value and old_value != new_value:
                base.add_conflict(field, new_value)
            continue
        if not old_value:
            setattr(base, field, new_value)
            base.field_sources[field] = source
        elif old_value != new_value:
            if field in {"doi", "pmid", "pmcid"}:
                base.add_conflict(field, new_value)
            elif field == "title" and normalize_title(old_value) != normalize_title(new_value):
                ratio = SequenceMatcher(None, normalize_title(old_value), normalize_title(new_value)).ratio()
                if ratio < 0.92:
                    base.add_conflict(field, new_value)
            elif len(new_value) > len(old_value) and field in {"authors", "journal"}:
                setattr(base, field, new_value)
                base.field_sources[field] = source

    merge_abstract(base, incoming, source)
    if incoming.oa_status not in {"", "Não consultado"}:
        base.oa_status = incoming.oa_status
    if incoming.status not in {"", "Importado"}:
        base.status = incoming.status
    base.downloaded = max(base.downloaded, incoming.downloaded)
    return base.normalize()


def merge_abstract(base: Article, incoming: Article, source: str) -> None:
    new = str(incoming.abstract or "").strip()
    if not new:
        return
    old = str(base.abstract or "").strip()
    if not old:
        base.abstract = new
        base.abstract_status = incoming.abstract_status if incoming.abstract_status != "Não" else "Sim — arquivo importado"
        base.abstract_source = source
        base.field_sources["abstract"] = source
        return
    if normalize_abstract(old) == normalize_abstract(new):
        return
    if normalize_abstract(old) in normalize_abstract(new):
        base.abstract = new
        base.abstract_status = incoming.abstract_status if incoming.abstract_status != "Não" else "Sim — arquivo importado"
        base.abstract_source = source
        base.field_sources["abstract"] = source
        return
    if normalize_abstract(new) in normalize_abstract(old):
        return
    base.abstract_status = "Conflito entre fontes"
    base.add_conflict("abstract", new)


def normalize_abstract(text: str) -> str:
    return " ".join(clean_text(text).lower().split())


def probable_match(a: Article, b: Article) -> float:
    ta = normalize_title(a.title)
    tb = normalize_title(b.title)
    if not ta or not tb:
        return 0.0
    score = SequenceMatcher(None, ta, tb).ratio()
    if a.year and b.year and a.year != b.year:
        score -= 0.15
    if a.first_author and b.first_author:
        aa = a.first_author.split()[0].lower()
        bb = b.first_author.split()[0].lower()
        if aa == bb:
            score += 0.05
    return max(0.0, min(1.0, score))
