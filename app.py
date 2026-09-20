#!/usr/bin/env python3
"""
Interfaz web para explorador-de-redit
- Extrae hilos de Reddit a Markdown descargable
- Funciona CON o SIN credenciales
- Guarda credenciales en localStorage del navegador
- Previsualización del Markdown
- Historial de hilos explorados (persistente en history.json)
"""

import io
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from flask import Flask, request, render_template_string, send_file, flash, redirect, url_for

try:
    import praw
except ImportError:
    praw = None

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "explorador-de-redit-dev-key-cambia-esto")

USER_AGENT = "web:explorador-de-redit:v1.2 (by u/usuario)"
HISTORY_FILE = Path(__file__).parent / "history.json"
HISTORY_MD_DIR = Path(__file__).parent / "history_md"
HISTORY_MD_DIR.mkdir(exist_ok=True)
MAX_HISTORY = 50  # máximo de entradas en el historial


# ---------------------------------------------------------------------------
# Historial
# ---------------------------------------------------------------------------

def cargar_historial() -> list:
    if not HISTORY_FILE.exists():
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def guardar_historial(entries: list) -> None:
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def anadir_al_historial(
    url: str,
    title: str,
    filename: str,
    mode: str,
    markdown: str,
) -> str:
    """Guarda una entrada y el Markdown en disco. Devuelve el id de la entrada."""
    entries = cargar_historial()
    entry_id = str(uuid.uuid4())[:8]

    # Guardar el markdown en archivo local para poder re-descargarlo
    md_path = HISTORY_MD_DIR / f"{entry_id}.md"
    md_path.write_text(markdown, encoding="utf-8")

    entry = {
        "id": entry_id,
        "url": url,
        "title": title,
        "filename": filename,
        "mode": mode,  # noauth | auth
        "created_at": datetime.now(timezone.utc).isoformat(),
        "md_file": str(md_path.name),
    }

    # Evitar duplicados exactos de URL recientes: actualizamos la entrada si existe
    entries = [e for e in entries if e.get("url") != url]
    entries.insert(0, entry)
    entries = entries[:MAX_HISTORY]

    # Limpiar archivos md huérfanos (más allá del límite)
    ids_vivos = {e["id"] for e in entries}
    for f in HISTORY_MD_DIR.glob("*.md"):
        if f.stem not in ids_vivos:
            try:
                f.unlink()
            except OSError:
                pass

    guardar_historial(entries)
    return entry_id


def eliminar_entrada(entry_id: str) -> bool:
    entries = cargar_historial()
    nueva = [e for e in entries if e.get("id") != entry_id]
    if len(nueva) == len(entries):
        return False
    guardar_historial(nueva)
    md_path = HISTORY_MD_DIR / f"{entry_id}.md"
    if md_path.exists():
        try:
            md_path.unlink()
        except OSError:
            pass
    return True


def obtener_entrada(entry_id: str) -> dict | None:
    for e in cargar_historial():
        if e.get("id") == entry_id:
            return e
    return None


# ---------------------------------------------------------------------------
# Utilidades comunes
# ---------------------------------------------------------------------------

