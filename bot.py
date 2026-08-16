import os
import time
import json
import re
import urllib.request
import urllib.parse
import threading
import ssl
import http.cookiejar
from datetime import datetime, timedelta
import psycopg2
from flask import Flask, jsonify

# Load .env file if available (for local execution)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Configuration from Environment Variables
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
CHAT_ID_ENV = os.environ.get("CHAT_ID", "0").strip()
CHAT_ID = int(CHAT_ID_ENV) if CHAT_ID_ENV.lstrip("-").isdigit() else 0
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "").strip()
CHECK_INTERVAL_HOURS = int(os.environ.get("CHECK_INTERVAL_HOURS", "12"))
LOOKBACK_DAYS = int(os.environ.get("LOOKBACK_DAYS", "3"))

# Global states
spotify_access_token = ""
spotify_token_expires = datetime.now()
is_checking = False
check_lock = threading.Lock()

# ----------------- Flask Initialization -----------------
app = Flask(__name__)

@app.route("/trigger_check", methods=["POST"])
def trigger_check():
    try:
        run_check_async(CHAT_ID)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ----------------- DB HELPERS -----------------
def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def execute_query(query, params=None, fetch=False):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(query, params)
        if fetch:
            rows = cur.fetchall()
            return rows
        conn.commit()
    except Exception as e:
        print(f"DB Error: {e}")
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()

# ----------------- TELEGRAM HELPERS -----------------
def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown", "disable_web_page_preview": "false"}).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=data)
        ctx = ssl._create_unverified_context()
        with urllib.request.urlopen(req, context=ctx) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f"Error sending Telegram message: {e}")
        return None

def get_telegram_updates(offset=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?timeout=30"
    if offset:
        url += f"&offset={offset}"
    try:
        req = urllib.request.Request(url)
        ctx = ssl._create_unverified_context()
        with urllib.request.urlopen(req, timeout=35, context=ctx) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f"Error getting Telegram updates: {e}")
        return None

# ----------------- SPOTIFY API HELPERS -----------------
def get_spotify_token():
    global spotify_access_token, spotify_token_expires
    if spotify_access_token and datetime.now() < spotify_token_expires:
        return spotify_access_token

    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        print("Error: SPOTIFY_CLIENT_ID or SPOTIFY_CLIENT_SECRET environment variables are missing.")
        return None

    url = "https://accounts.spotify.com/api/token"
    data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode("utf-8")
    
    import base64
    auth_str = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}"
    auth_b64 = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
    
    headers = {
        "Authorization": f"Basic {auth_b64}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    try:
        req = urllib.request.Request(url, data=data, headers=headers)
        ctx = ssl._create_unverified_context()
        with urllib.request.urlopen(req, context=ctx) as resp:
            res = json.loads(resp.read().decode('utf-8'))
            spotify_access_token = res["access_token"]
            expires_in = res["expires_in"]
            spotify_token_expires = datetime.now() + timedelta(seconds=expires_in - 60)
            return spotify_access_token
    except Exception as e:
        print(f"Error getting Spotify token: {e}")
        return None

def spotify_request(url):
    token = get_spotify_token()
    if not token:
        return None
        
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        ctx = ssl._create_unverified_context()
        with urllib.request.urlopen(req, context=ctx) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f"Spotify request error on URL {url}: {e}")
        return None

def resolve_spotify_artist_id(artist_name):
    query_str = urllib.parse.quote(f"artist:\"{artist_name}\"")
    url = f"https://api.spotify.com/v1/search?q={query_str}&type=artist&limit=1"
    
    res = spotify_request(url)
    if res and res.get("artists", {}).get("items"):
        item = res["artists"]["items"][0]
        return item["id"]
    return None

