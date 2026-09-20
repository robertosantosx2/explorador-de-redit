# explorador-de-redit

Extrae **hilos completos** de Reddit (post + todos los comentarios anidados) y los convierte en un archivo **Markdown** descargable.

Disponible en dos modos:

1. **Interfaz web** (recomendada) – introduce la URL y descarga el `.md`
2. **Script de terminal** – para automatización o uso avanzado

---

## Interfaz web (más fácil)

### Instalación rápida

```bash
git clone https://github.com/robertosantosx2/explorador-de-redit.git
cd explorador-de-redit

python -m venv .venv
source .venv/bin/activate          # Linux / macOS
# .venv\Scripts\activate           # Windows

pip install -r requirements.txt
```

### Ejecutar la web

```bash
python app.py
```

Abre el navegador en: **http://127.0.0.1:5000**

1. Pega la URL del hilo de Reddit
2. Introduce tus **Client ID** y **Client Secret** (se obtienen gratis en [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) creando una app de tipo **script**)
3. Pulsa **Extraer y descargar Markdown**

El archivo `.md` se descargará automáticamente.

> **Nota de seguridad**: las credenciales solo se usan en tu máquina y no se guardan en ningún sitio.

---

## Cómo obtener las credenciales de Reddit

1. Entra en [https://www.reddit.com/prefs/apps](https://www.reddit.com/prefs/apps)
2. Pulsa **“Create App”** o **“Create Another App”**
3. Rellena:
   - **Name**: cualquier nombre (ej. `explorador-de-redit`)
   - **Type**: **script**
   - **Redirect URI**: `http://localhost:8080`
4. Copia el **client_id** (aparece debajo del nombre de la app) y el **secret**

---

## Script de terminal (CLI)

También puedes usar el script clásico:

```bash
# Configura las variables de entorno o un archivo .env
cp .env.example .env
# Edita .env con tus credenciales

python reddit_to_markdown.py "https://www.reddit.com/r/subreddit/comments/ID/titulo/"

# Opciones útiles
python reddit_to_markdown.py "URL" -o salida.md
python reddit_to_markdown.py "URL" --limit 20
```

---

## Estructura del proyecto

```
explorador-de-redit/
├── app.py                  # Interfaz web (Flask)
├── reddit_to_markdown.py   # Script CLI
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Notas

- En hilos con miles de comentarios la extracción puede tardar un poco. Usa el campo **Límite de "More Comments"** (por defecto 30) para acelerar.
- El Markdown generado incluye título, autor, puntuación, fecha, cuerpo del post y todo el árbol de comentarios con indentación.
- Las credenciales nunca se almacenan; solo se usan durante la petición.

## Licencia

AGPL-3.0