def timestamp_a_str(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def escapar_markdown(texto: str) -> str:
    if not texto:
        return ""
    return texto.replace("\r\n", "\n").strip()


def normalizar_url(url: str) -> str:
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if path.endswith(".json"):
        path = path[:-5]
    return f"https://www.reddit.com{path}"


def nombre_archivo_seguro(title: str, post_id: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_ " else "" for c in (title or ""))[:50]
    safe = safe.strip().replace(" ", "_") or post_id
    return f"{post_id}_{safe}.md"


# ---------------------------------------------------------------------------
# Modo SIN credenciales
# ---------------------------------------------------------------------------

def comentario_json_a_md(node: dict, profundidad: int = 0) -> str:
    if node.get("kind") != "t1":
        return ""

    data = node.get("data", {})
    autor = data.get("author") or "[eliminado]"
    puntuacion = data.get("score", 0)
    fecha = timestamp_a_str(data.get("created_utc", 0))
    cuerpo = escapar_markdown(data.get("body", ""))

    indent = "  " * profundidad
    lineas = [
        f"{indent}- **u/{autor}** ({puntuacion} pts) · {fecha}",
        f"{indent}  ",
    ]
    for linea in cuerpo.split("\n"):
        lineas.append(f"{indent}  {linea}")
    lineas.append("")

    replies = data.get("replies")
    if isinstance(replies, dict):
        children = replies.get("data", {}).get("children", [])
        for child in children:
            lineas.append(comentario_json_a_md(child, profundidad + 1))

    return "\n".join(lineas)


def extraer_sin_credenciales(url: str) -> tuple[str, str, str]:
    base = normalizar_url(url)
    json_url = base + ".json"

    headers = {"User-Agent": USER_AGENT}
    resp = requests.get(json_url, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if not isinstance(data, list) or len(data) < 2:
        raise ValueError("Respuesta inesperada de Reddit. ¿Es una URL de hilo válida?")

    post_data = data[0]["data"]["children"][0]["data"]
    comments_listing = data[1]["data"]["children"]

    title = post_data.get("title", "Sin título")
    author = post_data.get("author") or "[eliminado]"
    score = post_data.get("score", 0)
    num_comments = post_data.get("num_comments", 0)
    created = post_data.get("created_utc", 0)
    subreddit = post_data.get("subreddit", "")
    selftext = post_data.get("selftext", "")
    is_self = post_data.get("is_self", True)
    post_url = post_data.get("url", "")
    post_id = post_data.get("id", "unknown")
    permalink = f"https://www.reddit.com{post_data.get('permalink', '')}"

    md = []
    md.append(f"# {title}\n")
    md.append(f"**Subreddit:** r/{subreddit}  ")
    md.append(f"**Autor:** u/{author}  ")
    md.append(f"**Puntuación:** {score}  ")
    md.append(f"**Comentarios:** {num_comments}  ")
    md.append(f"**Fecha:** {timestamp_a_str(created)}  ")
    md.append(f"**URL:** {permalink}\n")
    md.append("---\n")

    if selftext:
        md.append("## Post\n")
        md.append(escapar_markdown(selftext))
        md.append("\n---\n")
    elif post_url and not is_self:
        md.append("## Enlace\n")
        md.append(f"{post_url}\n")
        md.append("---\n")

    md.append("## Comentarios\n")
    md.append(
        "> *Modo sin credenciales: solo se incluyen los comentarios visibles "
        "en la primera carga (no se expanden los \"more comments\").*\n"
    )

    for child in comments_listing:
        md.append(comentario_json_a_md(child))

    md.append("\n---\n")
    md.append(
        f"*Extraído con [explorador-de-redit](https://github.com/robertosantosx2/explorador-de-redit) "
        f"(modo sin credenciales) · {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*"
    )

    markdown = "\n".join(md)
    filename = nombre_archivo_seguro(title, post_id)
    return markdown, filename, title


# ---------------------------------------------------------------------------
# Modo CON credenciales (PRAW)
# ---------------------------------------------------------------------------

def comentario_praw_a_md(comment, profundidad: int = 0) -> str:
    if praw is None or isinstance(comment, praw.models.MoreComments):
        return ""

    autor = str(comment.author) if comment.author else "[eliminado]"
    puntuacion = comment.score
    fecha = timestamp_a_str(comment.created_utc)
    cuerpo = escapar_markdown(comment.body)

    indent = "  " * profundidad
    lineas = [
        f"{indent}- **u/{autor}** ({puntuacion} pts) · {fecha}",
        f"{indent}  ",
    ]
    for linea in cuerpo.split("\n"):
        lineas.append(f"{indent}  {linea}")
    lineas.append("")

    for respuesta in comment.replies:
        lineas.append(comentario_praw_a_md(respuesta, profundidad + 1))

    return "\n".join(lineas)


def extraer_con_credenciales(
    url: str,
    client_id: str,
    client_secret: str,
    user_agent: str | None = None,
    max_more: int | None = 30,
) -> tuple[str, str, str]:
    if praw is None:
        raise RuntimeError("PRAW no está instalado. Ejecuta: pip install praw")

    ua = user_agent or USER_AGENT
    reddit = praw.Reddit(
        client_id=client_id.strip(),
        client_secret=client_secret.strip(),
        user_agent=ua.strip(),
    )

    submission = reddit.submission(url=normalizar_url(url))
    submission.comments.replace_more(limit=max_more)

    autor = str(submission.author) if submission.author else "[eliminado]"
    fecha = timestamp_a_str(submission.created_utc)
    subreddit = str(submission.subreddit)
    permalink = f"https://www.reddit.com{submission.permalink}"

    md = []
    md.append(f"# {submission.title}\n")
    md.append(f"**Subreddit:** r/{subreddit}  ")
    md.append(f"**Autor:** u/{autor}  ")
    md.append(f"**Puntuación:** {submission.score}  ")
    md.append(f"**Comentarios:** {submission.num_comments}  ")
    md.append(f"**Fecha:** {fecha}  ")
    md.append(f"**URL:** {permalink}\n")
    md.append("---\n")

    if submission.selftext:
        md.append("## Post\n")
        md.append(escapar_markdown(submission.selftext))
        md.append("\n---\n")
    elif submission.url and not submission.is_self:
        md.append("## Enlace\n")
        md.append(f"{submission.url}\n")
        md.append("---\n")

    md.append("## Comentarios\n")

    for top in submission.comments:
        md.append(comentario_praw_a_md(top))

    md.append("\n---\n")
    md.append(
        f"*Extraído con [explorador-de-redit](https://github.com/robertosantosx2/explorador-de-redit) "
        f"· {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*"
    )

    markdown = "\n".join(md)
    filename = nombre_archivo_seguro(submission.title, submission.id)
    return markdown, filename, submission.title


# ---------------------------------------------------------------------------
# Interfaz web
# ---------------------------------------------------------------------------

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Explorador de Reddit → Markdown</title>
  <style>
    :root {
      --bg: #0f1419;
      --card: #1a2332;
      --border: #2d3a4f;
      --text: #e7e9ea;
      --muted: #8b98a5;
      --accent: #1d9bf0;
      --accent-hover: #1a8cd8;
      --success: #00ba7c;
      --error: #f4212e;
      --warn: #ffad1f;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 2rem 1rem;
    }
    .container { width: 100%; max-width: 680px; }
    h1 {
      font-size: 1.75rem;
      font-weight: 700;
      margin-bottom: 0.35rem;
      letter-spacing: -0.02em;
    }
    .subtitle { color: var(--muted); font-size: 0.95rem; margin-bottom: 1.75rem; }
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 1.75rem;
      margin-bottom: 1.25rem;
    }
    label {
      display: block;
      font-size: 0.875rem;
      font-weight: 600;
      margin-bottom: 0.4rem;
    }
    input[type="text"], input[type="password"], input[type="url"], input[type="number"] {
      width: 100%;
      padding: 0.75rem 1rem;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 10px;
      color: var(--text);
      font-size: 0.95rem;
      margin-bottom: 1rem;
      transition: border-color 0.15s;
    }
    input:focus { outline: none; border-color: var(--accent); }
    .hint { font-size: 0.8rem; color: var(--muted); margin-top: -0.6rem; margin-bottom: 1rem; }
    .mode-toggle {
      display: flex;
      gap: 0.5rem;
      margin-bottom: 1.25rem;
      background: var(--bg);
      padding: 0.3rem;
      border-radius: 12px;
      border: 1px solid var(--border);
    }
    .mode-toggle label {
      flex: 1;
      text-align: center;
      padding: 0;
      border-radius: 9px;
      cursor: pointer;
      font-size: 0.9rem;
      font-weight: 600;
      color: var(--muted);
      margin: 0;
    }
    .mode-toggle input { display: none; }
    .mode-toggle input:checked + span {
      background: var(--accent);
      color: white;
    }
    .mode-toggle label span { display: block; padding: 0.6rem; border-radius: 9px; }
    details { margin-bottom: 1rem; }
    summary {
      cursor: pointer;
      font-size: 0.9rem;
      color: var(--muted);
      user-select: none;
    }
    summary:hover { color: var(--text); }
    .credentials { margin-top: 0.9rem; }
    .btn-row { display: flex; gap: 0.75rem; margin-top: 0.5rem; }
    button, .btn {
      flex: 1;
      padding: 0.85rem 1rem;
      border: none;
      border-radius: 9999px;
      font-size: 0.95rem;
      font-weight: 700;
      cursor: pointer;
      transition: background 0.15s, opacity 0.15s;
      text-align: center;
      text-decoration: none;
      display: inline-block;
    }
    .btn-primary { background: var(--accent); color: white; }
    .btn-primary:hover { background: var(--accent-hover); }
    .btn-secondary {
      background: transparent;
      color: var(--text);
      border: 1px solid var(--border);
    }
    .btn-secondary:hover { border-color: var(--muted); }
    .btn-danger {
      background: transparent;
      color: #ff8a8a;
      border: 1px solid var(--error);
      padding: 0.35rem 0.7rem;
      font-size: 0.75rem;
      border-radius: 8px;
      flex: none;
    }
    .btn-danger:hover { background: rgba(244,33,46,0.15); }
    button:disabled { opacity: 0.55; cursor: not-allowed; }
    .alert {
      padding: 0.9rem 1.1rem;
      border-radius: 10px;
      margin-bottom: 1.25rem;
      font-size: 0.9rem;
    }
    .alert-error {
      background: rgba(244, 33, 46, 0.15);
      border: 1px solid var(--error);
      color: #ff8a8a;
    }
    .alert-success {
      background: rgba(0, 186, 124, 0.15);
      border: 1px solid var(--success);
      color: #7dffc3;
    }
    .alert-warn {
      background: rgba(255, 173, 31, 0.12);
      border: 1px solid var(--warn);
      color: #ffd78a;
    }
    footer {
      margin-top: 1.5rem;
      text-align: center;
      font-size: 0.8rem;
      color: var(--muted);
    }
    footer a { color: var(--accent); text-decoration: none; }
    .spinner {
      display: inline-block;
      width: 1.05em;
      height: 1.05em;
      border: 2px solid rgba(255,255,255,0.3);
      border-top-color: white;
      border-radius: 50%;
      animation: spin 0.7s linear infinite;
      vertical-align: middle;
      margin-right: 0.45rem;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    .preview-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 0.75rem;
      gap: 0.75rem;
      flex-wrap: wrap;
    }
    .preview-header h2 { font-size: 1.1rem; }
    pre.preview {
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1rem;
      max-height: 420px;
      overflow: auto;
      font-size: 0.82rem;
      line-height: 1.45;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .hidden { display: none !important; }

    /* Historial */
    .history-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1rem;
    }
    .history-header h2 {
      font-size: 1.15rem;
      font-weight: 700;
    }
    .history-list { list-style: none; }
    .history-item {
      display: flex;
      gap: 0.75rem;
      align-items: flex-start;
      padding: 0.85rem 0;
      border-bottom: 1px solid var(--border);
    }
    .history-item:last-child { border-bottom: none; }
    .history-meta { flex: 1; min-width: 0; }
    .history-title {
      font-weight: 600;
      font-size: 0.92rem;
      margin-bottom: 0.25rem;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .history-title a { color: var(--text); text-decoration: none; }
    .history-title a:hover { color: var(--accent); }
    .history-sub {
      font-size: 0.78rem;
      color: var(--muted);
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
    }
    .badge {
      display: inline-block;
      padding: 0.1rem 0.45rem;
      border-radius: 6px;
      font-size: 0.72rem;
      font-weight: 600;
    }
    .badge-noauth {
      background: rgba(139, 152, 165, 0.2);
      color: var(--muted);
    }
    .badge-auth {
      background: rgba(29, 155, 240, 0.2);
      color: var(--accent);
    }
    .history-actions {
      display: flex;
      gap: 0.4rem;
      flex-shrink: 0;
    }
    .btn-sm {
      padding: 0.35rem 0.65rem;
      font-size: 0.75rem;
      border-radius: 8px;
      flex: none;
    }
    .empty-history {
      color: var(--muted);
      font-size: 0.9rem;
      text-align: center;
      padding: 1rem 0;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>Explorador de Reddit</h1>
    <p class="subtitle">Extrae un hilo completo a Markdown · con o sin credenciales</p>

    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for category, message in messages %}
          <div class="alert alert-{{ category }}">{{ message }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}

    <div class="card">
      <form method="POST" action="/" id="extract-form">
        <input type="hidden" name="action" id="action-field" value="download">

        <label for="url">URL del hilo de Reddit</label>
        <input type="url" id="url" name="url" required
               placeholder="https://www.reddit.com/r/subreddit/comments/ID/titulo/"
               value="{{ request.form.url or prefill_url or '' }}">

        <div class="mode-toggle">
          <label>
            <input type="radio" name="mode" value="noauth" id="mode-noauth"
                   {% if not request.form.mode or request.form.mode == 'noauth' %}checked{% endif %}>
            <span>Sin credenciales</span>
          </label>
          <label>
            <input type="radio" name="mode" value="auth" id="mode-auth"
                   {% if request.form.mode == 'auth' %}checked{% endif %}>
            <span>Con credenciales</span>
          </label>
        </div>

        <div id="auth-fields" class="{% if not request.form.mode or request.form.mode == 'noauth' %}hidden{% endif %}">
          <details open>
            <summary>Credenciales de Reddit (API)</summary>
            <div class="credentials">
              <label for="client_id">Client ID</label>
              <input type="text" id="client_id" name="client_id"
                     placeholder="Desde reddit.com/prefs/apps"
                     value="{{ request.form.client_id or '' }}">

              <label for="client_secret">Client Secret</label>
              <input type="password" id="client_secret" name="client_secret"
                     placeholder="••••••••••••"
                     value="{{ request.form.client_secret or '' }}">

              <label for="user_agent">User-Agent (opcional)</label>
              <input type="text" id="user_agent" name="user_agent"
                     placeholder="web:explorador-de-redit:v1.2 (by u/tu_usuario)"
                     value="{{ request.form.user_agent or '' }}">

              <label style="display:flex;align-items:center;gap:0.5rem;font-weight:500;margin-bottom:0.8rem;">
                <input type="checkbox" id="remember" style="width:auto;margin:0;">
                Recordar credenciales en este navegador
              </label>
            </div>
          </details>

          <label for="limit">Límite de "More Comments"</label>
          <input type="number" id="limit" name="limit" min="0" step="1"
                 placeholder="30"
                 value="{{ request.form.limit or '30' }}">
          <p class="hint">Solo aplica con credenciales. 30 es un buen equilibrio velocidad/completitud.</p>
        </div>

        <div class="btn-row">
          <button type="submit" class="btn-secondary" id="btn-preview"
                  onclick="document.getElementById('action-field').value='preview'">
            Previsualizar
          </button>
          <button type="submit" class="btn-primary" id="btn-download"
                  onclick="document.getElementById('action-field').value='download'">
            Descargar Markdown
          </button>
        </div>
      </form>
    </div>

    {% if preview_markdown %}
    <div class="card">
      <div class="preview-header">
        <h2>Previsualización</h2>
        <form method="POST" action="/download" style="margin:0;">
          <input type="hidden" name="markdown" value="{{ preview_markdown | e }}">
          <input type="hidden" name="filename" value="{{ preview_filename | e }}">
          <button type="submit" class="btn-primary btn-sm">Descargar este Markdown</button>
        </form>
      </div>
      <pre class="preview">{{ preview_markdown }}</pre>
    </div>
    {% endif %}

    <!-- Historial -->
    <div class="card">
      <div class="history-header">
        <h2>Historial</h2>
        {% if history %}
        <form method="POST" action="/history/clear" onsubmit="return confirm('¿Borrar todo el historial?');" style="margin:0;">
          <button type="submit" class="btn-danger">Vaciar</button>
        </form>
        {% endif %}
      </div>

      {% if history %}
      <ul class="history-list">
        {% for item in history %}
        <li class="history-item">
          <div class="history-meta">
            <div class="history-title">
              <a href="{{ item.url }}" target="_blank" title="{{ item.title }}">{{ item.title }}</a>
            </div>
            <div class="history-sub">
              <span class="badge badge-{{ item.mode }}">
                {{ 'API' if item.mode == 'auth' else 'Sin creds' }}
              </span>
              <span>{{ item.created_at[:16].replace('T', ' ') }} UTC</span>
            </div>
          </div>
          <div class="history-actions">
            <a class="btn btn-secondary btn-sm" href="/?url={{ item.url | urlencode }}">Reusar</a>
            <a class="btn btn-primary btn-sm" href="/history/{{ item.id }}/download">.md</a>
            <form method="POST" action="/history/{{ item.id }}/delete" style="margin:0;"
                  onsubmit="return confirm('¿Eliminar esta entrada?');">
              <button type="submit" class="btn-danger">✕</button>
            </form>
          </div>
        </li>
        {% endfor %}
      </ul>
      {% else %}
      <p class="empty-history">Aún no has explorado ningún hilo.</p>
      {% endif %}
    </div>

    <div class="alert alert-warn" style="font-size:0.85rem;">
      <strong>Sin credenciales:</strong> solo comentarios visibles (no expande “load more”).
      <br><strong>Con credenciales:</strong> extracción más completa. El historial se guarda en este equipo.
    </div>

    <footer>
      <a href="https://github.com/robertosantosx2/explorador-de-redit" target="_blank">Código en GitHub</a>
      · Las credenciales solo se usan en tu máquina
    </footer>
  </div>

  <script>
    const modeNoauth = document.getElementById('mode-noauth');
    const modeAuth = document.getElementById('mode-auth');
    const authFields = document.getElementById('auth-fields');

    function updateMode() {
      authFields.classList.toggle('hidden', modeNoauth.checked);
    }
    modeNoauth.addEventListener('change', updateMode);
    modeAuth.addEventListener('change', updateMode);
    updateMode();

    const LS_KEY = 'explorador_reddit_creds';
    const clientId = document.getElementById('client_id');
    const clientSecret = document.getElementById('client_secret');
    const userAgent = document.getElementById('user_agent');
    const remember = document.getElementById('remember');

    try {
      const saved = JSON.parse(localStorage.getItem(LS_KEY) || 'null');
      if (saved) {
        if (saved.client_id) clientId.value = saved.client_id;
        if (saved.client_secret) clientSecret.value = saved.client_secret;
        if (saved.user_agent) userAgent.value = saved.user_agent;
        remember.checked = true;
      }
    } catch (e) {}

    document.getElementById('extract-form').addEventListener('submit', function () {
      if (remember.checked && modeAuth.checked) {
        localStorage.setItem(LS_KEY, JSON.stringify({
          client_id: clientId.value,
          client_secret: clientSecret.value,
          user_agent: userAgent.value
        }));
      } else if (!remember.checked) {
        localStorage.removeItem(LS_KEY);
      }

      const isPreview = document.getElementById('action-field').value === 'preview';
      const btn = isPreview ? document.getElementById('btn-preview') : document.getElementById('btn-download');
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner"></span> Extrayendo...';
      document.getElementById('btn-preview').disabled = true;
      document.getElementById('btn-download').disabled = true;
    });
  </script>
</body>
</html>
"""


def render_page(**kwargs):
    history = cargar_historial()
    return render_template_string(
        HTML_TEMPLATE,
        history=history,
        preview_markdown=kwargs.get("preview_markdown"),
        preview_filename=kwargs.get("preview_filename"),
        prefill_url=kwargs.get("prefill_url"),
    )


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        prefill = request.args.get("url", "")
        return render_page(prefill_url=prefill)

    url = request.form.get("url", "").strip()
    mode = request.form.get("mode", "noauth")
    action = request.form.get("action", "download")

    if not url:
        flash("Introduce la URL del hilo.", "error")
        return render_page(), 400

    try:
        if mode == "auth":
            client_id = request.form.get("client_id", "").strip()
            client_secret = request.form.get("client_secret", "").strip()
            user_agent = request.form.get("user_agent", "").strip() or None
            limit_raw = request.form.get("limit", "").strip()

            if not client_id or not client_secret:
                flash("En modo con credenciales necesitas Client ID y Client Secret.", "error")
                return render_page(), 400

            max_more = 30
            if limit_raw:
                try:
                    max_more = int(limit_raw)
                    if max_more < 0:
                        max_more = 0
                except ValueError:
                    flash("El límite debe ser un número entero.", "error")
                    return render_page(), 400

            markdown, filename, title = extraer_con_credenciales(
                url, client_id, client_secret, user_agent, max_more
            )
        else:
            markdown, filename, title = extraer_sin_credenciales(url)

        # Guardar en historial
        anadir_al_historial(
            url=normalizar_url(url),
            title=title,
            filename=filename,
            mode=mode,
            markdown=markdown,
        )

    except Exception as e:
        flash(f"Error al extraer el hilo: {str(e)}", "error")
        return render_page(), 500

    if action == "preview":
        return render_page(preview_markdown=markdown, preview_filename=filename)

    buffer = io.BytesIO(markdown.encode("utf-8"))
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="text/markdown; charset=utf-8",
    )


@app.route("/download", methods=["POST"])
def download_preview():
    markdown = request.form.get("markdown", "")
    filename = request.form.get("filename", "reddit_thread.md")
    if not markdown:
        flash("No hay contenido para descargar.", "error")
        return render_page(), 400

    buffer = io.BytesIO(markdown.encode("utf-8"))
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="text/markdown; charset=utf-8",
    )


@app.route("/history/<entry_id>/download")
def history_download(entry_id):
    entry = obtener_entrada(entry_id)
    if not entry:
        flash("Entrada no encontrada en el historial.", "error")
        return redirect(url_for("index"))

    md_path = HISTORY_MD_DIR / entry.get("md_file", f"{entry_id}.md")
    if not md_path.exists():
        flash("El archivo Markdown de esta entrada ya no existe.", "error")
        return redirect(url_for("index"))

    return send_file(
        md_path,
        as_attachment=True,
        download_name=entry.get("filename", f"{entry_id}.md"),
        mimetype="text/markdown; charset=utf-8",
    )


@app.route("/history/<entry_id>/delete", methods=["POST"])
def history_delete(entry_id):
    if eliminar_entrada(entry_id):
        flash("Entrada eliminada del historial.", "success")
    else:
        flash("No se pudo eliminar la entrada.", "error")
    return redirect(url_for("index"))


@app.route("/history/clear", methods=["POST"])
def history_clear():
    guardar_historial([])
    for f in HISTORY_MD_DIR.glob("*.md"):
        try:
            f.unlink()
        except OSError:
            pass
    flash("Historial vaciado.", "success")
    return redirect(url_for("index"))


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "1") == "1"
    print(f"\n🚀 Interfaz lista → http://127.0.0.1:{port}\n")
    print("   · Historial guardado en history.json + history_md/\n")
    app.run(host="0.0.0.0", port=port, debug=debug)
