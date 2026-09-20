# explorador-de-redit

Script para extraer **hilos completos** de Reddit (post + todos los comentarios anidados) y guardarlos en un archivo **Markdown** limpio y legible.

## Características

- Extrae el post original + **todo el árbol de comentarios**
- Formato Markdown bien estructurado (con indentación de respuestas)
- Incluye autor, puntuación, fecha y enlace original
- Opción para limitar la profundidad de "More Comments" en hilos enormes
- Fácil de usar desde la terminal

## Requisitos

- Python 3.9+
- Credenciales de la API de Reddit (gratuitas)

## Instalación

```bash
git clone https://github.com/robertosantosx2/explorador-de-redit.git
cd explorador-de-redit

# Crear entorno virtual (recomendado)
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows

pip install -r requirements.txt
```

## Configuración de credenciales

1. Ve a [https://www.reddit.com/prefs/apps](https://www.reddit.com/prefs/apps)
2. Haz clic en **"Create App"** o **"Create Another App"**
3. Rellena:
   - **Name**: explorador-de-redit (o el que quieras)
   - **Type**: **script**
   - **Redirect URI**: `http://localhost:8080`
4. Copia el **client_id** (aparece debajo del nombre) y el **client_secret**

Crea un archivo `.env` en la raíz del proyecto:

```bash
cp .env.example .env
```

Edita `.env` y pega tus datos:

```env
REDDIT_CLIENT_ID=tu_client_id
REDDIT_CLIENT_SECRET=tu_client_secret
REDDIT_USER_AGENT=script:explorador-de-redit:v1.0 (by u/tu_usuario)
```

## Uso

```bash
# Uso básico (genera el archivo automáticamente)
python reddit_to_markdown.py "https://www.reddit.com/r/AskReddit/comments/abc123/titulo_del_post/"

# Especificar nombre de salida
python reddit_to_markdown.py "URL_DEL_HILO" -o mi_hilo.md

# Limitar la expansión de comentarios ocultos (útil en hilos muy grandes)
python reddit_to_markdown.py "URL_DEL_HILO" --limit 20
```

### Ejemplo de salida

```markdown
# Título del post

**Subreddit:** r/ejemplo  
**Autor:** u/usuario  
**Puntuación:** 1520  
**Comentarios:** 87  
**Fecha:** 2025-03-15 14:22 UTC  
**URL:** https://www.reddit.com/r/ejemplo/comments/...

---

## Post

Texto original del post...

---

## Comentarios

- **u/comentario1** (342 pts) · 2025-03-15 14:30 UTC
  
  Texto del comentario...

  - **u/respuesta** (45 pts) · 2025-03-15 15:01 UTC
    
    Respuesta anidada...
```

## Notas

- En hilos con **miles de comentarios**, `replace_more(limit=None)` puede tardar varios minutos.
- Usa `--limit 10` o `--limit 20` si solo necesitas los comentarios más visibles.
- El script respeta los rate limits de Reddit.

## Licencia

AGPL-3.0
