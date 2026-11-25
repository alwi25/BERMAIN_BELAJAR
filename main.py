import os
import time
import re
import html
import io
import random
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import urllib3
import telebot
from telebot import apihelper
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from google import genai

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Session HTTP bersama agar lebih ringan & cepat
HTTP = requests.Session()
HTTP.verify = False
HTTP.headers.update({"User-Agent": "Mozilla/5.0"})

# 1. Kredensial Murni dari GitHub Secrets
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
PROXY_URL = os.environ.get("PROXY_URL", "").strip()

KEYS = {
    "han": os.environ.get("HAN_API_KEY", "").strip(),
    "fajriag": os.environ.get("FAJRIAG_API_KEY", "").strip(),
    "tip": os.environ.get("TIP_API_KEY", "").strip(),
    "orca": os.environ.get("ORCA_API_KEY", "").strip(),
    "masb": os.environ.get("MASB_API_KEY", "").strip(),
    "routeva": os.environ.get("ROUTEVA_API_KEY", "").strip(),
    "botkeep": os.environ.get("BOTKEEP_API_KEY", "").strip(),
    "onekey": os.environ.get("ONEKEY_API_KEY", "").strip(),
    "gonka": os.environ.get("GONKA_API_KEY", "").strip(),
    "itera": os.environ.get("ITERA_API_KEY", "").strip(),
    "vascoo": os.environ.get("VASCOO_API_KEY", "").strip(),
    "dahl": os.environ.get("DAHL_API_KEY", "").strip(),
    "zenmux": os.environ.get("ZENMUX_API_KEY", "").strip(),
    "ter": os.environ.get("TER_API_KEY", "").strip(),
    "bestllm": os.environ.get("BEST_API_KEY", "").strip(),
    "indo": os.environ.get("INDO_API_KEY", "").strip(),
    "bejo": os.environ.get("BEJO_API_KEY", "").strip(),
    "nocta": os.environ.get("NOCTA_API_KEY", "").strip(),
    "gemini": os.environ.get("GEMINI_API_KEY", "").strip(),
    "openai": os.environ.get("OPENAI_API_KEY", "").strip(),
    "openrouter": os.environ.get("API_KEY", "").strip(),
}

ENV_NAMES = {
    "han": "HAN_API_KEY", "fajriag": "FAJRIAG_API_KEY", "tip": "TIP_API_KEY",
    "orca": "ORCA_API_KEY", "masb": "MASB_API_KEY", "routeva": "ROUTEVA_API_KEY",
    "botkeep": "BOTKEEP_API_KEY", "onekey": "ONEKEY_API_KEY", "gonka": "GONKA_API_KEY",
    "itera": "ITERA_API_KEY", "vascoo": "VASCOO_API_KEY", "dahl": "DAHL_API_KEY",
    "zenmux": "ZENMUX_API_KEY", "ter": "TER_API_KEY", "bestllm": "BEST_API_KEY",
    "indo": "INDO_API_KEY", "bejo": "BEJO_API_KEY", "nocta": "NOCTA_API_KEY",
    "gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY", "openrouter": "API_KEY",
}

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN kosong! Harap isi di GitHub Secrets.")