# ----------------- RELEASES CORE MONITOR -----------------
def check_new_releases_job(trigger_chat_id=None):
    global is_checking
    with check_lock:
        if is_checking:
            if trigger_chat_id:
                send_telegram_message("Ya hay una búsqueda de lanzamientos en progreso. Por favor espera a que termine.")
            print("Check already in progress. Skipping.")
            return
        is_checking = True
        
    try:
        # Get all followed artists
        artists = execute_query("SELECT id, artista, spotify_id FROM adm.releases_seguimiento ORDER BY artista ASC;", fetch=True)
        if not artists:
            print("No artists to follow.")
            if trigger_chat_id:
                send_telegram_message("No tienes ningún artista en tu lista de seguimiento actualmente. Agrega algunos usando `/seguir Nombre`.")
            return

        new_releases_count = 0
        
        for db_id, name, spotify_id in artists:
            time.sleep(0.3)
            
            if not spotify_id:
                print(f"Resolving Spotify ID for: {name}")
                spotify_id = resolve_spotify_artist_id(name)
                if spotify_id:
                    execute_query("UPDATE adm.releases_seguimiento SET spotify_id = %s WHERE id = %s;", (spotify_id, db_id))
                    print(f"Resolved {name} -> {spotify_id}")
                else:
                    print(f"Could not resolve Spotify ID for {name}")
                    continue
            
            albums_url = f"https://api.spotify.com/v1/artists/{spotify_id}/albums?include_groups=album,single,ep,compilation&limit=10&market=MX"
            res = spotify_request(albums_url)
            if not res or not res.get("items"):
                continue
                
            for album in res["items"]:
                album_id = album["id"]
                album_name = album["name"]
                release_date = album["release_date"]
                release_date_precision = album["release_date_precision"]
                release_type = album["album_group"]
                spotify_url = album.get("external_urls", {}).get("spotify", "")
                
                already_notified = execute_query("SELECT 1 FROM adm.releases_notificadas WHERE spotify_album_id = %s;", (album_id,), fetch=True)
                if already_notified:
                    continue
                    
                is_recent = False
                if release_date_precision == "day":
                    try:
                        rel_date = datetime.strptime(release_date, "%Y-%m-%d").date()
                        today = datetime.now().date()
                        if today - timedelta(days=LOOKBACK_DAYS) <= rel_date <= today + timedelta(days=1):
                            is_recent = True
                    except Exception as date_err:
                        print(f"Error parsing date {release_date}: {date_err}")
                
                if is_recent:
                    type_labels = {
                        "album": "💿 Álbum",
                        "single": "🎵 Sencillo (Single)",
                        "ep": "💿 EP",
                        "compilation": "🗂️ Recopilación"
                    }
                    friendly_type = type_labels.get(release_type, "🎵 Lanzamiento")
                    
                    msg = (
                        f"✨ *¡Nuevo Lanzamiento!*\n\n"
                        f"👤 *Artista:* {name}\n"
                        f"💿 *Título:* {album_name}\n"
                        f"🏷️ *Tipo:* {friendly_type}\n"
                        f"📅 *Fecha:* {release_date}\n\n"
                        f"🔗 [Escuchar en Spotify]({spotify_url})"
                    )
                    
                    send_telegram_message(msg)
                    new_releases_count += 1
                    
                try:
                    execute_query(
                        "INSERT INTO adm.releases_notificadas (spotify_album_id, artista, titulo, tipo_lanzamiento, fecha_lanzamiento) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (spotify_album_id) DO NOTHING;",
                        (album_id, name, album_name, release_type, release_date)
                    )
                except Exception as db_err:
                    print(f"Error inserting notified album {album_id}: {db_err}")

        print(f"Releases check completed. Notified of {new_releases_count} new releases.")
        if trigger_chat_id:
            if new_releases_count == 0:
                send_telegram_message(f"✅ *Búsqueda de lanzamientos completada.*\nNo se encontraron nuevos lanzamientos en los últimos {LOOKBACK_DAYS} días para tus artistas en seguimiento.")
            else:
                send_telegram_message(f"✅ *Búsqueda de lanzamientos completada.*\nSe encontraron y notificaron *{new_releases_count}* nuevos lanzamientos.")
    except Exception as e:
        print(f"Error in releases job: {e}")
        if trigger_chat_id:
            send_telegram_message(f"Ocurrió un error al buscar lanzamientos: {e}")
    finally:
        with check_lock:
            is_checking = False

def run_check_async(trigger_chat_id=None):
    threading.Thread(target=check_new_releases_job, args=(trigger_chat_id,)).start()

# ----------------- SCHEDULER LOOP -----------------
def scheduler_loop():
    print(f"Scheduler loop started. Will check every {CHECK_INTERVAL_HOURS} hours.")
    while True:
        run_check_async()
        time.sleep(CHECK_INTERVAL_HOURS * 3600)

# ----------------- TELEGRAM COMMAND HANDLERS -----------------
def handle_command_seguir(chat_id, artist_name):
    if not artist_name:
        send_telegram_message("⚠️ Por favor escribe el nombre del artista. Uso: `/seguir Nombre del Artista`")
        return
        
    try:
        execute_query("INSERT INTO adm.releases_seguimiento (artista, origen_importacion) VALUES (%s, 'manual') ON CONFLICT (artista) DO NOTHING;", (artist_name,))
        send_telegram_message(f"Se ha añadido a *{artist_name}* a la lista de seguimiento. Buscaré sus nuevos lanzamientos en Spotify.")
        run_check_async(chat_id)
    except Exception as e:
        send_telegram_message(f"Error al guardar artista: {e}")

