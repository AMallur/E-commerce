"""FastAPI application exposing the medical bill explainer."""
from __future__ import annotations

import json
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app.config import get_settings
from app.parsing.pipeline import parse_document, parsed_document_to_dict
from app.rendering.report import render_html, write_pdf

LOGGER = logging.getLogger(__name__)

app = FastAPI(title="Medical Bill Explainer", version="1.0.0")


@app.post("/parse")
async def parse_bill(file: UploadFile = File(...)) -> JSONResponse:
    settings = get_settings()
    suffix = Path(file.filename or "upload.pdf").suffix or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
        shutil.copyfileobj(file.file, temp)
        temp_path = Path(temp.name)
    document = parse_document(temp_path, settings=settings)
    payload = parsed_document_to_dict(document)
    if not settings.persist_uploads:
        temp_path.unlink(missing_ok=True)
    return JSONResponse(payload)


@app.post("/render")
async def render_bill(file: UploadFile = File(...)) -> FileResponse:
    settings = get_settings()
    suffix = Path(file.filename or "upload.pdf").suffix or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
        shutil.copyfileobj(file.file, temp)
        temp_path = Path(temp.name)
    document = parse_document(temp_path, settings=settings)
    html_content = render_html(document, settings=settings)
    if settings.persist_uploads:
        output_dir = temp_path.parent
    else:
        output_dir = Path(tempfile.mkdtemp())
    pdf_path = output_dir / "report.pdf"
    try:
        write_pdf(document, pdf_path, html_content=html_content, settings=settings)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    if not settings.persist_uploads:
        temp_path.unlink(missing_ok=True)
    return FileResponse(path=pdf_path, media_type="application/pdf", filename="report.pdf")


__all__ = ["app"]

from fastapi.responses import HTMLResponse


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return """<!DOCTYPE html>
<html lang=\"en\">
<head>
<meta charset=\"utf-8\" />
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
<title>Medical Bill Explainer</title>
<style>
body { font-family: Arial, sans-serif; margin: 2rem; background: #f8fafc; }
main { max-width: 960px; margin: auto; background: #fff; padding: 2rem; border-radius: 0.5rem; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
header { text-align: center; margin-bottom: 2rem; }
label { display: block; margin-bottom: 0.5rem; font-weight: bold; }
input[type=file] { margin-bottom: 1rem; }
button { background: #2563eb; color: white; border: none; padding: 0.75rem 1.5rem; border-radius: 0.375rem; cursor: pointer; font-size: 1rem; }
button:disabled { background: #a5b4fc; cursor: not-allowed; }
#results { margin-top: 2rem; }
.card-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; }
.card { background: #eff6ff; padding: 1rem; border-radius: 0.5rem; }
summary { font-weight: bold; }
.accordion { margin-top: 1.5rem; }
.line-card { border: 1px solid #cbd5f5; border-radius: 0.5rem; padding: 1rem; margin-bottom: 1rem; }
</style>
</head>
<body>
<main>
<header>
<h1>Medical Bill Explainer</h1>
<p>Upload a PDF medical bill to receive a plain-language summary.</p>
</header>
<section>
<label for=\"file\">Medical bill PDF</label>
<input id=\"file\" type=\"file\" accept=\"application/pdf\" />
<button id=\"uploadBtn\">Upload and Analyze</button>
</section>
<section id=\"status\"></section>
<section id=\"results\" hidden>
<div class=\"card-grid\">
<div class=\"card\"><h3>Total Charge</h3><p id=\"total-charge\"></p></div>
<div class=\"card\"><h3>Total Allowed</h3><p id=\"total-allowed\"></p></div>
<div class=\"card\"><h3>Insurer Paid</h3><p id=\"payer-paid\"></p></div>
<div class=\"card\"><h3>Patient Owes</h3><p id=\"patient-owes\"></p></div>
</div>
<div class=\"accordion\" id=\"lines\"></div>
<a id=\"download-json\" download=\"parsed.json\">Download JSON</a>
</section>
<footer style=\"margin-top:2rem; font-size:0.875rem; color:#475569;\">Educational summary, not medical or legal advice.</footer>
</main>
<script>
const uploadBtn = document.getElementById('uploadBtn');
const fileInput = document.getElementById('file');
const statusEl = document.getElementById('status');
const results = document.getElementById('results');
const totals = {
  charge: document.getElementById('total-charge'),
  allowed: document.getElementById('total-allowed'),
  payer: document.getElementById('payer-paid'),
  patient: document.getElementById('patient-owes'),
};
const linesContainer = document.getElementById('lines');
const downloadJson = document.getElementById('download-json');

uploadBtn.addEventListener('click', async () => {
  if (!fileInput.files.length) {
    statusEl.textContent = 'Please select a PDF file first.';
    return;
  }
  uploadBtn.disabled = true;
  statusEl.textContent = 'Uploading and parsing…';
  const form = new FormData();
  form.append('file', fileInput.files[0]);
  try {
    const response = await fetch('/parse', { method: 'POST', body: form });
    if (!response.ok) {
      throw new Error('Parsing failed.');
    }
    const payload = await response.json();
    statusEl.textContent = 'Completed.';
    results.hidden = false;
    totals.charge.textContent = formatCurrency(payload.totals.total_charge);
    totals.allowed.textContent = formatCurrency(payload.totals.total_allowed);
    totals.payer.textContent = formatCurrency(payload.totals.payer_paid);
    totals.patient.textContent = formatCurrency(payload.totals.patient_owes);
    linesContainer.innerHTML = '';
    payload.lines.forEach(line => {
      const card = document.createElement('div');
      card.className = 'line-card';
      const heading = document.createElement('h3');
      heading.textContent = `Line ${line.line_no}: ${line.code || ''}`;
      const body = document.createElement('p');
      body.textContent = line.explanation;
      const list = document.createElement('ul');
      const fields = ['charge','allowed','payer_paid','patient_owes_line'];
      fields.forEach(field => {
        if (line[field] !== null && line[field] !== undefined) {
          const item = document.createElement('li');
          item.textContent = `${field.replace(/_/g,' ')}: ${formatCurrency(line[field])}`;
          list.appendChild(item);
        }
      });
      card.appendChild(heading);
      card.appendChild(body);
      card.appendChild(list);
      linesContainer.appendChild(card);
    });
    downloadJson.href = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' }));
  } catch (err) {
    console.error(err);
    statusEl.textContent = 'An error occurred while parsing the document.';
  } finally {
    uploadBtn.disabled = false;
  }
});

function formatCurrency(value) {
  if (value === null || value === undefined) {
    return '—';
  }
  return new Intl.NumberFormat(undefined, { style: 'currency', currency: 'USD' }).format(value);
}
</script>
</body>
</html>"""
