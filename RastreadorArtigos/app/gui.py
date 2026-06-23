from __future__ import annotations

from datetime import datetime
from pathlib import Path
from queue import Empty, Queue
import json
import tempfile
import threading
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .apis import ApiClient
from .database import Database
from .downloader import (
    DownloadError,
    create_package,
    download_pdfs_folder,
    verify_article_pdf,
)
from .exporters import write_html, write_txt
from .importers import parse_files, parse_source
from .models import Article, normalize_title
from .reconcile import merge_articles, probable_match


VISIBLE_COLUMNS = [
    ("id", "ID", 80),
    ("authors_main", "Autores principais", 180),
    ("short_name", "Estudo", 125),
    ("year", "Ano", 60),
    ("title", "Título", 350),
    ("journal", "Periódico", 170),
    ("doi", "DOI", 205),
    ("pmid", "PMID", 90),
    ("pmcid", "PMCID", 110),
    ("abstract_status", "Abstract disponível", 160),
    ("oa_status", "Acesso", 120),
    ("pdf", "PDF", 165),
    ("structured", "Texto estruturado", 120),
    ("status", "Status", 230),
    ("downloaded", "PDF baixado", 95),
]

FORMAT_OPTIONS = {
    "Detectar automaticamente": "auto",
    "CSV/TSV": "table",
    "PubMed/MEDLINE/NBIB": "medline",
    "PubMed Abstract": "pubmed_abstract",
    "PubMed Summary": "pubmed_summary",
    "Lista de PMID": "pmid_list",
    "Lista de DOI": "doi_list",
    "XML da relação": "xml",
}