def handle_command_desafiliar(chat_id, artist_name):
    if not artist_name:
        send_telegram_message("Por favor escribe el nombre del artista. Uso: `/desafiliar Nombre del Artista`")
        return
        
    try:
        exists = execute_query("SELECT 1 FROM adm.releases_seguimiento WHERE artista ILIKE %s;", (artist_name,), fetch=True)
        if not exists:
            send_telegram_message(f"El artista *{artist_name}* no se encuentra en tu lista de seguimiento.")
            return
            
        execute_query("DELETE FROM adm.releases_seguimiento WHERE artista ILIKE %s;", (artist_name,))
        send_telegram_message(f"Se ha eliminado a *{artist_name}* de la lista de seguimiento.")
    except Exception as e:
        send_telegram_message(f"Error al desafiliar artista: {e}")

def handle_command_siguiendo(chat_id):
    try:
        rows = execute_query("SELECT artista, spotify_id FROM adm.releases_seguimiento ORDER BY artista ASC;", fetch=True)
        if not rows:
            send_telegram_message("No estás siguiendo a ningún artista actualmente. Agrega uno con `/seguir Nombre`.")
            return
            
        msg = "📋 *Artistas en Seguimiento:*\n\n"
        for idx, r in enumerate(rows, 1):
            name, spotify_id = r
            if spotify_id:
                spotify_url = f"https://open.spotify.com/artist/{spotify_id}"
                msg += f"{idx}. [{name}]({spotify_url})\n"
            else:
                msg += f"{idx}. {name} _(Sin ID de Spotify, se resolverá en la próxima búsqueda)_\n"
        send_telegram_message(msg)
    except Exception as e:
        send_telegram_message(f"Error al consultar lista: {e}")

# ----------------- FLASK SERVER THREAD -----------------
def run_flask():
    app.run(host="0.0.0.0", port=8085, debug=False, use_reloader=False)

# ----------------- MAIN LOGIC -----------------
def main():
    print("Iniciando Bot de Lanzamientos Musicales...")

    missing_vars = []
    if not TELEGRAM_TOKEN: missing_vars.append("TELEGRAM_TOKEN")
    if not CHAT_ID: missing_vars.append("CHAT_ID")
    if not DATABASE_URL: missing_vars.append("DATABASE_URL")
    if not SPOTIFY_CLIENT_ID: missing_vars.append("SPOTIFY_CLIENT_ID")
    if not SPOTIFY_CLIENT_SECRET: missing_vars.append("SPOTIFY_CLIENT_SECRET")

    if missing_vars:
        print(f"ADVERTENCIA: Faltan las siguientes variables de entorno: {', '.join(missing_vars)}")
        print("Asegúrate de configurar tu archivo .env o pasar las variables al contenedor.")
    
    # Start scheduler thread
    threading.Thread(target=scheduler_loop, daemon=True).start()
    
    # Start Flask Web Dashboard thread
    threading.Thread(target=run_flask, daemon=True).start()
    print("Web dashboard server started on port 8085.")
    
    send_telegram_message(
        "🤖 *Bot de Lanzamientos Sinfonía Activado.*\n\n"
        "Comandos disponibles:\n"
        "➕ /seguir `<artista>` - Seguir a un nuevo artista\n"
        "➖ /desafiliar `<artista>` - Dejar de seguir a un artista\n"
        "📋 /siguiendo - Listar artistas en seguimiento\n"
        "🔍 /checar - Forzar búsqueda de lanzamientos ahora"
    )
    
    offset = None
    while True:
        updates = get_telegram_updates(offset)
        if updates and updates.get("ok"):
            for result in updates.get("result", []):
                offset = result.get("update_id") + 1
                message = result.get("message", {})
                chat = message.get("chat", {})
                chat_id = chat.get("id")
                text = message.get("text", "").strip()
                
                if chat_id != CHAT_ID:
                    continue
                    
                text_lower = text.lower()
                
                if text_lower in ["/start", "start", "hola"]:
                    send_telegram_message(
                        "🤖 ¡Hola! Comandos disponibles:\n"
                        "• /seguir `<nombre>`\n"
                        "• /desafiliar `<nombre>`\n"
                        "• /siguiendo\n"
                        "• /checar"
                    )
                elif text_lower.startswith("/seguir "):
                    name = text[len("/seguir "):].strip()
                    handle_command_seguir(chat_id, name)
                elif text_lower.startswith("/desafiliar "):
                    name = text[len("/desafiliar "):].strip()
                    handle_command_desafiliar(chat_id, name)
                elif text_lower in ["/siguiendo", "siguiendo"]:
                    handle_command_siguiendo(chat_id)
                elif text_lower in ["/checar", "checar", "/check", "check"]:
                    send_telegram_message("🔍 Iniciando búsqueda manual de lanzamientos en Spotify...")
                    run_check_async(chat_id)
                    
        time.sleep(1)

if __name__ == "__main__":
    main()
