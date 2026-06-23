from __future__ import annotations

from pathlib import Path
import csv
import io
import re
import xml.etree.ElementTree as ET
from typing import Iterable

from .models import Article, clean_text, main_authors, normalize_doi, normalize_pmcid, normalize_pmid

ALIASES = {
    "id": {"id", "id_interno", "codigo", "código", "article_id"},
    "authors": {"autores", "authors", "author"},
    "authors_main": {"autores principais", "authors_main", "autores_principais"},
    "first_author": {"primeiro_autor_grupo", "primeiro_autor", "first_author", "first author"},
    "short_name": {"nome_curto", "nome curto", "abreviatura", "study_name", "acronimo", "acrônimo"},
    "year": {"ano", "year"},
    "title": {"titulo", "título", "title"},
    "journal": {"periodico", "periódico", "journal", "source"},
    "doi": {"doi"},
    "pmid": {"pmid"},
    "pmcid": {"pmcid"},
    "abstract": {"abstract", "resumo"},
}


def canonical_header(value: str) -> str:
    key = clean_text(value).lower()
    for field, aliases in ALIASES.items():
        if key in aliases:
            return field
    return ""


def read_text(path: str | Path) -> str:
    raw = Path(path).read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def detect_format(text: str, filename: str = "") -> str:
    suffix = Path(filename).suffix.lower()
    sample = text[:8000]
    if suffix in {".nbib"} or re.search(r"(?m)^PMID-\s*\d+", sample):
        return "medline"
    if suffix == ".xml" or sample.lstrip().startswith("<?xml") or "<article_registry" in sample:
        return "xml"
    if suffix in {".csv", ".tsv"}:
        return "table"
    if re.search(r"(?m)^\s*\d+[\.:]\s+", sample):
        if re.search(r"(?m)^(?:IMPORTANCE|BACKGROUND|OBJECTIVE|PURPOSE|AIM|INTRODUCTION):", sample):
            return "pubmed_abstract"
        return "pubmed_summary"
    lines = [line.strip() for line in sample.splitlines() if line.strip()]
    if lines and all(re.fullmatch(r"\d{5,10}", line) for line in lines[: min(20, len(lines))]):
        return "pmid_list"
    if lines and all(re.search(r"10\.\d{4,9}/\S+", line, re.I) for line in lines[: min(20, len(lines))]):
        return "doi_list"
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        first = next(csv.reader(io.StringIO(sample), dialect))
        if sum(bool(canonical_header(cell)) for cell in first) >= 2:
            return "table"
    except (csv.Error, StopIteration):
        pass
    return "unknown"


def parse_source(text: str, source_name: str = "colagem", forced_format: str = "auto") -> list[Article]:
    fmt = detect_format(text, source_name) if forced_format == "auto" else forced_format
    parsers = {
        "table": parse_table,
        "medline": parse_medline,
        "pubmed_abstract": parse_pubmed_abstract,
        "pubmed_summary": parse_pubmed_summary,
        "pmid_list": parse_pmid_list,
        "doi_list": parse_doi_list,
        "xml": parse_registry_xml,
    }
    if fmt not in parsers:
        raise ValueError("Formato não reconhecido automaticamente.")
    records = parsers[fmt](text)
    for article in records:
        article.source = source_name
        article.normalize()
        for field in ("authors", "authors_main", "first_author", "short_name", "year", "title", "journal", "doi", "pmid", "pmcid", "abstract"):
            if getattr(article, field):
                article.field_sources.setdefault(field, source_name)
        if article.abstract:
            article.abstract_status = "Sim — arquivo importado"
            article.abstract_source = source_name
    return records


def parse_files(paths: Iterable[str | Path]) -> list[Article]:
    records: list[Article] = []
    for path in paths:
        path = Path(path)
        records.extend(parse_source(read_text(path), path.name, "auto"))
    return records


