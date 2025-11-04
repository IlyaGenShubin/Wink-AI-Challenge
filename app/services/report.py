import os
from typing import Any
from fastapi.templating import Jinja2Templates
from weasyprint import HTML
from app.models.schemas import AnalysisResult
from fastapi import Request

TEMPLATES = Jinja2Templates(directory="app/templates")

def render_html(analysis: AnalysisResult) -> str:
    # Рендерим Jinja2 вручную через TemplateResponse альтернативой: используем шаблон report.html
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    env = Environment(
        loader=FileSystemLoader("app/templates"),
        autoescape=select_autoescape()
    )
    tpl = env.get_template("report.html")
    html = tpl.render(analysis=analysis)
    out_path = os.path.join("data", "reports", f"{analysis.file_id}.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path

def render_pdf(analysis: AnalysisResult) -> str:
    html_path = render_html(analysis)
    pdf_path = os.path.join("data", "reports", f"{analysis.file_id}.pdf")
    HTML(html_path, encoding="utf-8").write_pdf(pdf_path)
    return pdf_path
