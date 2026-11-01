import os
import time
import json
import logging
import requests
from typing import Dict, List

# Konfigurasi Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Konfigurasi dari Environment Variables (dengan fallback sesuai detail yang diberikan)
TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN",
    "9148476943:AAGzzLXRtSFmxS5qPvPBndBfWssAJm4GvhY",
)
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.bestllmapi.com/v1").rstrip("/")
AI_API_KEY = os.getenv("AI_API_KEY", "sk-8e673f8a5ecbc3b7-gjs2d2-6970375c")
AI_MODEL = os.getenv("AI_MODEL", "deepseek/deepseek-v4-flash")
SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "Kamu adalah asisten AI pintar yang ramah, membantu, dan menjawab dengan jelas.",
)

# Durasi maksimal jalannya bot dalam sekali eksekusi (berguna untuk GitHub Actions cron/workflow)
# Set ke 0 untuk berjalan tanpa batas waktu (misal di VPS / Codespaces / lokal)
MAX_RUNTIME_SECONDS = int(os.getenv("MAX_RUNTIME_SECONDS", "0"))
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "12"))

TELEGRAM_API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# Penyimpanan riwayat percakapan per chat_id di memori
chat_histories: Dict[int, List[Dict[str, str]]] = {}


def send_chat_action(chat_id: int, action: str = "typing") -> None:
    """Mengirim indikator status (seperti 'typing') ke pengguna Telegram."""
    try:
        requests.post(
            f"{TELEGRAM_API_BASE}/sendChatAction",
            json={"chat_id": chat_id, "action": action},
            timeout=10,
        )
    except requests.RequestException as exc:
        logger.debug("Gagal mengirim chat action: %s", exc)


def send_telegram_message(chat_id: int, text: str, reply_to_message_id: int = None) -> None:
    """Mengirim pesan ke Telegram, otomatis memecah pesan jika lebih dari 4000 karakter."""
    if not text:
        text = "(Respons kosong dari model AI)"

    max_len = 4000
    chunks = [text[i : i + max_len] for i in range(0, len(text), max_len)]

    for idx, chunk in enumerate(chunks):
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "Markdown",
        }
        if idx == 0 and reply_to_message_id:
            payload["reply_to_message_id"] = reply_to_message_id

        try:
            resp = requests.post(
                f"{TELEGRAM_API_BASE}/sendMessage",
                json=payload,
                timeout=20,
            )
            # Jika gagal parsing Markdown, kirim ulang sebagai plain text
            if resp.status_code != 200:
                payload.pop("parse_mode", None)
                requests.post(
                    f"{TELEGRAM_API_BASE}/sendMessage",
                    json=payload,
                    timeout=20,
                )
        except requests.RequestException as exc:
            logger.error("Gagal mengirim pesan ke Telegram: %s", exc)


def query_ai_model(chat_id: int, user_message: str) -> str:
    """Mengirim riwayat pesan ke endpoint OpenAI-compatible (/v1/chat/completions)."""
    history = chat_histories.setdefault(
        chat_id,
        [{"role": "system", "content": SYSTEM_PROMPT}],
    )
    history.append({"role": "user", "content": user_message})

    # Batasi jumlah pesan agar tidak melebihi batas token
    if len(history) > MAX_HISTORY_MESSAGES + 1:
        history[:] = [history[0]] + history[-MAX_HISTORY_MESSAGES:]

    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "TelegramAIBot/1.0",
    }

    payload = {
        "model": AI_MODEL,
        "messages": history,
        "temperature": 0.7,
        "stream": False,
    }

    endpoint = f"{AI_BASE_URL}/chat/completions"

    try:
        response = requests.post(
            endpoint,
            headers=headers,
            json=payload,
            timeout=90,
        )
        response.raise_for_status()
        data = response.json()

        choices = data.get("choices", [])
        if choices and "message" in choices[0]:
            reply_content = choices[0]["message"].get("content", "").strip()
        elif choices and "text" in choices[0]:
            reply_content = choices[0].get("text", "").strip()
        else:
            reply_content = f"Format respons API tidak dikenali:\n{json.dumps(data, indent=2)}"

        if reply_content:
            history.append({"role": "assistant", "content": reply_content})
        return reply_content

    except requests.HTTPError as http_err:
        err_body = ""
        if http_err.response is not None:
            err_body = http_err.response.text[:400]
        logger.error("HTTP Error dari API AI: %s | %s", http_err, err_body)
        # Hapus pesan user terakhir jika gagal agar riwayat tetap bersih
        history.pop()
        return f"Terjadi kesalahan dari server AI ({http_err}).\nDetail: {err_body}"
    except requests.RequestException as req_err:
        logger.error("Koneksi ke API AI gagal: %s", req_err)
        history.pop()
        return f"Gagal terhubung ke endpoint AI ({AI_BASE_URL}): {req_err}"
    except Exception as exc:
        logger.exception("Kesalahan tak terduga saat memanggil AI:")
        history.pop()
        return f"Terjadi kesalahan internal: {exc}"