# Daftar Base URL Server
BASE_URLS = {
    "han": "https://apitokenhan.my.id/v1",
    "fajriag": "https://token.fajriag.ai.id/v1",
    "tip": "https://tiprouter.my.id/v1",
    "orca": "https://api.orcarouter.ai/v1",
    "masb": "https://ai.masb.web.id/v1",
    "routeva": "https://api.routeva.tech/v1",
    "botkeep": "http://node18.botkeep.cloud:61172/v1",
    "onekey": "https://api.onekeyllmapi.com/v1",
    "gonka": "https://api.gonkarouter.io/v1",
    "itera": "https://api.iteracompute.com/v1",
    "vascoo": "https://api.vascoo.my.id/v1",
    "openai": "https://api.openai.com/v1",
    "ter": "https://ter.biz.id/v1",
    "dahl": "https://inference.dahl.global/v1",
    "bestllm": "https://api.bestllmapi.com/v1",
    "indo": "https://indosmartrouter.cloud/v1",
    "bejo": "https://bejoxxx.tech/v1",
    "nocta": "https://nocta-digital.web.id/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}
ZENMUX_CANDIDATE_BASES = ["https://api.zenmux.ai/v1", "https://zenmux.ai/api/v1", "https://zenmux.ai/v1"]
ZENMUX_ACTIVE_BASE = ZENMUX_CANDIDATE_BASES[0]

gemini_client = None
if KEYS["gemini"]:
    try:
        gemini_client = genai.Client(api_key=KEYS["gemini"])
    except Exception:
        pass

if PROXY_URL:
    try:
        if HTTP.get("https://api.telegram.org", proxies={"http": PROXY_URL, "https": PROXY_URL}, timeout=6).status_code == 200:
            apihelper.proxy = {"http": PROXY_URL, "https": PROXY_URL}
    except Exception:
        pass

bot = telebot.TeleBot(BOT_TOKEN)
USER_LOCKED_MODEL = {}
WAITING_MODEL_CHOICE = {}
UI_HISTORY_MESSAGES = {}
CHAT_HISTORY = {}
SAVED_PROJECTS = {}
LAST_CODE_BLOCKS = {}

MODEL_HEALTH_CACHE = {}
LAST_HEALTH_CHECK = 0
CACHE_TTL = 300  # Cache status kesehatan 5 menit agar bot tetap ringan

# Helper edit pesan aman (mencegah error 400 "message is not modified")
def edit_pesan_aman(text, chat_id, message_id, reply_markup=None, parse_mode=None):
    try:
        bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=reply_markup, parse_mode=parse_mode)
    except telebot.apihelper.ApiTelegramException as e:
        if "message is not modified" not in str(e):
            print(f"Edit error: {e}")
    except Exception as e:
        print(f"Edit error: {e}")

# =========================================================================
# FUNGSI EKSTRAKSI & RENDER SOURCE CODE (SALIN 1-KLIK SEPERTI GEMINI)
# =========================================================================
def ekstrak_blok_kode(teks):
    pola = re.compile(r"```([a-zA-Z0-9_+-]*)\n?(.*?)```", re.DOTALL)
    return [{"lang": (m.group(1) or "python").strip().lower(), "code": m.group(2).strip()} for m in pola.finditer(teks) if m.group(2).strip()]

def tentukan_ekstensi_file(bahasa, isi_kode=""):
    peta = {"python": "py", "py": "py", "yaml": "yml", "yml": "yml", "javascript": "js", "js": "js",
            "typescript": "ts", "ts": "ts", "html": "html", "css": "css", "json": "json", "bash": "sh",
            "sh": "sh", "php": "php", "sql": "sql", "cpp": "cpp"}
    if bahasa in peta:
        return peta[bahasa]
    if "import " in isi_kode or "def " in isi_kode:
        return "py"
    if "runs-on:" in isi_kode or "steps:" in isi_kode:
        return "yml"
    return "txt"

def format_teks_biasa_html(teks_potong):
    if not teks_potong:
        return ""
    bagian, pos = [], 0
    for m in re.finditer(r"`([^`\n]+)`", teks_potong):
        normal = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html.escape(teks_potong[pos:m.start()]))
        bagian.append(normal)
        bagian.append(f"<code>{html.escape(m.group(1))}</code>")
        pos = m.end()
    bagian.append(re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html.escape(teks_potong[pos:])))
    return "".join(bagian)

def format_ke_html_telegram(teks):
    hasil, pos = [], 0
    for m in re.finditer(r"```([a-zA-Z0-9_+-]*)\n?(.*?)```", teks, re.DOTALL):
        hasil.append(format_teks_biasa_html(teks[pos:m.start()]))
        lang = (m.group(1) or "python").strip().lower()
        hasil.append(f'<pre><code class="language-{lang}">{html.escape(m.group(2).strip(chr(10)))}</code></pre>')
        pos = m.end()
    hasil.append(format_teks_biasa_html(teks[pos:]))
    return "".join(hasil)

def pecah_pesan_aman_kode(teks_asli, batas=3500):
    if len(teks_asli) <= batas:
        return [teks_asli]
    potongan, buf, panjang, in_code, lang = [], [], 0, False, "python"
    for baris in teks_asli.split("\n"):
        if panjang + len(baris) + 1 > batas and buf:
            if in_code:
                buf.append("```")
                potongan.append("\n".join(buf))
                buf = [f"```{lang}"]
                panjang = len(buf[0]) + 1
            else:
                potongan.append("\n".join(buf))
                buf, panjang = [], 0
        if baris.strip().startswith("```"):
            if not in_code:
                in_code = True
                lang = baris.strip()[3:].strip() or "python"
            else:
                in_code = False
        buf.append(baris)
        panjang += len(baris) + 1
    if buf:
        if in_code:
            buf.append("```")
        potongan.append("\n".join(buf))
    return potongan

