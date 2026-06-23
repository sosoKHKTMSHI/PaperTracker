from __future__ import annotations

import json
import time
import urllib.parse
import xml.etree.ElementTree as ET

import requests

from .models import Article, clean_text, normalize_doi, normalize_pmcid, normalize_pmid
from .reconcile import merge_articles


class ApiError(RuntimeError):
    pass


class ApiClient:
    def __init__(self, config: dict):
        self.config = config
        self.email = config.get("email", "")
        self.tool_name = config.get("tool_name", "RastreadorArtigos")
        self.openalex_key = config.get("openalex_api_key", "")
        self.timeout = float(config.get("timeout_seconds", 25))
        self.max_retries = int(config.get("max_retries", 3))
        self.interval = float(config.get("request_interval_seconds", 0.4))
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": f"{self.tool_name}/1.0 ({self.email})",
            "Accept": "application/json, application/xml, text/xml, */*",
        })

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                response = self.session.request(method, url, timeout=self.timeout, **kwargs)
                if response.status_code == 429 or response.status_code >= 500:
                    raise ApiError(f"HTTP {response.status_code}")
                return response
            except (requests.RequestException, ApiError) as exc:
                last_error = exc
                if attempt + 1 < self.max_retries:
                    time.sleep(min(4.0, (2 ** attempt) * max(self.interval, 0.3)))
        raise ApiError(str(last_error or "Falha de comunicação"))

    def pause(self) -> None:
        if self.interval > 0:
            time.sleep(self.interval)

    def complete_identifiers(self, article: Article) -> Article:
        enriched = Article(id=article.id)
        if article.pmid:
            try:
                enriched = merge_articles(enriched, self.pubmed_metadata(article.pmid), "PubMed")
            except ApiError:
                pass
        if article.doi:
            try:
                enriched = merge_articles(enriched, self.crossref(article.doi), "Crossref")
            except ApiError:
                pass
        if self.openalex_key:
            try:
                enriched = merge_articles(enriched, self.openalex(article), "OpenAlex")
            except ApiError:
                pass
        try:
            enriched = merge_articles(enriched, self.pmc_id_converter(article), "PMC ID Converter")
        except ApiError:
            pass
        effective_pmid = enriched.pmid or article.pmid
        if effective_pmid and not (article.abstract or enriched.abstract):
            try:
                abstract = self.pubmed_abstract(effective_pmid)
                if abstract:
                    enriched.abstract = abstract
                    enriched.abstract_status = "Sim — API"
                    enriched.abstract_source = "BioC PubMed"
            except ApiError:
                pass
        return merge_articles(article, enriched, "APIs")


    def pubmed_metadata(self, pmid: str) -> Article:
        response = self.request(
            "GET",
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
            params={
                "db": "pubmed", "id": pmid, "retmode": "xml",
                "tool": self.tool_name, "email": self.email,
            },
        )
        if not response.ok:
            raise ApiError(f"PubMed HTTP {response.status_code}")
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as exc:
            raise ApiError("Resposta XML inválida do PubMed") from exc
        record = root.find(".//PubmedArticle")
        if record is None:
            return Article(pmid=pmid)
        title_node = record.find(".//ArticleTitle")
        title = "".join(title_node.itertext()).strip() if title_node is not None else ""
        journal_node = record.find(".//Journal/Title")
        journal = "".join(journal_node.itertext()).strip() if journal_node is not None else ""
        year = clean_text(record.findtext(".//JournalIssue/PubDate/Year") or "")
        if not year:
            date_text = clean_text(record.findtext(".//JournalIssue/PubDate/MedlineDate") or "")
            import re
            match = re.search(r"\b(19|20)\d{2}\b", date_text)
            year = match.group(0) if match else ""
        authors = []
        collective = ""
        for author in record.findall(".//AuthorList/Author"):
            group = clean_text(author.findtext("CollectiveName") or "")
            if group:
                collective = collective or group
                authors.append(group)
                continue
            name = clean_text(" ".join(filter(None, [author.findtext("ForeName"), author.findtext("LastName")])))
            if name:
                authors.append(name)
        ids = {}
        for node in record.findall(".//PubmedData/ArticleIdList/ArticleId"):
            ids[(node.get("IdType") or "").lower()] = clean_text(node.text or "")
        abstract_parts = []
        for node in record.findall(".//Abstract/AbstractText"):
            text = "".join(node.itertext()).strip()
            label = clean_text(node.get("Label") or "")
            if text:
                abstract_parts.append(f"{label}: {text}" if label else text)
        abstract = " ".join(abstract_parts)
        return Article(
            authors="; ".join(authors), first_author=collective or (authors[0] if authors else ""),
            year=year, title=title, journal=journal, doi=normalize_doi(ids.get("doi", "")),
            pmid=normalize_pmid(ids.get("pubmed", "") or pmid), pmcid=normalize_pmcid(ids.get("pmc", "")),
            abstract=abstract, abstract_status="Sim — API" if abstract else "Não",
            abstract_source="PubMed" if abstract else "", source="PubMed",
        )

    def crossref(self, doi: str) -> Article:
        response = self.request(
            "GET", f"https://api.crossref.org/works/{urllib.parse.quote(doi, safe='')}",
            params={"mailto": self.email},
        )
        if response.status_code == 404:
            return Article(doi=doi)
        if not response.ok:
            raise ApiError(f"Crossref HTTP {response.status_code}")
        message = response.json().get("message") or {}
        authors = []
        for author in message.get("author") or []:
            name = clean_text(" ".join(filter(None, [author.get("given"), author.get("family")])))
            if name:
                authors.append(name)
        date_parts = ((message.get("published-print") or message.get("published-online") or message.get("issued") or {}).get("date-parts") or [[]])
        year = str(date_parts[0][0]) if date_parts and date_parts[0] else ""
        titles = message.get("title") or []
        journals = message.get("container-title") or []
        return Article(
            authors="; ".join(authors), first_author=authors[0] if authors else "", year=year,
            title=titles[0] if titles else "", journal=journals[0] if journals else "",
            doi=normalize_doi(message.get("DOI") or doi), landing_url=message.get("URL") or "", source="Crossref",
        )

    def openalex(self, article: Article) -> Article:
        external = ""
        if article.doi:
            external = f"https://doi.org/{article.doi}"
        elif article.pmid:
            external = f"pmid:{article.pmid}"
        elif article.pmcid:
            external = f"pmcid:{article.pmcid}"
        if not external:
            return Article(id=article.id)
        url = f"https://api.openalex.org/works/{urllib.parse.quote(external, safe=':/')}"
        params = {"api_key": self.openalex_key} if self.openalex_key else {}
        response = self.request("GET", url, params=params)
        if response.status_code == 404:
            return Article(id=article.id)
        if not response.ok:
            raise ApiError(f"OpenAlex HTTP {response.status_code}")
        data = response.json()
        ids = data.get("ids") or {}
        authors = []
        for item in data.get("authorships") or []:
            name = ((item.get("author") or {}).get("display_name") or "").strip()
            if name:
                authors.append(name)
        location = data.get("best_oa_location") or data.get("primary_location") or {}
        source = location.get("source") or {}
        pdf = location.get("pdf_url") or ""
        landing = location.get("landing_page_url") or ""
        doi = ids.get("doi") or data.get("doi") or ""
        return Article(
            id=article.id,
            authors="; ".join(authors),
            first_author=authors[0] if authors else "",
            year=str(data.get("publication_year") or ""),
            title=data.get("display_name") or data.get("title") or "",
            journal=source.get("display_name") or "",
            doi=normalize_doi(doi),
            pmid=normalize_pmid(ids.get("pmid") or ""),
            pmcid=normalize_pmcid(ids.get("pmcid") or ""),
            openalex_id=clean_text(data.get("id") or ""),
            landing_url=landing,
            pdf_url=pdf,
            oa_status="Aberto" if (data.get("open_access") or {}).get("is_oa") else "Fechado",
            source="OpenAlex",
        )

    def pmc_id_converter(self, article: Article) -> Article:
        identifier = article.pmcid or article.pmid or article.doi
        if not identifier:
            return Article(id=article.id)
        params = {
            "ids": identifier,
            "format": "json",
            "tool": self.tool_name,
            "email": self.email,
        }
        response = self.request("GET", "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/", params=params)
        if not response.ok:
            raise ApiError(f"PMC ID Converter HTTP {response.status_code}")
        records = response.json().get("records") or []
        record = records[0] if records else {}
        return Article(
            id=article.id,
            doi=normalize_doi(record.get("doi") or ""),
            pmid=normalize_pmid(record.get("pmid") or ""),
            pmcid=normalize_pmcid(record.get("pmcid") or ""),
            source="PMC ID Converter",
        )

    def unpaywall(self, article: Article) -> Article:
        if not article.doi:
            return article
        url = f"https://api.unpaywall.org/v2/{urllib.parse.quote(article.doi, safe='')}"
        response = self.request("GET", url, params={"email": self.email})
        if response.status_code == 404:
            article.oa_status = "Não localizado"
            article.status = "Requer acesso institucional/manual"
            return article
        if not response.ok:
            raise ApiError(f"Unpaywall HTTP {response.status_code}")
        data = response.json()
        best = data.get("best_oa_location") or {}
        article.oa_status = "Aberto" if data.get("is_oa") else "Fechado"
        article.landing_url = best.get("url") or best.get("url_for_landing_page") or article.landing_url
        article.pdf_url = best.get("url_for_pdf") or article.pdf_url
        article.license = best.get("license") or article.license
        article.source = "Unpaywall" if best else article.source
        article.status = "Arquivo integral aberto localizado" if article.pdf_url else "Requer acesso institucional/manual"
        return article

    def pmc_resources(self, article: Article) -> Article:
        if not article.pmcid:
            return article
        response = self.request(
            "GET",
            "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi",
            params={"id": article.pmcid},
        )
        if response.ok:
            try:
                root = ET.fromstring(response.content)
                record = root.find(".//record")
                if record is not None:
                    article.license = record.get("license", article.license)
                for link in root.findall(".//link"):
                    href = self.normalize_download_url(link.get("href", ""))
                    fmt = (link.get("format") or "").lower()
                    if fmt == "pdf" and href:
                        article.pdf_url = href
                        article.source = "PMC OA"
            except ET.ParseError:
                pass
        json_url = f"https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_JSON/{article.pmcid}/UNICODE"
        xml_url = f"https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_XML/{article.pmcid}/UNICODE"
        if self.valid_json_endpoint(json_url):
            article.json_url = json_url
            article.source = article.source or "BioC PMC"
        if self.valid_xml_endpoint(xml_url):
            article.xml_url = xml_url
            article.source = article.source or "BioC PMC"
        article.landing_url = article.landing_url or f"https://pmc.ncbi.nlm.nih.gov/articles/{article.pmcid}/"
        if article.pdf_url or article.json_url or article.xml_url:
            article.oa_status = "Aberto"
            article.status = "Arquivo integral aberto localizado"
        elif article.oa_status == "Não consultado":
            article.oa_status = "Não localizado"
            article.status = "Requer acesso institucional/manual"
        return article

    def pubmed_abstract(self, pmid: str) -> str:
        url = f"https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pubmed.cgi/BioC_JSON/{pmid}/UNICODE"
        response = self.request("GET", url)
        if not response.ok:
            raise ApiError(f"BioC PubMed HTTP {response.status_code}")
        data = response.json()
        passages = []
        documents = data if isinstance(data, list) else data.get("documents", [])
        for collection in documents if isinstance(documents, list) else []:
            docs = collection.get("documents", []) if isinstance(collection, dict) else []
            if "passages" in collection:
                docs = [collection]
            for document in docs:
                for passage in document.get("passages", []):
                    info = passage.get("infons") or {}
                    kind = str(info.get("type") or info.get("section_type") or "").lower()
                    text = clean_text(passage.get("text") or "")
                    if text and kind not in {"title", "front"}:
                        passages.append(text)
        return " ".join(dict.fromkeys(passages)).strip()

    def valid_json_endpoint(self, url: str) -> bool:
        try:
            response = self.request("GET", url)
            if not response.ok:
                return False
            json.loads(response.text)
            return bool(response.text.strip())
        except (ApiError, ValueError):
            return False

    def valid_xml_endpoint(self, url: str) -> bool:
        try:
            response = self.request("GET", url)
            if not response.ok:
                return False
            ET.fromstring(response.content)
            return bool(response.content.strip())
        except (ApiError, ET.ParseError):
            return False

    @staticmethod
    def normalize_download_url(url: str) -> str:
        if url.startswith("ftp://ftp.ncbi.nlm.nih.gov/"):
            return url.replace("ftp://ftp.ncbi.nlm.nih.gov/", "https://ftp.ncbi.nlm.nih.gov/", 1)
        return url
