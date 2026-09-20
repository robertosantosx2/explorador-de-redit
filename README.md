# explorador-de-redit

Extrae **hilos completos** de Reddit (post + comentarios) y los convierte en un archivo **Markdown** descargable.

## Características

- Interfaz web moderna
- Funciona **con o sin credenciales**
- Previsualización del Markdown
- Guarda credenciales en el navegador (opcional)
- **Historial de hilos explorados** (persistente en tu equipo)
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

### Historial

Cada hilo que extraes (previsualización o descarga) se guarda automáticamente:

- Título, URL, fecha y modo usado
- Puedes **re-descargar** el `.md` sin volver a pedir datos a Reddit
- Botón **Reusar** para cargar la URL otra vez en el formulario
- Eliminar entradas individuales o vaciar todo el historial

Los datos se guardan en `history.json` y los Markdown en la carpeta `history_md/` (ambos ignorados por git).

### Dos modos de extracción

| Modo | Credenciales | Ventajas | Limitaciones |
|------|--------------|----------|--------------|
| **Sin credenciales** | No | Instantáneo de probar | Solo comentarios visibles |
| **Con credenciales** | Sí (API gratuita) | Muchos más comentarios | Hay que crear una app en Reddit |

### Credenciales (opcional)

1. [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) → Create App → tipo **script**
2. Redirect URI: `http://localhost:8080`
3. Copia client_id y secret

---

## Script de terminal

```bash
cp .env.example .env
python reddit_to_markdown.py "https://www.reddit.com/r/.../comments/.../"
```

## Licencia

AGPL-3.0
