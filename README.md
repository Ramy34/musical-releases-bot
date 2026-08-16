# 🎵 Bot de Lanzamientos Musicales (Spotify + Telegram)

Un bot en Python que monitorea automáticamente nuevos lanzamientos (álbumes, sencillos, EPs) de una lista de artistas en **Spotify** y notifica las novedades por **Telegram**.
Los datos de seguimiento y control de duplicados se gestionan en una base de datos **PostgreSQL**.

---

## 🚀 Características

* **Monitoreo Automático:** Revisa periódicamente nuevos lanzamientos de los artistas en seguimiento.
* **Integración con Spotify API:** Usa el flujo `Client Credentials` de Spotify.
* **Ventana de Búsqueda Configurable:** Permite ajustar los días hacia atrás (`LOOKBACK_DAYS`) para buscar lanzamientos recientes.
* **Gestión vía Telegram:** Control de lista de artistas mediante comandos de chat (`/seguir`, `/desafiliar`, `/siguiendo`, `/checar`).
* **Filtro Inteligente:** Evita enviar notificaciones duplicadas registrando los IDs de los lanzamientos en la base de datos.
* **API Web / Dashboard:** Expone un endpoint HTTP (`POST /trigger_check`) en el puerto `8085` para disparar comprobaciones manuales.
* **Despliegue con Docker:** Configurado para ejecutarse fácilmente mediante Docker y Docker Compose.

---

## 🛠️ Requisitos Previos

* **Docker** y **Docker Compose** (o Python 3.10+ y PostgreSQL si se ejecuta localmente).
* Un **Bot de Telegram** (creado a través de [@BotFather](https://t.me/BotFather)) y tu `CHAT_ID`.
* Una aplicación en **Spotify Developer Dashboard** ([developer.spotify.com](https://developer.spotify.com/dashboard)) para obtener `Client ID` y `Client Secret`.
* Base de datos **PostgreSQL** con el esquema y tablas requeridas.

---

## 🗄️ Configuración de la Base de Datos (PostgreSQL)

El bot requiere un esquema llamado `adm` y dos tablas principales para su funcionamiento. Ejecuta las siguientes sentencias SQL en tu base de datos PostgreSQL:

```sql
-- 1. Crear esquema adm (si no existe)
CREATE SCHEMA IF NOT EXISTS adm;

-- 2. Tabla para almacenar la lista de artistas en seguimiento
CREATE TABLE IF NOT EXISTS adm.releases_seguimiento (
    id SERIAL PRIMARY KEY,
    artista TEXT NOT NULL UNIQUE,
    spotify_id TEXT,
    origen_importacion TEXT DEFAULT 'manual',
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Tabla para llevar el historial de lanzamientos ya notificados
CREATE TABLE IF NOT EXISTS adm.releases_notificadas (
    spotify_album_id TEXT PRIMARY KEY,
    artista TEXT NOT NULL,
    titulo TEXT NOT NULL,
    tipo_lanzamiento TEXT,
    fecha_lanzamiento TEXT,
    fecha_notificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 📲 ¿Cómo obtener tu CHAT_ID de Telegram?

Para que el bot sepa a qué chat o usuario enviarle las notificaciones:

1. Abre la aplicación de Telegram.
2. Busca el bot oficial **`@userinfobot`** o **`@raw_data_bot`**.
3. Inicia una conversación enviándole cualquier mensaje (ej. `/start`).
4. El bot te responderá mostrando tus datos, entre ellos tu **`Id`** numérico (por ejemplo: `123456789`).
5. Copia ese número y asígnalo a la variable `CHAT_ID` en tu archivo `.env`.

*Nota:* Si quieres que las notificaciones lleguen a un **grupo**, añade tu bot al grupo, envía un mensaje ahí y obtén el ID del grupo (suele empezar con un signo menos, ej: `-100123456789`).

---

## ⚙️ Configuración del Entorno (.env)

1. Clona este repositorio:
   ```bash
   git clone https://github.com/Ramy34/musical-releases-bot.git
   cd musical-releases-bot
   ```

2. Copia la plantilla de variables de entorno y edítala con tus datos:
   ```bash
   cp .env.example .env
   ```

3. Edita `.env` agregando tus credenciales:
   ```env
   TELEGRAM_TOKEN=tu_token_de_telegram
   CHAT_ID=tu_chat_id
   DATABASE_URL=postgresql://usuario:contraseña@host:5432/musica
   SPOTIFY_CLIENT_ID=tu_spotify_client_id
   SPOTIFY_CLIENT_SECRET=tu_spotify_client_secret
   CHECK_INTERVAL_HOURS=12
   LOOKBACK_DAYS=3
   ```

---

## 🐳 Despliegue con Docker Compose

Para iniciar el bot en segundo plano:

```bash
docker compose up -d --build
```

Para ver los logs del contenedor:
```bash
docker compose logs -f releases-bot
```

Para detener el contenedor:
```bash
docker compose down
```

---

## 🤖 Comandos de Telegram

Una vez activo, el bot responde a los siguientes comandos en tu chat de Telegram:

| Comando | Descripción |
| :--- | :--- |
| `➕ /seguir <artista>` | Añade un artista a la lista de seguimiento |
| `➖ /desafiliar <artista>` | Elimina un artista de la lista de seguimiento |
| `📋 /siguiendo` | Lista los artistas que estás siguiendo con enlaces a Spotify |
| `🔍 /checar` | Fuerza una verificación manual de lanzamientos en Spotify |

---

## 🛠️ Estructura del Proyecto

```
.
├── bot.py               # Código principal del bot (Flask + Telegram + Spotify API + PostgreSQL)
├── compose.yml          # Configuración para Docker Compose
├── Dockerfile           # Imagen Docker para el entorno Python
├── requirements.txt     # Dependencias de Python
├── .env.example         # Plantilla de variables de entorno
└── README.md            # Documentación del proyecto
```
