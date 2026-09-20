# explorador-de-redit

Extrae **hilos completos** de Reddit (post + comentarios) y los convierte en un archivo **Markdown** descargable.

## Características

- **Interfaz web** moderna y sencilla
- Funciona **con o sin credenciales**
- Previsualización del Markdown antes de descargar
- Guarda las credenciales en el navegador (localStorage) si lo deseas
- Script CLI también disponible

---

## Uso rápido (interfaz web)

```bash
git clone https://github.com/robertosantosx2/explorador-de-redit.git
cd explorador-de-redit

python -m venv .venv
source .venv/bin/activate          # Linux / macOS
# .venv\Scripts\activate           # Windows

pip install -r requirements.txt
python app.py
```

Abre **http://127.0.0.1:5000**

### Dos modos de extracción

| Modo | Credenciales | Ventajas | Limitaciones |
|------|--------------|----------|--------------|
| **Sin credenciales** | No | Instantáneo de probar | Solo comentarios visibles (no expande “load more”) |
| **Con credenciales** | Sí (API gratuita) | Muchos más comentarios | Hay que crear una app en Reddit |

### Cómo obtener credenciales (opcional pero recomendado)

1. Ve a [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps)
2. **Create App** → tipo **script**
3. Redirect URI: `http://localhost:8080`
4. Copia el **client_id** y el **secret**

En la web marca “Recordar credenciales” y no tendrás que escribirlas cada vez.

---

## Script de terminal

```bash
cp .env.example .env   # rellena tus credenciales
python reddit_to_markdown.py "https://www.reddit.com/r/.../comments/.../"
```

---

## Estructura

```
explorador-de-redit/
├── app.py                  # Interfaz web (Flask)
├── reddit_to_markdown.py   # Script CLI
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Licencia

AGPL-3.0
