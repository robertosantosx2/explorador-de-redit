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

    md_path = HISTORY_MD_DIR / f"{entry_id}.md"
    md_path.write_text(markdown, encoding="utf-8")

    entry = {
        "id": entry_id,
        "url": url,
        "title": title,
        "filename": filename,
        "mode": mode,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "md_file": str(md_path.name),
    }

    entries = [e for e in entries if e.get("url") != url]
    entries.insert(0, entry)
    entries = entries[:MAX_HISTORY]

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


def load_template() -> str:
    """Carga la plantilla HTML desde templates/index.html."""
    p = Path(__file__).parent / "templates" / "index.html"
    return p.read_text(encoding="utf-8")


def render_page(**kwargs):
    history = cargar_historial()
    return render_template_string(
        load_template(),
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