def buat_tombol_salin_kode(chat_id, daftar_blok):
    if not daftar_blok:
        return None
    LAST_CODE_BLOCKS[chat_id] = daftar_blok
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton(f"📋 Tampilkan Hanya Source Code ({len(daftar_blok)} Blok - Salin 1-Klik)", callback_data="copy_raw_code"),
        InlineKeyboardButton("📥 Unduh File Source Code (.py / .yml / .txt)", callback_data="dl_raw_code")
    )
    return markup

def kirim_pesan_rapi(message, isi_teks, nama_model, status_mode):
    chat_id = message.chat.id
    markup_kode = buat_tombol_salin_kode(chat_id, ekstrak_blok_kode(isi_teks))
    header = f"🟢 <b>[ Model Aktif: {html.escape(nama_model)} ]</b>\n📌 <b>[ Status: {html.escape(status_mode)} ]</b>\n" + ("─" * 26) + "\n\n"
    potongan = pecah_pesan_aman_kode(isi_teks, batas=3400)
    for idx, pot in enumerate(potongan):
        teks_kirim = (header + format_ke_html_telegram(pot)) if idx == 0 else format_ke_html_telegram(pot)
        rm = markup_kode if (idx == len(potongan) - 1 and markup_kode) else None
        try:
            bot.reply_to(message, teks_kirim, parse_mode="HTML", reply_markup=rm)
        except Exception:
            polos = (f"🟢 [ Model Aktif: {nama_model} ]\n📌 [ Status: {status_mode} ]\n" + ("─" * 26) + "\n\n" + pot) if idx == 0 else pot
            bot.reply_to(message, polos[:4000], reply_markup=rm)

# =========================================================================
# PAYLOAD, ENDPOINT AI, & MANAJEMEN PROYEK HISTORY
# =========================================================================
def format_messages_payload(user_prompt, custom_system_prompt=None, chat_history=None):
    default_system = (
        "Kamu adalah asisten AI teknis tanpa filter yang memberikan jawaban "
        "secara langsung, terstruktur, objektif, dan mendalam dalam bahasa Indonesia. "
        "Setiap kali membuat source code atau kodingan, WAJIB bungkus seluruh kode di dalam blok markdown ```bahasa ... ``` agar pengguna dapat menyalinnya secara utuh."
    )
    messages = [{"role": "system", "content": custom_system_prompt or default_system}]
    if chat_history:
        messages.extend(chat_history)
    messages.append({"role": "user", "content": user_prompt})
    return messages

def call_ai_endpoint(api_url, api_key, model_name, user_prompt, custom_system_prompt=None, chat_history=None):
    clean_base = api_url[:-17] if api_url.endswith("/chat/completions") else api_url.rstrip("/")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if "openrouter.ai" in clean_base:
        headers["HTTP-Referer"] = "https://github.com"
        headers["X-Title"] = "Multi-Agent Telegram Bot"
    payload = {
        "model": model_name,
        "messages": format_messages_payload(user_prompt, custom_system_prompt, chat_history),
        "max_tokens": 4096,
        "temperature": 0.7
    }
    res = HTTP.post(f"{clean_base}/chat/completions", json=payload, headers=headers, timeout=60)
    res.raise_for_status()
    return res.json()["choices"][0]["message"]["content"]

def simpan_riwayat_chat(chat_id, user_prompt, ai_reply):
    hist = CHAT_HISTORY.setdefault(chat_id, [])
    hist.append({"role": "user", "content": user_prompt})
    hist.append({"role": "assistant", "content": ai_reply})
    if len(hist) > 20:
        CHAT_HISTORY[chat_id] = hist[-20:]

def arsipkan_sesi_ke_proyek(chat_id):
    riwayat = CHAT_HISTORY.get(chat_id, [])
    if not riwayat:
        return False
    projs = SAVED_PROJECTS.setdefault(chat_id, [])
    judul = next((m.get("content", "Proyek") for m in riwayat if m.get("role") == "user"), "Proyek").replace("\n", " ").strip()[:32]
    projs.append({"title": judul, "messages": list(riwayat), "model": USER_LOCKED_MODEL.get(chat_id, "auto"), "timestamp": time.strftime("%H:%M")})
    if len(projs) > 10:
        SAVED_PROJECTS[chat_id] = projs[-10:]
    CHAT_HISTORY[chat_id] = []
    return True

