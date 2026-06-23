from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import re
import tempfile
import xml.etree.ElementTree as ET
import zipfile

import requests

from .database import Database
from .exporters import write_html, write_txt, write_xlsx
from .models import Article, now_iso


class DownloadError(RuntimeError):
    pass


BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 RastreadorArtigos/2.0",
    "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.4",
}


def safe_name(value: str, limit: int = 72) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", (value or "").strip())
    return value.strip("_")[:limit] or "artigo"


def article_base_name(article: Article) -> str:
    label = article.short_name or article.authors_main or article.first_author or "Artigo"
    year = f"_{safe_name(article.year, 8)}" if article.year else ""
    return f"{safe_name(article.id, 16)}_{safe_name(label)}{year}"


def check_pdf_url(url: str, timeout: float = 35) -> tuple[str, str, str]:
    """Return (status, message, final_url) without downloading the whole file."""
    if not url:
        return "Não localizado", "Nenhuma URL de PDF foi localizada.", ""
    headers = dict(BROWSER_HEADERS)
    headers["Range"] = "bytes=0-4095"
    try:
        with requests.get(url, timeout=timeout, allow_redirects=True, headers=headers, stream=True) as response:
            final_url = response.url or url
            code = response.status_code
            if code in {401, 403}:
                return "Acesso bloqueado", f"HTTP {code}; o servidor exige autorização ou bloqueou a consulta.", final_url
            if code == 429 or code >= 500:
                return "Erro temporário", f"HTTP {code}; tente novamente mais tarde.", final_url
            if code not in {200, 206}:
                return "Link inválido", f"HTTP {code}; o recurso não pôde ser validado.", final_url
            chunk = b""
            for part in response.iter_content(chunk_size=4096):
                if part:
                    chunk += part
                    if len(chunk) >= 4096:
                        break
            content_type = (response.headers.get("Content-Type") or "").lower()
            if b"%PDF-" in chunk[:1024]:
                return "Download confirmado", "PDF validado pela assinatura do arquivo.", final_url
            if "application/pdf" in content_type and chunk:
                return "Download confirmado", "PDF validado pelo tipo de conteúdo do servidor.", final_url
            if "text/html" in content_type or chunk.lstrip().startswith((b"<!DOCTYPE", b"<html", b"<HTML")):
                return "Link inválido", "A URL retornou uma página HTML, não um PDF.", final_url
            return "Link inválido", "O recurso não apresentou assinatura de PDF.", final_url
    except requests.Timeout:
        return "Erro temporário", "Tempo limite excedido durante a verificação.", url
    except requests.RequestException as exc:
        return "Erro temporário", f"Falha de rede: {exc}", url


def get_bytes(url: str, timeout: float = 60) -> tuple[bytes, str, str]:
    response = requests.get(url, timeout=timeout, allow_redirects=True, headers=BROWSER_HEADERS)
    if response.status_code != 200:
        raise DownloadError(f"HTTP {response.status_code}")
    return response.content, (response.headers.get("Content-Type") or "").lower(), response.url or url