class ArticleDialog(tk.Toplevel):
    fields = [
        ("authors", "Autores"), ("authors_main", "Autores principais"), ("short_name", "Nome curto"),
        ("year", "Ano"), ("title", "Título"), ("journal", "Periódico"), ("doi", "DOI"),
        ("pmid", "PMID"), ("pmcid", "PMCID"), ("abstract", "Abstract"),
    ]

    def __init__(self, parent, article: Article | None = None):
        super().__init__(parent)
        self.title("Editar artigo" if article else "Adicionar artigo")
        self.transient(parent)
        self.grab_set()
        self.result: Article | None = None
        self.article = article or Article()
        self.entries: dict[str, tk.Widget] = {}
        self.columnconfigure(1, weight=1)
        for row, (field, label) in enumerate(self.fields):
            ttk.Label(self, text=label).grid(row=row, column=0, sticky="nw", padx=8, pady=4)
            if field in {"title", "abstract"}:
                widget = tk.Text(self, height=3 if field == "title" else 8, width=75, wrap="word")
                widget.insert("1.0", getattr(self.article, field))
            else:
                widget = ttk.Entry(self, width=75)
                widget.insert(0, getattr(self.article, field))
            widget.grid(row=row, column=1, sticky="nsew", padx=8, pady=4)
            self.entries[field] = widget
        buttons = ttk.Frame(self)
        buttons.grid(row=len(self.fields), column=0, columnspan=2, sticky="e", padx=8, pady=10)
        ttk.Button(buttons, text="Cancelar", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(buttons, text="Salvar", command=self.save).pack(side="right", padx=4)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.geometry("850x650")

    def save(self):
        old_pdf_url = self.article.pdf_url
        for field, widget in self.entries.items():
            value = widget.get("1.0", "end").strip() if isinstance(widget, tk.Text) else widget.get().strip()
            setattr(self.article, field, value)
            self.article.manual_fields.add(field)
            self.article.field_sources[field] = "Edição manual"
        if self.article.abstract:
            if self.article.abstract_status == "Não":
                self.article.abstract_status = "Sim — edição manual"
            self.article.abstract_source = self.article.abstract_source or "Edição manual"
        else:
            self.article.abstract_status = "Não"
        if self.article.pdf_url != old_pdf_url:
            self.article.pdf_check_status = "Não verificado"
            self.article.pdf_check_message = ""
            self.article.pdf_checked_at = ""
        self.result = self.article.normalize()
        self.destroy()


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, config: dict):
        super().__init__(parent)
        self.title("Configurações")
        self.transient(parent)
        self.grab_set()
        self.result = None
        self.vars = {
            "tool_name": tk.StringVar(value=config.get("tool_name", "RastreadorArtigos")),
            "email": tk.StringVar(value=config.get("email", "")),
            "openalex_api_key": tk.StringVar(value=config.get("openalex_api_key", "")),
            "timeout_seconds": tk.StringVar(value=str(config.get("timeout_seconds", 30))),
            "max_retries": tk.StringVar(value=str(config.get("max_retries", 3))),
            "request_interval_seconds": tk.StringVar(value=str(config.get("request_interval_seconds", 0.4))),
        }
        labels = {
            "tool_name": "Nome da ferramenta",
            "email": "E-mail das APIs",
            "openalex_api_key": "Chave OpenAlex",
            "timeout_seconds": "Timeout (s)",
            "max_retries": "Tentativas",
            "request_interval_seconds": "Intervalo entre consultas (s)",
        }
        for row, key in enumerate(self.vars):
            ttk.Label(self, text=labels[key]).grid(row=row, column=0, sticky="w", padx=8, pady=5)
            ttk.Entry(self, textvariable=self.vars[key], width=58, show="*" if key == "openalex_api_key" else "").grid(
                row=row, column=1, padx=8, pady=5
            )
        ttk.Label(
            self,
            text="O e-mail é necessário para Unpaywall/NCBI. A chave OpenAlex é preservada apenas no computador.",
            foreground="#555555",
        ).grid(row=len(self.vars), column=0, columnspan=2, sticky="w", padx=8, pady=(2, 8))
        buttons = ttk.Frame(self)
        buttons.grid(row=len(self.vars) + 1, column=0, columnspan=2, sticky="e", padx=8, pady=10)
        ttk.Button(buttons, text="Cancelar", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(buttons, text="Salvar", command=self.save).pack(side="right", padx=4)

    def save(self):
        try:
            result = {key: var.get().strip() for key, var in self.vars.items()}
            result["timeout_seconds"] = float(result["timeout_seconds"])
            result["max_retries"] = int(result["max_retries"])
            result["request_interval_seconds"] = float(result["request_interval_seconds"])
            self.result = result
            self.destroy()
        except ValueError:
            messagebox.showerror("Configurações", "Timeout, tentativas e intervalo devem ser numéricos.", parent=self)


class App:
    def __init__(self, root: tk.Tk, base_dir: Path):
        self.root = root
        self.base_dir = base_dir
        self.config_path = base_dir / "config.json"
        self.config = self.load_config()
        self.db = Database(base_dir / "rastreador_artigos.db")
        self.events: Queue = Queue()
        self.cancel_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.temp_files: list[str] = []

        self.root.title("Rastreador de Artigos")
        self.root.geometry("1500x900")
        self.root.minsize(1100, 680)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.build_ui()
        self.reload_table()
        self.root.after(150, self.process_events)

    def load_config(self) -> dict:
        defaults = {
            "tool_name": "RastreadorArtigos",
            "email": "",
            "openalex_api_key": "",
            "timeout_seconds": 30,
            "max_retries": 3,
            "request_interval_seconds": 0.4,
        }
        try:
            defaults.update(json.loads(self.config_path.read_text(encoding="utf-8")))
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        return defaults

    def save_config(self):
        self.config_path.write_text(json.dumps(self.config, ensure_ascii=False, indent=2), encoding="utf-8")

    def build_ui(self):
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")

        header = ttk.Frame(self.root, padding=(10, 8))
        header.pack(fill="x")
        ttk.Label(header, text="Rastreador de Artigos", font=("Segoe UI", 16, "bold")).pack(side="left")
        self.email_label_var = tk.StringVar(value=self.config.get("email", ""))
        ttk.Label(header, textvariable=self.email_label_var).pack(side="right", padx=10)
        ttk.Button(header, text="Configurações", command=self.settings).pack(side="right")

        management = ttk.Frame(self.root, padding=(10, 0, 10, 6))
        management.pack(fill="x")
        for text, command in [
            ("Importar arquivos", self.import_files), ("Extrair texto", self.import_paste),
            ("Adicionar", self.add_article), ("Editar", self.edit_selected), ("Excluir", self.delete_selected),
            ("Desfazer exclusão", self.undo_delete), ("Renumerar IDs", self.renumber),
            ("Novo projeto / Zerar", self.reset_project), ("Limpar seleção", self.clear_selection),
        ]:
            ttk.Button(management, text=text, command=command).pack(side="left", padx=2)

        actions = ttk.Frame(self.root, padding=(10, 0, 10, 6))
        actions.pack(fill="x")
        for text, command in [
            ("Executar processo completo", self.run_full_process),
            ("Cancelar", self.cancel_task),
            ("Verificar PDFs", self.verify_pdfs),
            ("Abrir selecionados", self.open_selected),
            ("Abrir todos", self.open_all),
            ("Gerar relatório", self.generate_report),
            ("Imprimir", self.print_report),
            ("Baixar PDFs", self.download_pdfs),
            ("Gerar ZIP", self.generate_zip),
        ]:
            ttk.Button(actions, text=text, command=command).pack(side="left", padx=2)

        self.include_abstracts = tk.BooleanVar(value=False)
        self.download_json = tk.BooleanVar(value=True)
        self.download_xml = tk.BooleanVar(value=False)
        options = ttk.Frame(self.root, padding=(10, 0, 10, 6))
        options.pack(fill="x")
        ttk.Checkbutton(options, text="Incluir abstracts no relatório TXT", variable=self.include_abstracts).pack(side="left")
        ttk.Checkbutton(options, text="Incluir JSON BioC no ZIP", variable=self.download_json).pack(side="left", padx=12)
        ttk.Checkbutton(options, text="Incluir XML BioC no ZIP", variable=self.download_xml).pack(side="left")

        progress_frame = ttk.Frame(self.root, padding=(10, 0, 10, 6))
        progress_frame.pack(fill="x")
        self.progress = ttk.Progressbar(progress_frame, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True)
        self.progress_label = ttk.Label(progress_frame, text="Pronto")
        self.progress_label.pack(side="left", padx=8)

        paned = ttk.Panedwindow(self.root, orient="vertical")
        paned.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        input_frame = ttk.LabelFrame(paned, text="Entrada de dados")
        input_top = ttk.Frame(input_frame)
        input_top.pack(fill="x", padx=6, pady=4)
        ttk.Label(input_top, text="Formato:").pack(side="left")
        self.format_var = tk.StringVar(value="Detectar automaticamente")
        ttk.Combobox(input_top, textvariable=self.format_var, values=list(FORMAT_OPTIONS), state="readonly", width=28).pack(side="left", padx=6)
        ttk.Button(input_top, text="Limpar entrada", command=lambda: self.input_text.delete("1.0", "end")).pack(side="right")
        self.input_text = tk.Text(input_frame, height=7, wrap="none", undo=True)
        self.input_text.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        paned.add(input_frame, weight=1)

        table_frame = ttk.LabelFrame(paned, text="Artigos")
        self.tree = ttk.Treeview(table_frame, columns=[c[0] for c in VISIBLE_COLUMNS], show="headings", selectmode="extended")
        for key, label, width in VISIBLE_COLUMNS:
            self.tree.heading(key, text=label, command=lambda k=key: self.sort_tree(k, False))
            self.tree.column(key, width=width, minwidth=50, stretch=key in {"title", "status"})
        ybar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        xbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self.tree.bind("<Double-1>", lambda _e: self.edit_selected())
        self.tree.bind("<Delete>", lambda _e: self.delete_selected())
        self.tree.bind("<Escape>", lambda _e: self.clear_selection())
        self.tree.bind("<Button-1>", self.on_tree_click, add="+")
        for tag, color in {
            "available": "#c6efce", "partial": "#e2f0d9", "missing": "#fff2cc", "error": "#f4cccc",
            "working": "#d9eaf7", "conflict": "#e4dfec", "pending": "#e7e6e6",
        }.items():
            self.tree.tag_configure(tag, background=color)
        paned.add(table_frame, weight=4)

        notebook = ttk.Notebook(paned)
        self.summary_text = self.make_output_tab(notebook, "Resumo")
        self.links_text = self.make_output_tab(notebook, "Links")
        self.log_text = self.make_output_tab(notebook, "Log")
        paned.add(notebook, weight=1)

    @staticmethod
    def make_output_tab(notebook, title):
        frame = ttk.Frame(notebook)
        text = tk.Text(frame, height=8, wrap="word", state="disabled")
        scroll = ttk.Scrollbar(frame, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        notebook.add(frame, text=title)
        return text

    def set_output(self, widget: tk.Text, content: str):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", content)
        widget.configure(state="disabled")

    def article_values(self, article: Article):
        return (
            article.id, article.authors_main, article.short_name, article.year, article.title, article.journal,
            article.doi, article.pmid, article.pmcid, article.abstract_status, article.oa_status,
            article.pdf_display, article.structured_display, article.status,
            "Sim" if article.pdf_downloaded else "Não",
        )

    def reload_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for article in self.db.list_articles():
            self.tree.insert("", "end", iid=article.id, values=self.article_values(article), tags=(article.color_state,))
        self.refresh_outputs()

    def refresh_outputs(self):
        articles = self.db.list_articles()
        confirmed = sum(a.pdf_check_status == "Download confirmado" for a in articles)
        unverified = sum(bool(a.pdf_url) and a.pdf_check_status == "Não verificado" for a in articles)
        missing = sum(not a.pdf_url for a in articles)
        structured = sum(bool(a.json_url or a.xml_url) for a in articles)
        abstracts = sum(a.abstract_status != "Não" for a in articles)
        downloaded = sum(bool(a.pdf_downloaded) for a in articles)
        self.set_output(
            self.summary_text,
            f"Artigos cadastrados: {len(articles)}\n"
            f"PDFs com download confirmado: {confirmed}\n"
            f"Links de PDF ainda não verificados: {unverified}\n"
            f"PDFs não localizados: {missing}\n"
            f"Textos estruturados disponíveis: {structured}\n"
            f"PDFs baixados: {downloaded}\n"
            f"Abstracts disponíveis: {abstracts}\n",
        )
        links = []
        for article in articles:
            parts = []
            if article.pdf_url:
                parts.append(f"PDF [{article.pdf_display}]: {article.pdf_url}")
            else:
                parts.append("Não foi possível rastrear texto integral aberto.")
            if article.json_url:
                parts.append(f"JSON: {article.json_url}")
            if article.xml_url:
                parts.append(f"XML: {article.xml_url}")
            if article.doi:
                parts.append(f"DOI: https://doi.org/{article.doi}")
            if article.pmid:
                parts.append(f"PubMed: https://pubmed.ncbi.nlm.nih.gov/{article.pmid}/")
            links.append(f"{article.id} | {article.authors_main or article.short_name} | " + " | ".join(parts))
        self.set_output(self.links_text, "\n".join(links))
        log_lines = [f"{x['timestamp']} | {x['article_id']} | {x['service']} | {x['level']} | {x['message']}" for x in self.db.logs()]
        self.set_output(self.log_text, "\n".join(log_lines))

    def import_files(self):
        paths = filedialog.askopenfilenames(
            title="Selecionar arquivos",
            filetypes=[("Arquivos suportados", "*.csv *.tsv *.txt *.nbib *.xml"), ("Todos os arquivos", "*.*")],
        )
        if not paths:
            return
        try:
            count = self.integrate_records(parse_files(paths))
            self.reload_table()
            messagebox.showinfo("Importação", f"{count} registros foram incorporados ou atualizados.")
        except Exception as exc:
            messagebox.showerror("Importação", str(exc))

    def import_paste(self):
        text = self.input_text.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("Entrada", "Cole ou digite os dados antes de extrair.")
            return
        try:
            fmt = FORMAT_OPTIONS[self.format_var.get()]
            count = self.integrate_records(parse_source(text, "Colagem manual", fmt))
            self.reload_table()
            messagebox.showinfo("Extração", f"{count} registros foram incorporados ou atualizados.")
        except Exception as exc:
            messagebox.showerror("Extração", str(exc))

    def integrate_records(self, records: list[Article]) -> int:
        count = 0
        for incoming in records:
            incoming.normalize()
            existing = self.db.get(incoming.id) if incoming.id else None
            existing = existing or self.db.find_exact(incoming)
            if not existing and incoming.title:
                possible = self.db.find_by_title_year(normalize_title(incoming.title), incoming.year)
                if possible and probable_match(possible, incoming) >= 0.93:
                    existing = possible if messagebox.askyesno(
                        "Possível correspondência",
                        f"Unir o registro importado ao {possible.id}?\n\n{possible.title}\n\n{incoming.title}",
                    ) else None
            if existing:
                old_pdf = existing.pdf_url
                merged = merge_articles(existing, incoming, incoming.source)
                if merged.pdf_url != old_pdf:
                    merged.pdf_check_status = "Não verificado"
                    merged.pdf_check_message = ""
                    merged.pdf_checked_at = ""
                self.db.save(merged)
            else:
                if not incoming.id or self.db.get(incoming.id):
                    incoming.id = self.db.next_id()
                self.db.save(incoming)
            count += 1
        return count

    def add_article(self):
        dialog = ArticleDialog(self.root, Article(id=self.db.next_id()))
        self.root.wait_window(dialog)
        if dialog.result:
            self.db.save(dialog.result)
            self.reload_table()

    def selected_ids(self) -> list[str]:
        return list(self.tree.selection())

    def clear_selection(self):
        self.tree.selection_remove(self.tree.selection())
        self.tree.focus("")

    def on_tree_click(self, event):
        row = self.tree.identify_row(event.y)
        if not row:
            self.root.after_idle(self.clear_selection)
            return
        if row in self.tree.selection() and len(self.tree.selection()) == 1 and not (event.state & 0x0004):
            self.root.after_idle(self.clear_selection)
            return "break"

    def edit_selected(self):
        ids = self.selected_ids()
        if len(ids) != 1:
            messagebox.showwarning("Editar", "Selecione exatamente um artigo.")
            return
        article = self.db.get(ids[0])
        if not article:
            return
        dialog = ArticleDialog(self.root, article)
        self.root.wait_window(dialog)
        if dialog.result:
            self.db.save(dialog.result)
            self.reload_table()

    def delete_selected(self):
        ids = self.selected_ids()
        if not ids:
            messagebox.showwarning("Excluir", "Selecione pelo menos um artigo.")
            return
        if not messagebox.askyesno("Excluir", f"Excluir {len(ids)} artigo(s) da lista?"):
            return
        for article_id in ids:
            self.db.delete(article_id)
        self.reload_table()

    def undo_delete(self):
        if not self.db.undo_delete():
            messagebox.showinfo("Desfazer", "Não há exclusão para desfazer.")
            return
        self.reload_table()

    def renumber(self):
        if messagebox.askyesno("Renumerar IDs", "Renumerar todos os artigos sequencialmente?"):
            self.db.renumber()
            self.reload_table()

    def reset_project(self):
        if self.worker and self.worker.is_alive():
            messagebox.showwarning("Novo projeto", "Cancele ou aguarde a operação atual.")
            return
        if not messagebox.askyesno(
            "Novo projeto / Zerar",
            "Todos os artigos, resultados, links e logs serão removidos.\n\n"
            "O e-mail, a chave OpenAlex e as configurações serão preservados. Continuar?",
        ):
            return
        self.db.reset_project()
        for temp_file in self.temp_files:
            try:
                Path(temp_file).unlink(missing_ok=True)
            except OSError:
                pass
        self.temp_files.clear()
        self.input_text.delete("1.0", "end")
        self.clear_selection()
        self.progress["value"] = 0
        self.progress_label.configure(text="Pronto")
        self.reload_table()

    def settings(self):
        dialog = SettingsDialog(self.root, self.config)
        self.root.wait_window(dialog)
        if dialog.result:
            self.config.update(dialog.result)
            self.save_config()
            self.email_label_var.set(self.config.get("email", ""))
            messagebox.showinfo("Configurações", "Configurações salvas.")

    def _can_start(self, title: str) -> list[Article] | None:
        if self.worker and self.worker.is_alive():
            messagebox.showwarning(title, "Já existe uma operação em andamento.")
            return None
        articles = self.db.list_articles()
        if not articles:
            messagebox.showwarning(title, "Não há artigos na lista.")
            return None
        return articles

    def run_full_process(self):
        articles = self._can_start("Processo completo")
        if articles is None:
            return
        if not self.config.get("email"):
            if not messagebox.askyesno(
                "Configuração incompleta",
                "O e-mail das APIs está vazio. Unpaywall e NCBI podem recusar consultas.\n\nExecutar mesmo assim?",
            ):
                self.settings()
                return
        self._start_worker(self.full_process_worker, articles)

    def verify_pdfs(self):
        articles = self._can_start("Verificar PDFs")
        if articles is None:
            return
        candidates = [a for a in articles if a.pdf_url]
        if not candidates:
            messagebox.showwarning("Verificar PDFs", "Nenhuma URL de PDF foi localizada.")
            return
        self._start_worker(self.verify_worker, candidates)

    def _start_worker(self, target, articles, *extra):
        self.cancel_event.clear()
        self.progress["value"] = 0
        self.progress["maximum"] = max(1, len(articles))
        self.worker = threading.Thread(target=target, args=(articles, *extra), daemon=True)
        self.worker.start()

    def full_process_worker(self, articles: list[Article]):
        client = ApiClient(self.config)
        timeout = float(self.config.get("timeout_seconds", 30))
        total = len(articles)
        for index, article in enumerate(articles, 1):
            if self.cancel_event.is_set():
                self.events.put(("done", "Operação cancelada."))
                return
            try:
                article.status = "Consultando APIs"
                self.db.save(article)
                self.events.put(("refresh", index - 1, total, article.id))
                old_pdf = article.pdf_url
                article = client.complete_identifiers(article)
                if article.doi:
                    article = client.unpaywall(article)
                if not article.pdf_url and self.config.get("openalex_api_key"):
                    article = merge_articles(article, client.openalex(article), "OpenAlex")
                article = client.pmc_resources(article)
                if article.pdf_url != old_pdf:
                    article.pdf_check_status = "Não verificado"
                    article.pdf_check_message = ""
                    article.pdf_checked_at = ""
                if article.pdf_url:
                    article.status = "Verificando PDF"
                    self.db.save(article)
                    article = verify_article_pdf(article, timeout)
                elif article.json_url or article.xml_url:
                    article.status = "Texto estruturado disponível; PDF não localizado"
                    article.oa_status = "Aberto"
                else:
                    article.oa_status = "Requer acesso institucional/manual"
                    article.status = "Não foi possível rastrear texto integral aberto"
                self.db.save(article)
                self.db.log(article.id, "Processo completo", article.status)
            except Exception as exc:
                article.status = f"Erro de API: {exc}"
                self.db.save(article)
                self.db.log(article.id, "Processo completo", str(exc), "ERROR")
            self.events.put(("refresh", index, total, article.id))
        self.events.put(("done", "Processo completo concluído."))

    def verify_worker(self, articles: list[Article]):
        timeout = float(self.config.get("timeout_seconds", 30))
        total = len(articles)
        for index, article in enumerate(articles, 1):
            if self.cancel_event.is_set():
                self.events.put(("done", "Verificação cancelada."))
                return
            article.status = "Verificando PDF"
            self.db.save(article)
            try:
                article = verify_article_pdf(article, timeout)
                self.db.log(article.id, "Verificação PDF", f"{article.pdf_check_status}: {article.pdf_check_message}")
            except Exception as exc:
                article.pdf_check_status = "Erro temporário"
                article.pdf_check_message = str(exc)
                article.status = "Erro na verificação do PDF"
                self.db.log(article.id, "Verificação PDF", str(exc), "ERROR")
            self.db.save(article)
            self.events.put(("refresh", index, total, article.id))
        self.events.put(("done", "Verificação de PDFs concluída."))

    def cancel_task(self):
        self.cancel_event.set()

    def process_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "refresh":
                    _, current, total, article_id = event
                    self.progress["maximum"] = total
                    self.progress["value"] = current
                    self.progress_label.configure(text=f"{article_id} — {current}/{total}")
                    self.reload_table()
                elif kind == "done":
                    self.progress_label.configure(text=event[1])
                    self.reload_table()
                    messagebox.showinfo("Operação", event[1])
                elif kind == "error":
                    self.progress_label.configure(text="Erro")
                    self.reload_table()
                    messagebox.showerror("Operação", event[1])
        except Empty:
            pass
        self.root.after(150, self.process_events)

    def open_selected(self):
        ids = self.selected_ids()
        if not ids:
            messagebox.showwarning("Abrir links", "Selecione pelo menos um artigo.")
            return
        self.open_links([self.db.get(i) for i in ids])

    def open_all(self):
        articles = self.db.list_articles()
        if len(articles) > 15 and not messagebox.askyesno("Abrir links", f"Abrir {len(articles)} links no navegador?"):
            return
        self.open_links(articles)

    @staticmethod
    def open_links(articles):
        for article in articles:
            if article and article.main_link:
                webbrowser.open_new_tab(article.main_link)

    def generate_report(self):
        path = filedialog.asksaveasfilename(title="Salvar relatório", defaultextension=".txt", filetypes=[("Texto", "*.txt")])
        if path:
            write_txt(path, self.db.list_articles(), self.include_abstracts.get())
            messagebox.showinfo("Relatório", "Relatório gerado.")

    def print_report(self):
        handle = tempfile.NamedTemporaryFile(delete=False, suffix=".html")
        handle.close()
        write_html(handle.name, self.db.list_articles())
        self.temp_files.append(handle.name)
        webbrowser.open(Path(handle.name).as_uri())

    def download_pdfs(self):
        articles = self._can_start("Baixar PDFs")
        if articles is None:
            return
        eligible = [a for a in articles if a.pdf_check_status == "Download confirmado" and a.pdf_url]
        if not eligible:
            messagebox.showwarning("Baixar PDFs", "Nenhum PDF possui download confirmado. Execute o processo completo ou Verificar PDFs.")
            return
        parent = filedialog.askdirectory(title="Selecionar pasta de destino")
        if not parent:
            return
        destination = Path(parent) / f"Artigos_Baixados_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self._start_worker(self.download_folder_worker, eligible, destination, self.include_abstracts.get())

    def download_folder_worker(self, articles: list[Article], destination: Path, include_abstracts: bool):
        try:
            download_pdfs_folder(
                destination,
                articles,
                self.db,
                include_abstracts=include_abstracts,
                timeout=float(self.config.get("timeout_seconds", 30)) * 2,
                progress=lambda current, total, aid: self.events.put(("refresh", current, total, aid)),
                cancelled=self.cancel_event.is_set,
            )
            self.events.put(("done", f"PDFs e relatório salvos em:\n{destination}"))
        except Exception as exc:
            self.events.put(("error", str(exc)))

    def generate_zip(self):
        articles = self._can_start("Gerar ZIP")
        if articles is None:
            return
        eligible = [a for a in articles if a.pdf_check_status == "Download confirmado" and a.pdf_url]
        if not eligible:
            messagebox.showwarning("Gerar ZIP", "Nenhum PDF possui download confirmado. Execute o processo completo ou Verificar PDFs.")
            return
        path = filedialog.asksaveasfilename(title="Salvar pacote ZIP", defaultextension=".zip", filetypes=[("Arquivo ZIP", "*.zip")])
        if not path:
            return
        self._start_worker(
            self.zip_worker, eligible, Path(path), self.include_abstracts.get(), self.download_json.get(), self.download_xml.get()
        )

    def zip_worker(
        self, articles: list[Article], path: Path, include_abstracts: bool, download_json: bool, download_xml: bool
    ):
        try:
            create_package(
                path,
                articles,
                self.db,
                include_abstracts=include_abstracts,
                download_json=download_json,
                download_xml=download_xml,
                timeout=float(self.config.get("timeout_seconds", 30)) * 2,
                progress=lambda current, total, aid: self.events.put(("refresh", current, total, aid)),
                cancelled=self.cancel_event.is_set,
            )
            self.events.put(("done", f"Pacote gerado:\n{path}"))
        except Exception as exc:
            self.events.put(("error", str(exc)))

    def sort_tree(self, column: str, reverse: bool):
        items = [(self.tree.set(item, column), item) for item in self.tree.get_children("")]
        items.sort(key=lambda x: x[0].lower(), reverse=reverse)
        for index, (_, item) in enumerate(items):
            self.tree.move(item, "", index)
        self.tree.heading(column, command=lambda: self.sort_tree(column, not reverse))

    def close(self):
        self.cancel_event.set()
        for temp_file in self.temp_files:
            try:
                Path(temp_file).unlink(missing_ok=True)
            except OSError:
                pass
        self.db.close()
        self.root.destroy()
