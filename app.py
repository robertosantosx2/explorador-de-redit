#!/usr/bin/env python3
"""
Interfaz web para explorador-de-redit
- Extrae hilos de Reddit a Markdown descargable
- Funciona CON o SIN credenciales
- Guarda credenciales en localStorage del navegador
- Permite previsualizar el Markdown antes de descargar
"""

import io
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from flask import Flask, request, render_template_string, send_file, flash, session

try:
    import praw
except ImportError:
    praw = None

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "explorador-de-redit-dev-key-cambia-esto")

USER_AGENT = "web:explorador-de-redit:v1.1 (by u/usuario)"


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
    """Asegura que la URL sea usable y añade .json si hace falta."""
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    # Quitar parámetros y trailing slash extra
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
# Modo SIN credenciales (endpoint público .json)
# ---------------------------------------------------------------------------

def comentario_json_a_md(node: dict, profundidad: int = 0) -> str:
    """Convierte un nodo de comentario del JSON público a Markdown."""
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
    """
    Extrae usando el endpoint público .json.
    Devuelve (markdown, filename, titulo).
    Limitación: no expande los 'more comments' ocultos.
    """
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
    md.append("> *Modo sin credenciales: solo se incluyen los comentarios visibles en la primera carga (no se expanden los \"more comments\").*
")

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
# Modo CON credenciales (PRAW – más completo)
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
    .container { width: 100%; max-width: 640px; }
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
      padding: 0.6rem;
      border-radius: 9px;
      cursor: pointer;
      font-size: 0.9rem;
      font-weight: 600;
      color: var(--muted);
      margin: 0;
      transition: all 0.15s;
    }
    .mode-toggle input { display: none; }
    .mode-toggle input:checked + span {
      background: var(--accent);
      color: white;
      display: block;
      padding: 0.6rem;
      border-radius: 9px;
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
    #preview-box {
      display: none;
      margin-top: 1.25rem;
    }
    #preview-box.visible { display: block; }
    .preview-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 0.75rem;
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
               value="{{ request.form.url or '' }}">

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
                     placeholder="web:explorador-de-redit:v1.1 (by u/tu_usuario)"
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
    <div class="card" id="preview-box" class="visible">
      <div class="preview-header">
        <h2>Previsualización</h2>
        <form method="POST" action="/download" style="margin:0;">
          <input type="hidden" name="markdown" value="{{ preview_markdown | e }}">
          <input type="hidden" name="filename" value="{{ preview_filename | e }}">
          <button type="submit" class="btn-primary" style="width:auto;padding:0.5rem 1.1rem;font-size:0.85rem;">
            Descargar este Markdown
          </button>
        </form>
      </div>
      <pre class="preview">{{ preview_markdown }}</pre>
    </div>
    {% endif %}

    <div class="alert alert-warn" style="font-size:0.85rem;">
      <strong>Sin credenciales:</strong> usa el endpoint público de Reddit. Es más rápido de probar,
      pero no expande los comentarios ocultos (“load more”).
      <br><strong>Con credenciales:</strong> obtiene muchos más comentarios (recomendado para hilos grandes).
    </div>

    <footer>
      <a href="https://github.com/robertosantosx2/explorador-de-redit" target="_blank">Código en GitHub</a>
      · Las credenciales solo se usan en tu máquina
    </footer>
  </div>

  <script>
    // Toggle campos de autenticación
    const modeNoauth = document.getElementById('mode-noauth');
    const modeAuth = document.getElementById('mode-auth');
    const authFields = document.getElementById('auth-fields');

    function updateMode() {
      authFields.classList.toggle('hidden', modeNoauth.checked);
    }
    modeNoauth.addEventListener('change', updateMode);
    modeAuth.addEventListener('change', updateMode);
    updateMode();

    // localStorage para credenciales
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


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return render_template_string(HTML_TEMPLATE, preview_markdown=None)

    url = request.form.get("url", "").strip()
    mode = request.form.get("mode", "noauth")
    action = request.form.get("action", "download")  # download | preview

    if not url:
        flash("Introduce la URL del hilo.", "error")
        return render_template_string(HTML_TEMPLATE, preview_markdown=None), 400

    try:
        if mode == "auth":
            client_id = request.form.get("client_id", "").strip()
            client_secret = request.form.get("client_secret", "").strip()
            user_agent = request.form.get("user_agent", "").strip() or None
            limit_raw = request.form.get("limit", "").strip()

            if not client_id or not client_secret:
                flash("En modo con credenciales necesitas Client ID y Client Secret.", "error")
                return render_template_string(HTML_TEMPLATE, preview_markdown=None), 400

            max_more = 30
            if limit_raw:
                try:
                    max_more = int(limit_raw)
                    if max_more < 0:
                        max_more = 0
                except ValueError:
                    flash("El límite debe ser un número entero.", "error")
                    return render_template_string(HTML_TEMPLATE, preview_markdown=None), 400

            markdown, filename, title = extraer_con_credenciales(
                url, client_id, client_secret, user_agent, max_more
            )
        else:
            markdown, filename, title = extraer_sin_credenciales(url)

    except Exception as e:
        flash(f"Error al extraer el hilo: {str(e)}", "error")
        return render_template_string(HTML_TEMPLATE, preview_markdown=None), 500

    if action == "preview":
        return render_template_string(
            HTML_TEMPLATE,
            preview_markdown=markdown,
            preview_filename=filename,
        )

    # Descarga directa
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
    """Descarga el Markdown que se estaba previsualizando."""
    markdown = request.form.get("markdown", "")
    filename = request.form.get("filename", "reddit_thread.md")
    if not markdown:
        flash("No hay contenido para descargar.", "error")
        return render_template_string(HTML_TEMPLATE, preview_markdown=None), 400

    buffer = io.BytesIO(markdown.encode("utf-8"))
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="text/markdown; charset=utf-8",
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "1") == "1"
    print(f"\n🚀 Interfaz lista → http://127.0.0.1:{port}\n")
    print("   • Sin credenciales: modo rápido (comentarios visibles)")
    print("   • Con credenciales: extracción más completa\n")
    app.run(host="0.0.0.0", port=port, debug=debug)
