#!/usr/bin/env python3
"""
explorador-de-redit
Extrae un hilo completo de Reddit (post + todos los comentarios) y lo guarda en Markdown.

Uso:
    python reddit_to_markdown.py "https://www.reddit.com/r/subreddit/comments/ID/titulo/"
    python reddit_to_markdown.py "https://www.reddit.com/r/subreddit/comments/ID/titulo/" -o salida.md
    python reddit_to_markdown.py "https://www.reddit.com/r/subreddit/comments/ID/titulo/" --limit 20
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import praw
except ImportError:
    print("Error: falta la librería praw.")
    print("Instálala con:  pip install praw")
    sys.exit(1)


def crear_reddit():
    """Crea la instancia de Reddit usando variables de entorno o valores por defecto."""
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv(
        "REDDIT_USER_AGENT",
        "script:explorador-de-redit:v1.0 (by u/robertosantosx2)",
    )

    if not client_id or not client_secret:
        print(
            "Error: faltan las credenciales de Reddit.\n"
            "Crea un archivo .env o exporta las variables:\n"
            "  REDDIT_CLIENT_ID=tu_client_id\n"
            "  REDDIT_CLIENT_SECRET=tu_client_secret\n"
            "\nCómo obtenerlas:\n"
            "1. Ve a https://www.reddit.com/prefs/apps\n"
            "2. Crea una app de tipo 'script'\n"
            "3. Copia el client_id y client_secret"
        )
        sys.exit(1)

    return praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent,
    )


def timestamp_a_str(ts: float) -> str:
    """Convierte timestamp UTC a string legible."""
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def escapar_markdown(texto: str) -> str:
    """Escapa caracteres problemáticos para Markdown."""
    if not texto:
        return ""
    # Evita que se rompa el formato
    return texto.replace("\r\n", "\n").strip()


def comentario_a_markdown(comment, profundidad: int = 0) -> str:
    """Convierte un comentario (y sus respuestas) a Markdown con indentación."""
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

    # Cuerpo del comentario (indentado)
    for linea in cuerpo.split("\n"):
        lineas.append(f"{indent}  {linea}")

    lineas.append("")  # línea en blanco

    # Respuestas anidadas
    for respuesta in comment.replies:
        lineas.append(comentario_a_markdown(respuesta, profundidad + 1))

    return "\n".join(lineas)


def hilo_a_markdown(submission, max_more: int | None = None) -> str:
    """Convierte un submission completo a un documento Markdown."""
    # Expandir "More Comments"
    print("Cargando comentarios (esto puede tardar en hilos grandes)...")
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

    # Cuerpo del post
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
    md.append(f"*Extraído con [explorador-de-redit](https://github.com/robertosantosx2/explorador-de-redit) · {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*")

    return "\n".join(md)


def main():
    parser = argparse.ArgumentParser(
        description="Extrae un hilo completo de Reddit a Markdown",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python reddit_to_markdown.py "https://www.reddit.com/r/AskReddit/comments/abc123/titulo/"
  python reddit_to_markdown.py "https://www.reddit.com/r/python/comments/xyz/" -o hilo.md
  python reddit_to_markdown.py "URL" --limit 15   # limita la expansión de "More Comments"
        """,
    )
    parser.add_argument("url", help="URL completa del hilo de Reddit")
    parser.add_argument(
        "-o",
        "--output",
        help="Archivo de salida (.md). Por defecto se genera automáticamente.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Máximo de 'More Comments' a expandir (None = todos). Útil en hilos enormes.",
    )

    args = parser.parse_args()

    reddit = crear_reddit()

    try:
        submission = reddit.submission(url=args.url)
    except Exception as e:
        print(f"Error al obtener el hilo: {e}")
        sys.exit(1)

    markdown = hilo_a_markdown(submission, max_more=args.limit)

    # Nombre de archivo por defecto
    if args.output:
        output_path = Path(args.output)
    else:
        safe_title = "".join(c if c.isalnum() or c in "-_ " else "" for c in submission.title)[:60]
        safe_title = safe_title.strip().replace(" ", "_") or submission.id
        output_path = Path(f"{submission.id}_{safe_title}.md")

    output_path.write_text(markdown, encoding="utf-8")
    print(f"✅ Hilo guardado en: {output_path.resolve()}")
    print(f"   Título: {submission.title}")
    print(f"   Comentarios cargados: {len(submission.comments.list())}")


if __name__ == "__main__":
    main()
