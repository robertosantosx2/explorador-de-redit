# explorador-de-redit

Herramienta para **extraer hilos completos de Reddit** (el post original + los comentarios) y guardarlos en un archivo **Markdown** limpio y legible.

Puedes usarla de dos formas:

1. **Interfaz web** (recomendada) — abres el navegador, pegas la URL y descargas el `.md`
2. **Script de terminal (CLI)** — útil para automatizar o usar desde scripts

---

## Índice

1. [Qué hace esta aplicación](#qué-hace-esta-aplicación)
2. [Requisitos previos](#requisitos-previos)
3. [Instalación paso a paso](#instalación-paso-a-paso)
4. [Obtener credenciales de Reddit (opcional pero recomendado)](#obtener-credenciales-de-reddit-opcional-pero-recomendado)
5. [Usar la interfaz web](#usar-la-interfaz-web)
6. [Usar el script de terminal (CLI)](#usar-el-script-de-terminal-cli)
7. [Historial de hilos](#historial-de-hilos)
8. [Modos de extracción](#modos-de-extracción)
9. [Estructura del proyecto](#estructura-del-proyecto)
10. [Solución de problemas](#solución-de-problemas)
11. [Licencia](#licencia)

---

## Qué hace esta aplicación

Dada la URL de un hilo de Reddit, la aplicación:

- Lee el **título**, autor, puntuación, fecha y texto del post
- Recorre el **árbol de comentarios** (respuestas anidadas)
- Genera un archivo **Markdown** bien formateado
- Te permite **previsualizarlo** o **descargarlo**
- Guarda un **historial** de los hilos que has explorado para poder re-descargarlos después

---

## Requisitos previos

Antes de empezar necesitas:

| Requisito | Detalle |
|-----------|--------|
| **Python** | Versión **3.9 o superior** |
| **pip** | Viene incluido con Python normalmente |
| **Git** | Para clonar el repositorio (opcional si descargas el ZIP) |
| **Navegador** | Chrome, Firefox, Edge, etc. (solo para la interfaz web) |
| **Cuenta de Reddit** | Solo si quieres el modo con credenciales (gratuita) |

### Comprobar si tienes Python instalado

Abre una terminal (PowerShell en Windows, Terminal en macOS/Linux) y escribe:

```bash
python --version
```

o, en algunos sistemas:

```bash
python3 --version
```

Deberías ver algo como `Python 3.11.x` o superior.  
Si no tienes Python, descárgalo de [python.org](https://www.python.org/downloads/) e instálalo.  
**En Windows**: marca la casilla *“Add Python to PATH”* durante la instalación.

---

## Instalación paso a paso

### 1. Descargar el proyecto

**Opción A — Con Git (recomendado)**

```bash
git clone https://github.com/robertosantosx2/explorador-de-redit.git
cd explorador-de-redit
```

**Opción B — Sin Git**

1. Entra en https://github.com/robertosantosx2/explorador-de-redit
2. Pulsa el botón verde **Code → Download ZIP**
3. Descomprime el ZIP
4. Abre una terminal dentro de la carpeta descomprimida

### 2. Crear un entorno virtual (recomendado)

Así las librerías del proyecto no se mezclan con las del sistema:

```bash
# Crear el entorno
python -m venv .venv
```

Activarlo:

```bash
# Linux / macOS
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Windows (CMD)
.venv\Scripts\activate.bat
```

Cuando el entorno está activo verás `(.venv)` al principio de la línea de la terminal.

### 3. Instalar las dependencias

```bash
pip install -r requirements.txt
```

Esto instala:

- `flask` — servidor web de la interfaz
- `praw` — acceso a la API oficial de Reddit
- `requests` — para el modo sin credenciales
- `python-dotenv` — lectura de variables de entorno (CLI)

### 4. (Opcional) Preparar el archivo de credenciales para el CLI

Solo hace falta si vas a usar el **script de terminal**:

```bash
cp .env.example .env
```

Luego edita `.env` con un editor de texto y rellena tus datos (ver sección siguiente).

---

## Obtener credenciales de Reddit (opcional pero recomendado)

Reddit permite usar su API de forma gratuita creando una “aplicación”.  
**No es obligatorio**: puedes usar el modo *Sin credenciales*, pero con la API obtienes muchos más comentarios.

### Pasos detallados

1. Inicia sesión en Reddit con tu cuenta.
2. Abre esta página:  
   **[https://www.reddit.com/prefs/apps](https://www.reddit.com/prefs/apps)**
3. Baja hasta el final y pulsa **“are you a developer? create an app…”**  
   (o **“Create App”** / **“Create Another App”**).
4. Rellena el formulario así:

   | Campo | Valor |
   |-------|--------|
   | **name** | `explorador-de-redit` (o el nombre que quieras) |
   | **tipo** | Elige **script** |
   | **description** | (opcional) |
   | **about url** | (déjalo vacío) |
   | **redirect uri** | `http://localhost:8080` |

5. Pulsa **“create app”**.
6. En la tarjeta de la app que acaba de crearse verás:
   - Justo debajo del nombre: una cadena corta → ese es el **client_id**
   - La línea **“secret”** → ese es el **client_secret**

Copia ambos valores. Los necesitarás en la interfaz web o en el archivo `.env`.

> **Importante:** no compartas el *client_secret* públicamente. El archivo `.env` está en el `.gitignore` para que no se suba a GitHub.

---

## Usar la interfaz web

### Arrancar el servidor

Con el entorno virtual activado y estando dentro de la carpeta del proyecto:

```bash
python app.py
```

Verás un mensaje similar a:

```text
🚀 Interfaz lista → http://127.0.0.1:5000
```

### Abrir en el navegador

Abre tu navegador y ve a:

**http://127.0.0.1:5000**

(o **http://localhost:5000**)

### Extraer un hilo — paso a paso

1. **Copia la URL** del hilo de Reddit que te interesa.  
   Ejemplo:  
   `https://www.reddit.com/r/AskReddit/comments/abc123/titulo_del_post/`

2. **Pégala** en el campo *“URL del hilo de Reddit”*.

3. Elige el **modo**:
   - **Sin credenciales** → no pides nada a la API; más rápido de probar, pero solo trae los comentarios visibles en la primera carga.
   - **Con credenciales** → usa tu Client ID y Secret; obtiene muchos más comentarios (recomendado en hilos grandes).

4. Si elegiste *Con credenciales*:
   - Escribe tu **Client ID** y **Client Secret**.
   - (Opcional) marca *“Recordar credenciales en este navegador”* para no tener que escribirlas cada vez.
   - Puedes ajustar el **límite de “More Comments”** (por defecto 30). Un número más alto trae más comentarios pero tarda más.

5. Pulsa uno de los botones:
   - **Previsualizar** → muestra el Markdown en la página para revisarlo.
   - **Descargar Markdown** → descarga directamente el archivo `.md`.

6. Si previsualizaste, puedes pulsar **“Descargar este Markdown”** cuando estés contento con el resultado.

### Detener el servidor

En la terminal donde está corriendo `python app.py`, pulsa **Ctrl + C**.

---

## Usar el script de terminal (CLI)

Útil si quieres automatizar o no necesitas la interfaz gráfica.

### Configurar credenciales

1. Copia el ejemplo de variables de entorno:

   ```bash
   cp .env.example .env
   ```

2. Edita `.env` y rellénalo:

   ```env
   REDDIT_CLIENT_ID=tu_client_id_aqui
   REDDIT_CLIENT_SECRET=tu_client_secret_aqui
   REDDIT_USER_AGENT=script:explorador-de-redit:v1.0 (by u/tu_usuario)
   ```

   También puedes exportar las variables en la terminal en lugar de usar `.env`.

### Ejecutar

```bash
# Uso básico (genera el nombre del archivo automáticamente)
python reddit_to_markdown.py "https://www.reddit.com/r/subreddit/comments/ID/titulo/"

# Indicar el nombre de salida
python reddit_to_markdown.py "URL_DEL_HILO" -o mi_hilo.md

# Limitar la expansión de comentarios ocultos (más rápido en hilos enormes)
python reddit_to_markdown.py "URL_DEL_HILO" --limit 20
```

El script imprimirá la ruta del archivo generado y un resumen (título y número de comentarios cargados).

---

## Historial de hilos

La interfaz web **guarda automáticamente** cada hilo que extraes (tanto al previsualizar como al descargar).

### Qué se guarda

- Título del post
- URL original
- Fecha y hora de la extracción
- Modo usado (sin credenciales / con API)
- El propio archivo Markdown

### Qué puedes hacer con el historial

En la sección **Historial** de la página verás la lista de hilos:

| Acción | Qué hace |
|--------|----------|
| **Reusar** | Pone de nuevo la URL en el formulario para volver a extraer |
| **.md** | Descarga otra vez el Markdown **sin** volver a llamar a Reddit |
| **✕** | Elimina solo esa entrada |
| **Vaciar** | Borra todo el historial |

### Dónde se guardan los datos

| Archivo / carpeta | Contenido |
|-------------------|----------|
| `history.json` | Lista de entradas del historial |
| `history_md/` | Archivos `.md` de cada extracción |

Ambos están en el `.gitignore`: **no se suben a GitHub**. Solo existen en tu ordenador.  
Se mantienen hasta un máximo de **50** entradas; las más antiguas se eliminan solas.

---

## Modos de extracción

| Modo | ¿Necesita credenciales? | Ventajas | Limitaciones |
|------|-------------------------|----------|--------------|
| **Sin credenciales** | No | Muy fácil de probar, sin configuración | Solo los comentarios que Reddit muestra en la primera carga (no expande “load more”) |
| **Con credenciales (API)** | Sí | Puede expandir muchos más comentarios | Hay que crear una app en Reddit; en hilos enormes puede tardar |

**Recomendación práctica:**

- Para probar o hilos pequeños → *Sin credenciales*
- Para guardar un hilo importante o con muchos comentarios → *Con credenciales*

---

## Estructura del proyecto

```text
explorador-de-redit/
├── app.py                  # Interfaz web (Flask)
├── reddit_to_markdown.py   # Script de terminal (CLI)
├── requirements.txt        # Dependencias de Python
├── .env.example            # Plantilla de credenciales para el CLI
├── .gitignore
├── LICENSE                 # AGPL-3.0
├── README.md               # Este archivo
├── history.json            # (se crea solo) historial de hilos
└── history_md/             # (se crea solo) Markdown guardados del historial
```

---

## Solución de problemas

### “python no se reconoce como comando”

- Usa `python3` en lugar de `python`.
- En Windows, reinstala Python marcando *Add to PATH*.

### Error al instalar dependencias

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### “Error al extraer el hilo” / 403 / 429

- Reddit puede limitar las peticiones si haces muchas seguidas.
- En modo sin credenciales prueba más tarde o cambia a modo con credenciales.
- Comprueba que la URL sea realmente de un **hilo** (debe contener `/comments/`).

### La interfaz no abre en el navegador

- Confirma que la terminal muestra `http://127.0.0.1:5000`.
- Prueba también `http://localhost:5000`.
- Asegúrate de que ningún otro programa está usando el puerto 5000.  
  Si hace falta, arranca con otro puerto:

  ```bash
  PORT=8080 python app.py
  ```

### Los comentarios salen incompletos

- En modo **sin credenciales** es normal: Reddit no envía todos de golpe.
- Usa el modo **con credenciales** y sube el límite de “More Comments” (por ejemplo 50 o 100).  
  Valores muy altos en hilos enormes pueden tardar varios minutos.

### Quiero borrar el historial a mano

Borra estos archivos/carpetas dentro del proyecto:

- `history.json`
- la carpeta `history_md/`

O usa el botón **Vaciar** en la interfaz.

---

## Licencia

Este proyecto se distribuye bajo la licencia **AGPL-3.0**.  
Consulta el archivo [LICENSE](LICENSE) para más detalles.