def parse_table(text: str) -> list[Article]:
    sample = text[:10000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel_tab if "\t" in sample else csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        return []
    mapping = {header: canonical_header(header) for header in reader.fieldnames}
    articles: list[Article] = []
    for row in reader:
        data: dict[str, str] = {}
        for original, value in row.items():
            field = mapping.get(original or "", "")
            if field and value is not None:
                data[field] = value
        if not any(clean_text(v) for v in data.values()):
            continue
        article = Article(**{k: v for k, v in data.items() if k in Article.__dataclass_fields__})
        articles.append(article)
    return articles


def parse_medline(text: str) -> list[Article]:
    blocks = re.split(r"\n(?=PMID-\s*\d+)", text.strip())
    articles: list[Article] = []
    for block in blocks:
        fields: dict[str, list[str]] = {}
        current = ""
        for line in block.splitlines():
            match = re.match(r"^([A-Z0-9]{2,4})\s*-\s?(.*)$", line)
            if match:
                current = match.group(1)
                fields.setdefault(current, []).append(match.group(2).strip())
            elif current and re.match(r"^\s{4,}", line):
                fields[current][-1] += " " + line.strip()
        pmid = first(fields, "PMID")
        title = first(fields, "TI")
        abstract = " ".join(fields.get("AB", [])).strip()
        authors = "; ".join(fields.get("FAU", []) or fields.get("AU", []))
        group = first(fields, "CN")
        date = first(fields, "DP")
        year_match = re.search(r"\b(19|20)\d{2}\b", date)
        doi = ""
        for value in fields.get("LID", []) + fields.get("AID", []):
            if "[doi]" in value.lower() or value.lower().startswith("10."):
                doi = normalize_doi(value)
                break
        pmcid = ""
        for value in fields.get("PMC", []) + fields.get("PMCR", []):
            pmcid = normalize_pmcid(value)
            if pmcid:
                break
        article = Article(
            authors=authors or group,
            first_author=group or (fields.get("AU", [""])[0] if fields.get("AU") else ""),
            authors_main=group or main_authors(authors),
            year=year_match.group(0) if year_match else "",
            title=title,
            journal=first(fields, "JT") or first(fields, "TA"),
            doi=doi,
            pmid=pmid,
            pmcid=pmcid,
            abstract=abstract,
            abstract_status="Sim — arquivo importado" if abstract else "Não",
        )
        if any((article.pmid, article.doi, article.title)):
            articles.append(article)
    return articles


def first(fields: dict[str, list[str]], key: str) -> str:
    values = fields.get(key, [])
    return values[0] if values else ""


def split_numbered_blocks(text: str) -> list[str]:
    pattern = r"(?m)(?=^\s*(?:\d{1,3}:\s+|\d{1,3}\.\s+[A-Z][^\n]{0,80}\.\s+(?:19|20)\d{2}))"
    parts = re.split(pattern, text.strip())
    return [part.strip() for part in parts if part.strip()]


def identifiers(block: str) -> tuple[str, str, str]:
    doi_match = re.search(r"\bdoi\s*:\s*(10\.\d{4,9}/[^\s;]+)", block, re.I)
    if not doi_match:
        doi_match = re.search(r"\b(10\.\d{4,9}/[^\s;]+)", block, re.I)
    pmid_match = re.search(r"\bPMID\s*:\s*(\d+)", block, re.I)
    pmcid_match = re.search(r"\bPMCID\s*:\s*(PMC\d+)", block, re.I)
    return (
        normalize_doi(doi_match.group(1)) if doi_match else "",
        normalize_pmid(pmid_match.group(1)) if pmid_match else "",
        normalize_pmcid(pmcid_match.group(1)) if pmcid_match else "",
    )


def parse_pubmed_abstract(text: str) -> list[Article]:
    articles: list[Article] = []
    for block in split_numbered_blocks(text):
        doi, pmid, pmcid = identifiers(block)
        paragraphs = [re.sub(r"\s*\n\s*", " ", p).strip() for p in re.split(r"\n\s*\n", block) if p.strip()]
        citation = re.sub(r"^\s*\d+[\.:]\s+", "", paragraphs[0]) if paragraphs else ""
        title = paragraphs[1] if len(paragraphs) > 1 else ""
        authors = paragraphs[2] if len(paragraphs) > 2 and not paragraphs[2].lower().startswith("author information") else ""
        journal = citation.split(".", 1)[0].strip()
        year_match = re.search(r"\b(19|20)\d{2}\b", citation)
        abstract = extract_labeled_abstract(block)
        articles.append(
            Article(
                authors=authors,
                authors_main=main_authors(authors),
                year=year_match.group(0) if year_match else "",
                title=title.rstrip("."),
                journal=journal,
                doi=doi,
                pmid=pmid,
                pmcid=pmcid,
                abstract=abstract,
                abstract_status="Sim — arquivo importado" if abstract else "Não",
            )
        )
    return [a for a in articles if any((a.title, a.doi, a.pmid))]


def extract_labeled_abstract(block: str) -> str:
    start = re.search(
        r"(?m)^(IMPORTANCE|BACKGROUND|OBJECTIVE|OBJECTIVES|PURPOSE|AIM|AIMS|INTRODUCTION|CONTEXT|RATIONALE):\s*",
        block,
    )
    if not start:
        return ""
    body = block[start.start():]
    stop = re.search(
        r"(?m)^\s*(Copyright|©|PMID:|PMCID:|DOI:|Publication types:|MeSH terms:|Substances:|Grant support:|Conflict of interest)",
        body,
        re.I,
    )
    if stop:
        body = body[: stop.start()]
    return re.sub(r"\s+", " ", body).strip()


def parse_pubmed_summary(text: str) -> list[Article]:
    articles: list[Article] = []
    for block in split_numbered_blocks(text):
        plain = re.sub(r"^\s*\d+[\.:]\s+", "", block)
        plain = re.sub(r"\s+", " ", plain).strip()
        doi, pmid, pmcid = identifiers(plain)
        year_match = re.search(r"\b(19|20)\d{2}\b", plain)
        # O título costuma estar entre a lista de autores e o nome abreviado do periódico.
        title = ""
        authors = ""
        sentences = [s.strip() for s in re.split(r"(?<=\.)\s+", plain) if s.strip()]
        if sentences:
            authors = sentences[0]
        for sentence in sentences[1:]:
            if len(sentence) > 35 and not re.search(r"\b(?:doi|PMID|PMCID)\b", sentence, re.I):
                title = sentence
                break
        articles.append(
            Article(
                authors=authors,
                authors_main=main_authors(authors),
                year=year_match.group(0) if year_match else "",
                title=title.rstrip("."),
                doi=doi,
                pmid=pmid,
                pmcid=pmcid,
            )
        )
    return [a for a in articles if any((a.title, a.doi, a.pmid))]


def parse_pmid_list(text: str) -> list[Article]:
    return [Article(pmid=normalize_pmid(line)) for line in text.splitlines() if normalize_pmid(line)]


def parse_doi_list(text: str) -> list[Article]:
    articles = []
    for line in text.splitlines():
        match = re.search(r"10\.\d{4,9}/\S+", line, re.I)
        if match:
            articles.append(Article(doi=normalize_doi(match.group(0))))
    return articles


def parse_registry_xml(text: str) -> list[Article]:
    root = ET.fromstring(text)
    articles: list[Article] = []
    for node in root.findall(".//article"):
        identifiers_node = node.find("identifiers")
        access = node.find("access")
        article = Article(
            id=node.get("id", ""),
            authors=text_of(node, "authors"),
            authors_main=text_of(node, "authors_main") or text_of(node, "authors"),
            short_name=text_of(node, "short_name"),
            year=text_of(node, "year"),
            title=text_of(node, "title"),
            journal=text_of(node, "journal"),
            doi=text_of(identifiers_node, "doi"),
            pmid=text_of(identifiers_node, "pmid"),
            pmcid=text_of(identifiers_node, "pmcid"),
            openalex_id=text_of(identifiers_node, "openalex_id"),
            abstract=text_of(node, "abstract"),
            abstract_status=text_of(node, "abstract_status") or "Não",
            landing_url=text_of(access, "landing_url"),
            pdf_url=text_of(access, "pdf_url"),
            xml_url=text_of(access, "fulltext_xml_url"),
            json_url=text_of(access, "fulltext_json_url"),
            status=text_of(access, "status") or "Importado",
        )
        articles.append(article)
    return articles


def text_of(node: ET.Element | None, tag: str) -> str:
    if node is None:
        return ""
    child = node.find(tag)
    return clean_text(child.text if child is not None else "")
