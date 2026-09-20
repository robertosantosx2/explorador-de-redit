#!/usr/bin/env python3
"""
Interfaz web sencilla para explorador-de-redit
Permite introducir la URL de un hilo de Reddit y descargar el Markdown resultante.
"""

import io
import os
from datetime import datetime, timezone
from flask import Flask, request, render_template_string, send_file, flash, redirect, url_for

try:
    import praw
except ImportError:
    raise SystemExit("Instala las dependencias: pip install -r requirements.txt")

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "explorador-de-redit-dev-key-cambia-esto")

# ---------------------------------------------------------------------------
# Lógica de extracción (reutilizada del script CLI)
# ---------------------------------------------------------------------------

def timestamp_a_str(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def escapar_markdown(texto: str) -> str:
    if not texto:
        return ""
    return texto.replace("\r\n", "\n").strip()


def comentario_a_markdown(comment, profundidad: int = 0) -> str:
    if isinstance(comment, praw.models.MoreComments):
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
        lineas.append(comentario_a_markdown(respuesta, profundidad + 1))

    return "\n".join(lineas)


def hilo_a_markdown(submission, max_more: int | None = 30) -> str:
    """Convierte un submission a Markdown. Por defecto limita a 30 'More Comments'."""
    submission.comments.replace_more(limit=max_more)

    autor = str(submission.author) if submission.author else "[eliminado]"
    fecha = timestamp_a_str(submission.created_utc)
    subreddit = str(submission.subreddit)
    url = f"https://www.reddit.com{submission.permalink}"

    md = []
    md.append(f"# {submission.title}\n")
    md.append(f"**Subreddit:** r/{subreddit}  ")
    md.append(f"**Autor:** u/{autor}  ")
    md.append(f"**Puntuación:** {submission.score}  ")
    md.append(f"**Comentarios:** {submission.num_comments}  ")
    md.append(f"**Fecha:** {fecha}  ")
    md.append(f"**URL:** {url}\n")
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

    for top_comment in submission.comments:
        md.append(comentario_a_markdown(top_comment))

    md.append("\n---\n")
    md.append(
        f"*Extraído con [explorador-de-redit](https://github.com/robertosantosx2/explorador-de-redit) "
        f"· {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*"
    )

    return "\n".join(md)


def crear_reddit(client_id: str, client_secret: str, user_agent: str | None = None):
    if not user_agent:
        user_agent = "web:explorador-de-redit:v1.0 (by u/usuario)"
    return praw.Reddit(
        client_id=client_id.strip(),
        client_secret=client_secret.strip(),
        user_agent=user_agent.strip(),
    )


# ---------------------------------------------------------------------------
# Interfaz web
# ---------------------------------------------------------------------------

HTML_TEMPLATE = """
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
    .container {
      width: 100%;
      max-width: 560px;
    }
    h1 {
      font-size: 1.75rem;
      font-weight: 700;
      margin-bottom: 0.35rem;
      letter-spacing: -0.02em;
    }
    .subtitle {
      color: var(--muted);
      font-size: 0.95rem;
      margin-bottom: 2rem;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 1.75rem;
      margin-bottom: 1.5rem;
    }
    label {
      display: block;
      font-size: 0.875rem;
      font-weight: 600;
      margin-bottom: 0.4rem;
      color: var(--text);
    }
    input[type="text"], input[type="password"], input[type="url"] {
      width: 100%;
      padding: 0.75rem 1rem;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 10px;
      color: var(--text);
      font-size: 0.95rem;
      margin-bottom: 1.1rem;
      transition: border-color 0.15s;
    }
    input:focus {
      outline: none;
      border-color: var(--accent);
    }
    .hint {
      font-size: 0.8rem;
      color: var(--muted);
      margin-top: -0.7rem;
      margin-bottom: 1.1rem;
    }
    details {
      margin-bottom: 1.25rem;
    }
    summary {
      cursor: pointer;
      font-size: 0.9rem;
      color: var(--muted);
      user-select: none;
    }
    summary:hover { color: var(--text); }
    .credentials {
      margin-top: 1rem;
      padding-top: 0.5rem;
    }
    button {
      width: 100%;
      padding: 0.85rem 1.25rem;
      background: var(--accent);
      color: white;
      border: none;
      border-radius: 9999px;
      font-size: 1rem;
      font-weight: 700;
      cursor: pointer;
      transition: background 0.15s;
    }
    button:hover { background: var(--accent-hover); }
    button:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }
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
    footer {
      margin-top: 2rem;
      text-align: center;
      font-size: 0.8rem;
      color: var(--muted);
    }
    footer a { color: var(--accent); text-decoration: none; }
    .spinner {
      display: inline-block;
      width: 1.1em;
      height: 1.1em;
      border: 2px solid rgba(255,255,255,0.3);
      border-top-color: white;
      border-radius: 50%;
      animation: spin 0.7s linear infinite;
      vertical-align: middle;
      margin-right: 0.5rem;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
  </style>
</head>
<body>
  <div class="container">
    <h1>Explorador de Reddit</h1>
    <p class="subtitle">Extrae un hilo completo a Markdown descargable</p>

    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for category, message in messages %}
          <div class="alert alert-{{ category }}">{{ message }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}

    <div class="card">
      <form method="POST" action="/" id="extract-form">
        <label for="url">URL del hilo de Reddit</label>
        <input type="url" id="url" name="url" required
               placeholder="https://www.reddit.com/r/subreddit/comments/ID/titulo/"
               value="{{ request.form.url or '' }}">

        <details>
          <summary>Credenciales de Reddit (necesarias)</summary>
          <div class="credentials">
            <label for="client_id">Client ID</label>
            <input type="text" id="client_id" name="client_id" required
                   placeholder="Obtenido en reddit.com/prefs/apps"
                   value="{{ request.form.client_id or '' }}">

            <label for="client_secret">Client Secret</label>
            <input type="password" id="client_secret" name="client_secret" required
                   placeholder="••••••••••••">

            <label for="user_agent">User-Agent (opcional)</label>
            <input type="text" id="user_agent" name="user_agent"
                   placeholder="web:explorador-de-redit:v1.0 (by u/tu_usuario)"
                   value="{{ request.form.user_agent or '' }}">
            <p class="hint">Si lo dejas vacío se usa uno por defecto.</p>
          </div>
        </details>

        <label for="limit">Límite de "More Comments" (opcional)</label>
        <input type="text" id="limit" name="limit"
               placeholder="30 (recomendado). Deja vacío para intentar todos"
               value="{{ request.form.limit or '30' }}">
        <p class="hint">En hilos muy grandes un límite bajo es más rápido.</p>

        <button type="submit" id="btn">Extraer y descargar Markdown</button>
      </form>
    </div>

    <footer>
      <a href="https://github.com/robertosantosx2/explorador-de-redit" target="_blank">Código en GitHub</a>
      · Creado con ❤️ para extraer hilos de Reddit
    </footer>
  </div>

  <script>
    document.getElementById('extract-form').addEventListener('submit', function() {
      const btn = document.getElementById('btn');
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner"></span> Extrayendo hilo... (puede tardar)';
    });
  </script>
</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return render_template_string(HTML_TEMPLATE)

    url = request.form.get("url", "").strip()
    client_id = request.form.get("client_id", "").strip()
    client_secret = request.form.get("client_secret", "").strip()
    user_agent = request.form.get("user_agent", "").strip() or None
    limit_raw = request.form.get("limit", "").strip()

    if not url or not client_id or not client_secret:
        flash("Faltan campos obligatorios (URL, Client ID y Client Secret).", "error")
        return render_template_string(HTML_TEMPLATE), 400

    max_more = None
    if limit_raw:
        try:
            max_more = int(limit_raw)
            if max_more < 0:
                max_more = 0
        except ValueError:
            flash("El límite debe ser un número entero.", "error")
            return render_template_string(HTML_TEMPLATE), 400

    try:
        reddit = crear_reddit(client_id, client_secret, user_agent)
        submission = reddit.submission(url=url)
        markdown = hilo_a_markdown(submission, max_more=max_more)
    except Exception as e:
        flash(f"Error al extraer el hilo: {str(e)}", "error")
        return render_template_string(HTML_TEMPLATE), 500

    # Generar nombre de archivo seguro
    safe_title = "".join(c if c.isalnum() or c in "-_ " else "" for c in submission.title)[:50]
    safe_title = safe_title.strip().replace(" ", "_") or submission.id
    filename = f"{submission.id}_{safe_title}.md"

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
    app.run(host="0.0.0.0", port=port, debug=debug)