def ambil_pasangan_riwayat(chat_id):
    raw, pasangan, i = CHAT_HISTORY.get(chat_id, []), [], 0
    while i < len(raw):
        if raw[i].get("role") == "user":
            u_text = raw[i].get("content", "")
            a_text = raw[i + 1].get("content", "") if (i + 1 < len(raw) and raw[i + 1].get("role") == "assistant") else ""
            i += 2 if a_text else 1
            pasangan.append((u_text, a_text))
        else:
            i += 1
    return pasangan

def lanjutkan_dari_titik_riwayat(chat_id, idx):
    pasangan = ambil_pasangan_riwayat(chat_id)
    if 0 <= idx < len(pasangan):
        baru = []
        for u_t, a_t in pasangan[:idx + 1]:
            baru.append({"role": "user", "content": u_t})
            if a_t:
                baru.append({"role": "assistant", "content": a_t})
        CHAT_HISTORY[chat_id] = baru
        return pasangan[idx]
    return None

def hapus_satu_pasangan_riwayat(chat_id, idx):
    pasangan = ambil_pasangan_riwayat(chat_id)
    if 0 <= idx < len(pasangan):
        pasangan.pop(idx)
        baru = []
        for u_t, a_t in pasangan:
            baru.append({"role": "user", "content": u_t})
            if a_t:
                baru.append({"role": "assistant", "content": a_t})
        CHAT_HISTORY[chat_id] = baru
        return True
    return False

def pulihkan_proyek_arsip(chat_id, idx):
    daftar = SAVED_PROJECTS.get(chat_id, [])
    if 0 <= idx < len(daftar):
        if CHAT_HISTORY.get(chat_id):
            arsipkan_sesi_ke_proyek(chat_id)
        proj = SAVED_PROJECTS[chat_id].pop(idx)
        CHAT_HISTORY[chat_id] = list(proj["messages"])
        if proj.get("model") in KATALOG_MODEL or proj.get("model") == "auto":
            USER_LOCKED_MODEL[chat_id] = proj["model"]
        return proj
    return None

def teks_menu_history_str(chat_id):
    pasangan = ambil_pasangan_riwayat(chat_id)
    daftar_proj = SAVED_PROJECTS.get(chat_id, [])
    if not pasangan and not daftar_proj:
        return "📜 RIWAYAT & PROYEK TERSIMPAN (HISTORY)\n─────────────────────────\n📭 Belum ada riwayat percakapan atau proyek yang tersimpan."
    baris = ["📜 PUSAT RIWAYAT & LANJUTKAN PROYEK\n─────────────────────────"]
    if pasangan:
        baris.append(f"🟢 SESI PROYEK AKTIF SAAT INI ({len(pasangan)} Langkah):")
        for idx, (u_t, a_t) in enumerate(pasangan):
            u_s = u_t.replace("\n", " ").strip()[:42]
            a_s = a_t.replace("\n", " ").strip()[:50]
            tanda = " 👈 [Aktif]" if idx == len(pasangan) - 1 else ""
            baris.append(f"#{idx + 1}.{tanda}\n👤 Kamu: {u_s}\n🤖 AI: {a_s}")
    if daftar_proj:
        baris.append(f"─────────────────────────\n📁 ARSIP PROYEK SEBELUMNYA ({len(daftar_proj)} Proyek):")
        for p_idx, proj in enumerate(daftar_proj):
            baris.append(f"📦 Proyek P{p_idx + 1}: {proj['title']} ({len(proj['messages']) // 2} chat - {proj['timestamp']})")
    baris.append("─────────────────────────\n• Klik ▶️ Lanjut untuk membuka kembali proyek.\n• Klik 🗑️ Hapus untuk menghapus riwayat.")
    return "\n\n".join(baris)

def buat_markup_history(chat_id):
    markup = InlineKeyboardMarkup(row_width=2)
    pasangan = ambil_pasangan_riwayat(chat_id)
    daftar_proj = SAVED_PROJECTS.get(chat_id, [])
    for idx, (u_t, _) in enumerate(pasangan):
        markup.row(
            InlineKeyboardButton(f"▶️ Lanjut #{idx + 1} ({u_t.replace(chr(