def save_validated(url: str, target: Path, kind: str, timeout: float = 60) -> Path:
    content, content_type, _ = get_bytes(url, timeout)
    if kind == "pdf":
        if b"%PDF-" not in content[:1024] and "application/pdf" not in content_type:
            raise DownloadError("O recurso retornado não é um PDF válido.")
    elif kind == "json":
        try:
            json.loads(content.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DownloadError("O recurso retornado não é JSON válido.") from exc
    elif kind == "xml":
        try:
            ET.fromstring(content)
        except ET.ParseError as exc:
            raise DownloadError("O recurso retornado não é XML válido.") from exc
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


def verify_article_pdf(article: Article, timeout: float = 35) -> Article:
    status, message, final_url = check_pdf_url(article.pdf_url, timeout)
    article.pdf_check_status = status
    article.pdf_check_message = message
    article.pdf_checked_at = now_iso()
    if final_url and status == "Download confirmado":
        article.pdf_url = final_url
    if status == "Download confirmado":
        article.status = "PDF com download confirmado"
    elif article.pdf_url:
        article.status = status
    elif article.json_url or article.xml_url:
        article.status = "Texto estruturado disponível; PDF não localizado"
    else:
        article.status = "Não foi possível rastrear texto integral aberto"
    return article


def _download_pdf(article: Article, pdf_dir: Path, database: Database, timeout: float) -> Path | None:
    if article.pdf_check_status != "Download confirmado" or not article.pdf_url:
        return None
    target = pdf_dir / f"{article_base_name(article)}.pdf"
    try:
        save_validated(article.pdf_url, target, "pdf", timeout)
        article.pdf_downloaded = 1
        article.downloaded = 1
        article.pdf_download_error = ""
        article.status = "PDF baixado"
        database.save(article)
        database.log(article.id, "Download", f"PDF obtido: {target.name}")
        return target
    except Exception as exc:
        article.pdf_downloaded = 0
        article.downloaded = 0
        article.pdf_download_error = str(exc)
        article.status = "Erro no download do PDF"
        database.save(article)
        database.log(article.id, "Download", f"Falha no PDF: {exc}", "ERROR")
        return None


def download_pdfs_folder(
    destination: str | Path,
    articles: list[Article],
    database: Database,
    include_abstracts: bool,
    timeout: float = 60,
    progress=None,
    cancelled=None,
) -> Path:
    root = Path(destination)
    pdf_dir = root / "PDFs"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    eligible = [a for a in articles if a.pdf_check_status == "Download confirmado" and a.pdf_url]
    total = max(1, len(eligible))
    for index, article in enumerate(eligible, 1):
        if cancelled and cancelled():
            raise DownloadError("Operação cancelada.")
        _download_pdf(article, pdf_dir, database, timeout)
        if progress:
            progress(index, total, article.id)
    write_txt(root / "Relatorio_Rastreamento.txt", database.list_articles(), include_abstracts)
    return root


def create_package(
    zip_path: str | Path,
    articles: list[Article],
    database: Database,
    include_abstracts: bool,
    download_json: bool = True,
    download_xml: bool = False,
    timeout: float = 60,
    progress=None,
    cancelled=None,
) -> Path:
    zip_path = Path(zip_path)
    with tempfile.TemporaryDirectory(prefix="rastreador_artigos_") as temporary:
        root = Path(temporary) / "Rastreamento_Artigos"
        pdf_dir = root / "PDFs"
        structured_dir = root / "Textos_estruturados"
        pdf_dir.mkdir(parents=True, exist_ok=True)

        eligible = [a for a in articles if a.pdf_check_status == "Download confirmado" and a.pdf_url]
        downloaded_ids: set[str] = set()
        total = max(1, len(eligible))
        for index, article in enumerate(eligible, 1):
            if cancelled and cancelled():
                raise DownloadError("Operação cancelada.")
            pdf_path = _download_pdf(article, pdf_dir, database, timeout)
            if pdf_path:
                downloaded_ids.add(article.id)
                resources = []
                base = article_base_name(article)
                if download_json and article.json_url:
                    resources.append((article.json_url, structured_dir / f"{base}_bioc.json", "json"))
                if download_xml and article.xml_url:
                    resources.append((article.xml_url, structured_dir / f"{base}_bioc.xml", "xml"))
                for url, target, kind in resources:
                    try:
                        save_validated(url, target, kind, timeout)
                        database.log(article.id, "Download", f"{kind.upper()} obtido: {target.name}")
                    except Exception as exc:
                        database.log(article.id, "Download", f"Falha em {kind.upper()}: {exc}", "ERROR")
            if progress:
                progress(index, total, article.id)

        current = database.list_articles()
        write_xlsx(root / "status_artigos.xlsx", current, include_abstracts=False)
        write_html(root / "status_artigos.html", current)
        write_txt(root / "Relatorio_Rastreamento.txt", current, include_abstracts)

        if structured_dir.exists() and not any(structured_dir.iterdir()):
            structured_dir.rmdir()

        zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file in root.rglob("*"):
                if file.is_file():
                    archive.write(file, file.relative_to(root))
    return zip_path