def handle_message(message: dict) -> None:
    """Memproses pesan masuk dari pengguna Telegram."""
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    message_id = message.get("message_id")
    text = (message.get("text") or "").strip()

    if not chat_id or not text:
        return

    user_info = message.get("from", {})
    username = user_info.get("username") or user_info.get("first_name") or str(chat_id)
    logger.info("Pesan dari %s (%s): %s", username, chat_id, text[:80])

    # Perintah bawaan
    if text.startswith("/start"):
        welcome_msg = (
            "Halo! Saya adalah *Bot AI Telegram* yang terhubung ke model "
            f"`{AI_MODEL}`.\n\n"
            "*Perintah yang tersedia:*\n"
            "• Kirim pesan apa saja untuk mulai mengobrol dengan AI\n"
            "• `/reset` — Hapus riwayat percakapan\n"
            "• `/info` — Lihat konfigurasi model & endpoint saat ini"
        )
        send_telegram_message(chat_id, welcome_msg, reply_to_message_id=message_id)
        return

    if text.startswith("/reset") or text.startswith("/clear"):
        chat_histories[chat_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
        send_telegram_message(
            chat_id,
            "Riwayat percakapan berhasil direset! Silakan mulai topik baru.",
            reply_to_message_id=message_id,
        )
        return

    if text.startswith("/info"):
        info_msg = (
            "*Informasi Konfigurasi Bot AI*\n"
            f"• *Model:* `{AI_MODEL}`\n"
            f"• *Base URL:* `{AI_BASE_URL}`\n"
            f"• *Pesan dalam memori:* `{max(0, len(chat_histories.get(chat_id, [])) - 1)}`"
        )
        send_telegram_message(chat_id, info_msg, reply_to_message_id=message_id)
        return

    # Kirim status "sedang mengetik..."
    send_chat_action(chat_id, "typing")

    # Panggil API AI dan kirim balasan
    ai_reply = query_ai_model(chat_id, text)
    send_telegram_message(chat_id, ai_reply, reply_to_message_id=message_id)


def run_polling() -> None:
    """Menjalankan long-polling Telegram Bot."""
    logger.info("Memulai Telegram AI Bot...")
    logger.info("Model: %s | Endpoint: %s", AI_MODEL, AI_BASE_URL)

    offset = 0
    start_time = time.time()

    while True:
        # Berhenti otomatis jika MAX_RUNTIME_SECONDS diset (misal untuk GitHub Actions)
        if MAX_RUNTIME_SECONDS > 0 and (time.time() - start_time) >= MAX_RUNTIME_SECONDS:
            logger.info("Batas waktu eksekusi (%s detik) tercapai. Bot berhenti dengan aman.", MAX_RUNTIME_SECONDS)
            break

        try:
            resp = requests.get(
                f"{TELEGRAM_API_BASE}/getUpdates",
                params={"offset": offset, "timeout": 25},
                timeout=35,
            )
            if resp.status_code == 401:
                logger.error("Token Bot Telegram tidak valid (401 Unauthorized). Periksa TELEGRAM_BOT_TOKEN.")
                break

            data = resp.json()
            if not data.get("ok"):
                logger.warning("Respons getUpdates tidak ok: %s", data)
                time.sleep(3)
                continue

            for update in data.get("result", []):
                offset = update["update_id"] + 1
                if "message" in update:
                    handle_message(update["message"])

        except requests.RequestException as exc:
            logger.warning("Gangguan jaringan saat polling: %s. Mencoba lagi dalam 5 detik...", exc)
            time.sleep(5)
        except KeyboardInterrupt:
            logger.info("Bot dihentikan oleh pengguna.")
            break
        except Exception as exc:
            logger.exception("Kesalahan pada loop utama: %s", exc)
            time.sleep(5)


if __name__ == "__main__":
    run_polling()
