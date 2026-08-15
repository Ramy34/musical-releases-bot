# 🎵 Bot de Lanzamientos Musicales (Spotify + Telegram)

Un bot en Python que monitorea automáticamente nuevos lanzamientos (álbumes, sencillos, EPs) de una lista de artistas en **Spotify** y notifica las novedades por **Telegram**. Los datos de seguimiento y control de duplicados se gestionan en una base de datos **PostgreSQL**.

---

## 🚀 Características

* **Monitoreo Automático:** Revisa periódicamente nuevos lanzamientos de artistas en seguimiento.
* **Integración con Spotify API:** Usa el flujo `Client Credentials` de Spotify (no requiere cuenta Premium).
* **Gestión vía Telegram:** Control de lista de artistas mediante comandos de chat (`/seguir`, `/desafiliar`, `/siguiendo`, `/sembrar`, `/checar`).
* **Auto-importación ("Sembrado"):** Posibilidad de importar automáticamente artistas desde la base de datos de música existente.
* **Filtro Inteligente:** Evita enviar notificaciones duplicadas registrando los IDs de los lanzamientos.
* **API Web / Dashboard:** Expone un endpoint HTTP (`POST /trigger_check`) en el puerto `8085` para disparar comprobaciones manuales.
* **Despliegue con Docker:** Configurado para ejecutarse fácilmente mediante Docker y Docker Compose.

---

## 🛠️ Requisitos Previos

* **Docker** y **Docker Compose** (o Python 3.10+ y PostgreSQL si se ejecuta localmente).
* Un **Bot de Telegram** (creado a través de [@BotFather](https://t.me/BotFather)) y tu `CHAT_ID`.
* Una aplicación en **Spotify Developer Dashboard** ([developer.spotify.com](https://developer.spotify.com/dashboard)) para obtener `Client ID` y `Client Secret`.
* Base de datos PostgreSQL con acceso a las tablas/vistas requeridas.

---

## ⚙️ Configuración (.env)

1. Clona este repositorio:
   ```bash
   git clone https://github.com/tu-usuario/tu-repositorio.git
   cd tu-repositorio
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
| `🌱 /sembrar` | Importa automáticamente artistas con playlist desde la base de datos |
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
