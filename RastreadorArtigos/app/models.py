from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
import re
import unicodedata


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def clean_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).replace("\ufeff", " ").replace("\u200b", " ")
    return re.sub(r"\s+", " ", text).strip()


def normalize_doi(value: object) -> str:
    text = clean_text(value)
    text = re.sub(r"^(?:doi\s*:\s*|https?://(?:dx\.)?doi\.org/)", "", text, flags=re.I)
    text = re.sub(r"\s*\[doi\]\s*$", "", text, flags=re.I)
    return text.rstrip(" .;,)").lower()


def normalize_pmid(value: object) -> str:
    match = re.search(r"\b(\d{5,10})\b", clean_text(value))
    return match.group(1) if match else ""


def normalize_pmcid(value: object) -> str:
    match = re.search(r"\bPMC\s*(\d+)\b", clean_text(value), flags=re.I)
    return f"PMC{match.group(1)}" if match else ""


def normalize_title(value: object) -> str:
    text = unicodedata.normalize("NFKD", clean_text(value)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def main_authors(authors: str, group: str = "") -> str:
    group = clean_text(group)
    authors = clean_text(authors)
    if group and ("group" in group.lower() or "trial" in group.lower() or "collabor" in group.lower()):
        return group
    first = re.split(r";|\band\b", authors, maxsplit=1, flags=re.I)[0].strip(" ,") if authors else group
    return f"{first} et al." if first else ""


def suggest_short_name(title: str, first_author: str, year: str) -> str:
    title = clean_text(title)
    candidates = re.findall(r"\b[A-Z][A-Z0-9-]{2,}\b", title)
    ignored = {"PDF", "PMC", "PMID", "NPWT", "INPWT", "CINPWT", "SSI", "RCT"}
    for candidate in candidates:
        if candidate not in ignored and len(candidate) <= 24:
            return candidate
    author = clean_text(first_author).replace(" et al.", "")
    surname = author.split()[0] if author else "Estudo"
    return clean_text(f"{surname} {year}")


@dataclass
class Article:
    id: str = ""
    authors: str = ""
    authors_main: str = ""
    first_author: str = ""
    short_name: str = ""
    year: str = ""
    title: str = ""
    journal: str = ""
    doi: str = ""
    pmid: str = ""
    pmcid: str = ""
    openalex_id: str = ""
    abstract: str = ""
    abstract_status: str = "Não"
    abstract_source: str = ""
    oa_status: str = "Não consultado"
    landing_url: str = ""
    pdf_url: str = ""
    xml_url: str = ""
    json_url: str = ""
    license: str = ""
    source: str = ""
    status: str = "Importado"
    downloaded: int = 0
    pdf_check_status: str = "Não verificado"
    pdf_check_message: str = ""
    pdf_checked_at: str = ""
    pdf_downloaded: int = 0
    pdf_download_error: str = ""
    field_sources: dict[str, str] = field(default_factory=dict)
    manual_fields: set[str] = field(default_factory=set)
    conflicts: dict[str, list[str]] = field(default_factory=dict)
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def normalize(self) -> "Article":
        self.id = clean_text(self.id).upper()
        self.authors = clean_text(self.authors)
        self.first_author = clean_text(self.first_author)
        self.year = clean_text(self.year)
        self.title = clean_text(self.title)
        self.journal = clean_text(self.journal)
        self.doi = normalize_doi(self.doi)
        self.pmid = normalize_pmid(self.pmid)
        self.pmcid = normalize_pmcid(self.pmcid)
        self.openalex_id = clean_text(self.openalex_id)
        self.abstract = re.sub(r"[ \t]+", " ", str(self.abstract or "")).strip()
        if self.abstract and self.abstract_status == "Não":
            self.abstract_status = "Sim — arquivo importado"
        if not self.authors_main:
            self.authors_main = main_authors(self.authors, self.first_author)
        if not self.short_name:
            self.short_name = suggest_short_name(self.title, self.authors_main or self.first_author, self.year)
        self.updated_at = now_iso()
        return self

    @property
    def structured_url(self) -> str:
        return self.json_url or self.xml_url

    @property
    def main_link(self) -> str:
        if self.pdf_check_status == "Download confirmado" and self.pdf_url:
            return self.pdf_url
        if self.landing_url:
            return self.landing_url
        if self.pmcid:
            return f"https://pmc.ncbi.nlm.nih.gov/articles/{self.pmcid}/"
        if self.doi:
            return f"https://doi.org/{self.doi}"
        if self.pmid:
            return f"https://pubmed.ncbi.nlm.nih.gov/{self.pmid}/"
        return ""

    @property
    def pdf_display(self) -> str:
        if not self.pdf_url:
            return "Não localizado"
        return self.pdf_check_status or "Não verificado"

    @property
    def structured_display(self) -> str:
        items = []
        if self.json_url:
            items.append("JSON")
        if self.xml_url:
            items.append("XML")
        return "+".join(items) if items else "Não"

    @property
    def color_state(self) -> str:
        if self.conflicts or self.abstract_status == "Conflito entre fontes":
            return "conflict"
        if self.status.startswith("Consultando") or self.status.startswith("Verificando") or self.status.startswith("Baixando"):
            return "working"
        if self.status.startswith("Erro") or self.pdf_check_status in {"Link inválido", "Erro temporário"}:
            return "error"
        if self.pdf_check_status == "Download confirmado":
            return "available"
        if self.pdf_url or self.json_url or self.xml_url:
            return "partial"
        status_lower = self.status.lower()
        if (
            self.oa_status in {"Não localizado", "Fechado", "Requer acesso institucional/manual"}
            or "não foi possível" in status_lower
            or "requer acesso" in status_lower
        ):
            return "missing"
        return "pending"

    def add_conflict(self, field_name: str, value: str) -> None:
        value = clean_text(value)
        if not value:
            return
        self.conflicts.setdefault(field_name, [])
        if value not in self.conflicts[field_name]:
            self.conflicts[field_name].append(value)
        self.status = "Conflito de dados"

    def to_db(self) -> dict[str, object]:
        data = asdict(self)
        data["field_sources"] = json.dumps(self.field_sources, ensure_ascii=False)
        data["manual_fields"] = json.dumps(sorted(self.manual_fields), ensure_ascii=False)
        data["conflicts"] = json.dumps(self.conflicts, ensure_ascii=False)
        return data

    @classmethod
    def from_db(cls, row: dict[str, object]) -> "Article":
        data = dict(row)
        data["field_sources"] = json.loads(data.get("field_sources") or "{}")
        data["manual_fields"] = set(json.loads(data.get("manual_fields") or "[]"))
        data["conflicts"] = json.loads(data.get("conflicts") or "{}")
        valid = {field.name for field in cls.__dataclass_fields__.values()}
        return cls(**{key: value for key, value in data.items() if key in valid})
