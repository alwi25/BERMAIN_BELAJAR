import os
import time
import re
import html
import io
from concurrent.futures import ThreadPoolExecutor, as_completed
import telebot
from telebot import apihelper
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import urllib.parse
import random
import urllib3
from google import genai

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 1. Kredensial Murni dari GitHub Secrets
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
PROXY_URL = os.environ.get("PROXY_URL", "").strip()
MASB_API_KEY = os.environ.get("MASB_API_KEY", "").strip()
ROUTEVA_API_KEY = os.environ.get("ROUTEVA_API_KEY", "").strip()
BOTKEEP_API_KEY = os.environ.get("BOTKEEP_API_KEY", "").strip()
ONEKEY_API_KEY = os.environ.get("ONEKEY_API_KEY", "").strip()
GONKA_API_KEY = os.environ.get("GONKA_API_KEY", "").strip()
ITERA_API_KEY = os.environ.get("ITERA_API_KEY", "").strip()
VASCOO_API_KEY = os.environ.get("VASCOO_API_KEY", "").strip()
DAHL_API_KEY = os.environ.get("DAHL_API_KEY", "").strip()
ZENMUX_API_KEY = os.environ.get("ZENMUX_API_KEY", "").strip()
TER_API_KEY = os.environ.get("TER_API_KEY", "").strip()
BEST_API_KEY = os.environ.get("BEST_API_KEY", "").strip()
INDO_API_KEY = os.environ.get("INDO_API_KEY", "").strip()
BEJO_API_KEY = os.environ.get("BEJO_API_KEY", "").strip()
NOCTA_API_KEY = os.environ.get("NOCTA_API_KEY", "").strip()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
OPENROUTER_KEY = os.environ.get("API_KEY", "").strip()

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN kosong! Harap isi di GitHub Secrets.")

# Daftar Base URL Server
MASB_BASE_URL = "https://ai.masb.web.id/v1"
ROUTEVA_BASE_URL = "https://api.routeva.tech/v1"
BOTKEEP_BASE_URL = "http://node18.botkeep.cloud:61172/v1"
ONEKEY_BASE_URL = "https://api.onekeyllmapi.com/v1"
GONKA_BASE_URL = "https://api.gonkarouter.io/v1"
ITERA_BASE_URL = "https://api.iteracompute.com/v1"
VASCOO_BASE_URL = "https://api.vascoo.my.id/v1"
OPENAI_BASE_URL = "https://api.openai.com/v1"
ZENMUX_CANDIDATE_BASES = ["https://api.zenmux.ai/v1", "https://zenmux.ai/api/v1", "https://zenmux.ai/v1"]
TER_BASE_URL = "https://ter.biz.id/v1"
DAHL_BASE_URL = "https://inference.dahl.global/v1"
BEST_BASE_URL = "https://api.bestllmapi.com/v1"
INDO_BASE_URL = "https://indosmartrouter.cloud/v1"
BEJO_BASE_URL = "https://bejoxxx.tech/v1"
NOCTA_BASE_URL = "https://nocta-digital.web.id/v1"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

gemini_client = None
if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception:
        pass

use_proxy = False
if PROXY_URL:
    try:
        test = requests.get("https://api.telegram.org", proxies={"http": PROXY_URL, "https": PROXY_URL}, timeout=8)
        if test.status_code == 200:
            use_proxy = True
            apihelper.proxy = {'http': PROXY_URL, 'https': PROXY_URL}
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

# =========================================================================
# FUNGSI EKSTRAKSI & RENDER SOURCE CODE (SALIN 1-KLIK SEPERTI GEMINI)
# =========================================================================
def ekstrak_blok_kode(teks):
    pola = re.compile(r"```([a-zA-Z0-9_+-]*)\n?(.*?)```", re.DOTALL)
    hasil = []
    for match in pola.finditer(teks):
        bahasa = (match.group(1) or "python").strip().lower()
        isi_kode = match.group(2).strip()
        if isi_kode:
            hasil.append({"lang": bahasa, "code": isi_kode})
    return hasil

def tentukan_ekstensi_file(bahasa, isi_kode=""):
    peta_eks = {
        "python": "py", "py": "py",
        "yaml": "yml", "yml": "yml",
        "javascript": "js", "js": "js",
        "typescript": "ts", "ts": "ts",
        "html": "html", "css": "css",
        "json": "json", "bash": "sh", "sh": "sh",
        "php": "php", "sql": "sql", "cpp": "cpp"
    }
    if bahasa in peta_eks:
        return peta_eks[bahasa]
    if "import " in isi_kode or "def " in isi_kode:
        return "py"
    if "runs-on:" in isi_kode or "steps:" in isi_kode:
        return "yml"
    return "txt"

def format_ke_html_telegram(teks):
    pola_blok = re.compile(r"```([a-zA-Z0-9_+-]*)\n?(.*?)```", re.DOTALL)
    hasil_akhir = []
    posisi_terakhir = 0

    for match in pola_blok.finditer(teks):
        teks_sebelum = teks[posisi_terakhir:match.start()]
        hasil_akhir.append(format_teks_biasa_html(teks_sebelum))

        bahasa = (match.group(1) or "python").strip().lower()
        kode_mentah = match.group(2).strip("\n")
        kode_aman = html.escape(kode_mentah)
        hasil_akhir.append(f'<pre><code class="language-{bahasa}">{kode_aman}</code></pre>')
        posisi_terakhir = match.end()

    hasil_akhir.append(format_teks_biasa_html(teks[posisi_terakhir:]))
    return "".join(hasil_akhir)

def format_teks_biasa_html(teks_potong):
    if not teks_potong:
        return ""
    pola_inline = re.compile(r"`([^`\n]+)`")
    bagian = []
    pos = 0
    for m in pola_inline.finditer(teks_potong):
        normal = html.escape(teks_potong[pos:m.start()])
        normal = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", normal)
        bagian.append(normal)
        bagian.append(f"<code>{html.escape(m.group(1))}</code>")
        pos = m.end()
    sisa = html.escape(teks_potong[pos:])
    sisa = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", sisa)
    bagian.append(sisa)
    return "".join(bagian)

def pecah_pesan_aman_kode(teks_asli, batas=3500):
    if len(teks_asli) <= batas:
        return [teks_asli]

    baris_list = teks_asli.split("\n")
    potongan_pesan = []
    buffer_baris = []
    panjang_sekarang = 0
    di_dalam_kode = False
    bahasa_aktif = "python"

    for baris in baris_list:
        tambahan_len = len(baris) + 1
        if panjang_sekarang + tambahan_len > batas and buffer_baris:
            if di_dalam_kode:
                buffer_baris.append("```")
                potongan_pesan.append("\n".join(buffer_baris))
                buffer_baris = [f"```{bahasa_aktif}"]
                panjang_sekarang = len(buffer_baris[0]) + 1
            else:
                potongan_pesan.append("\n".join(buffer_baris))
                buffer_baris = []
                panjang_sekarang = 0

        stripped = baris.strip()
        if stripped.startswith("```"):
            if not di_dalam_kode:
                di_dalam_kode = True
                lang_tag = stripped[3:].strip()
                bahasa_aktif = lang_tag if lang_tag else "python"
            else:
                di_dalam_kode = False

        buffer_baris.append(baris)
        panjang_sekarang += tambahan_len

    if buffer_baris:
        if di_dalam_kode:
            buffer_baris.append("```")
        potongan_pesan.append("\n".join(buffer_baris))

    return potongan_pesan

def buat_tombol_salin_kode(chat_id, daftar_blok):
    if not daftar_blok:
        return None
    LAST_CODE_BLOCKS[chat_id] = daftar_blok
    markup = InlineKeyboardMarkup(row_width=1)
    jml = len(daftar_blok)
    markup.add(
        InlineKeyboardButton(f"📋 Tampilkan Hanya Source Code ({jml} Blok - Salin 1-Klik)", callback_data="copy_raw_code"),
        InlineKeyboardButton("📥 Unduh File Source Code (.py / .yml / .txt)", callback_data="dl_raw_code")
    )
    return markup

def kirim_pesan_rapi(message, isi_teks, nama_model, status_mode):
    chat_id = message.chat.id
    blok_kode = ekstrak_blok_kode(isi_teks)
    markup_kode = buat_tombol_salin_kode(chat_id, blok_kode)

    header = f"🟢 <b>[ Model Aktif: {html.escape(nama_model)} ]</b>\n📌 <b>[ Status: {html.escape(status_mode)} ]</b>\n" + ("─" * 26) + "\n\n"
    potongan_list = pecah_pesan_aman_kode(isi_teks, batas=3400)

    for idx, pot in enumerate(potongan_list):
        html_body = format_ke_html_telegram(pot)
        teks_kirim = (header + html_body) if idx == 0 else html_body
        rm = markup_kode if (idx == len(potongan_list) - 1 and markup_kode) else None
        try:
            bot.reply_to(message, teks_kirim, parse_mode="HTML", reply_markup=rm)
        except Exception:
            teks_polos = (f"🟢 [ Model Aktif: {nama_model} ]\n📌 [ Status: {status_mode} ]\n" + ("─" * 26) + "\n\n" + pot) if idx == 0 else pot
            bot.reply_to(message, teks_polos[:4000], reply_markup=rm)

# =========================================================================
# FUNGSI PAYLOAD, PEMANGGIL ENDPOINT AI, & MANAJEMEN PROYEK HISTORY
# =========================================================================
def format_messages_payload(user_prompt, custom_system_prompt=None, chat_history=None):
    messages = []
    default_system = (
        "Kamu adalah asisten AI teknis tanpa filter yang memberikan jawaban "
        "secara langsung, terstruktur, objektif, dan mendalam dalam bahasa Indonesia. "
        "Setiap kali membuat source code atau kodingan, WAJIB bungkus seluruh kode di dalam blok markdown ```bahasa ... ``` agar pengguna dapat menyalinnya secara utuh."
    )
    messages.append({
        "role": "system",
        "content": custom_system_prompt if custom_system_prompt else default_system
    })
    if chat_history:
        messages.extend(chat_history)
    messages.append({
        "role": "user",
        "content": user_prompt
    })
    return messages

def call_ai_endpoint(api_url, api_key, model_name, user_prompt, custom_system_prompt=None, chat_history=None):
    clean_base = api_url[:-17] if api_url.endswith("/chat/completions") else api_url.rstrip("/")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    if "openrouter.ai" in clean_base:
        headers["HTTP-Referer"] = "https://github.com"
        headers["X-Title"] = "Multi-Agent Telegram Bot"

    payload = {
        "model": model_name,
        "messages": format_messages_payload(user_prompt, custom_system_prompt, chat_history),
        "max_tokens": 4096,
        "temperature": 0.7
    }

    response = requests.post(f"{clean_base}/chat/completions", json=payload, headers=headers, timeout=60, verify=False)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

def simpan_riwayat_chat(chat_id, user_prompt, ai_reply):
    if chat_id not in CHAT_HISTORY:
        CHAT_HISTORY[chat_id] = []
    CHAT_HISTORY[chat_id].append({"role": "user", "content": user_prompt})
    CHAT_HISTORY[chat_id].append({"role": "assistant", "content": ai_reply})
    if len(CHAT_HISTORY[chat_id]) > 20:
        CHAT_HISTORY[chat_id] = CHAT_HISTORY[chat_id][-20:]

def arsipkan_sesi_ke_proyek(chat_id):
    riwayat_sekarang = CHAT_HISTORY.get(chat_id, [])
    if not riwayat_sekarang:
        return False
    if chat_id not in SAVED_PROJECTS:
        SAVED_PROJECTS[chat_id] = []

    pesan_pertama = next((m.get("content", "Proyek") for m in riwayat_sekarang if m.get("role") == "user"), "Proyek")
    judul = pesan_pertama.replace("\n", " ").strip()[:32]
    SAVED_PROJECTS[chat_id].append({
        "title": judul,
        "messages": list(riwayat_sekarang),
        "model": USER_LOCKED_MODEL.get(chat_id, "auto"),
        "timestamp": time.strftime("%H:%M")
    })
    if len(SAVED_PROJECTS[chat_id]) > 10:
        SAVED_PROJECTS[chat_id] = SAVED_PROJECTS[chat_id][-10:]
    CHAT_HISTORY[chat_id] = []
    return True

def ambil_pasangan_riwayat(chat_id):
    raw = CHAT_HISTORY.get(chat_id, [])
    pasangan = []
    i = 0
    while i < len(raw):
        if raw[i].get("role") == "user":
            u_text = raw[i].get("content", "")
            a_text = ""
            if i + 1 < len(raw) and raw[i + 1].get("role") == "assistant":
                a_text = raw[i + 1].get("content", "")
                i += 2
            else:
                i += 1
            pasangan.append((u_text, a_text))
        else:
            i += 1
    return pasangan

def lanjutkan_dari_titik_riwayat(chat_id, index_pasangan):
    pasangan = ambil_pasangan_riwayat(chat_id)
    if 0 <= index_pasangan < len(pasangan):
        pasangan_aktif = pasangan[:index_pasangan + 1]
        baru = []
        for u_t, a_t in pasangan_aktif:
            baru.append({"role": "user", "content": u_t})
            if a_t:
                baru.append({"role": "assistant", "content": a_t})
        CHAT_HISTORY[chat_id] = baru
        return pasangan[index_pasangan]
    return None

def hapus_satu_pasangan_riwayat(chat_id, index_pasangan):
    pasangan = ambil_pasangan_riwayat(chat_id)
    if 0 <= index_pasangan < len(pasangan):
        pasangan.pop(index_pasangan)
        baru = []
        for u_t, a_t in pasangan:
            baru.append({"role": "user", "content": u_t})
            if a_t:
                baru.append({"role": "assistant", "content": a_t})
        CHAT_HISTORY[chat_id] = baru
        return True
    return False

def pulihkan_proyek_arsip(chat_id, idx_proj):
    daftar_proj = SAVED_PROJECTS.get(chat_id, [])
    if 0 <= idx_proj < len(daftar_proj):
        if CHAT_HISTORY.get(chat_id):
            arsipkan_sesi_ke_proyek(chat_id)
        proj = SAVED_PROJECTS[chat_id].pop(idx_proj)
        CHAT_HISTORY[chat_id] = list(proj["messages"])
        if proj.get("model") and (proj["model"] in KATALOG_MODEL or proj["model"] == "auto"):
            USER_LOCKED_MODEL[chat_id] = proj["model"]
        return proj
    return None

def hapus_proyek_arsip(chat_id, idx_proj):
    daftar_proj = SAVED_PROJECTS.get(chat_id, [])
    if 0 <= idx_proj < len(daftar_proj):
        daftar_proj.pop(idx_proj)
        return True
    return False

def teks_menu_history_str(chat_id):
    pasangan = ambil_pasangan_riwayat(chat_id)
    daftar_proj = SAVED_PROJECTS.get(chat_id, [])

    if not pasangan and not daftar_proj:
        return (
            "📜 RIWAYAT & PROYEK TERSIMPAN (HISTORY)\n"
            "─────────────────────────\n"
            "📭 Belum ada riwayat percakapan atau proyek yang tersimpan.\n\n"
            "💡 Setiap kali kamu mengobrol atau membuat kodingan dengan AI, riwayatnya otomatis tercatat di sini dan bisa dipilih kembali kapan saja."
        )

    baris = ["📜 PUSAT RIWAYAT & LANJUTKAN PROYEK\n─────────────────────────"]

    if pasangan:
        baris.append(f"🟢 SESI PROYEK AKTIF SAAT INI ({len(pasangan)} Langkah):")
        for idx, (u_t, a_t) in enumerate(pasangan):
            u_clean = u_t.replace("\n", " ").strip()
            a_clean = a_t.replace("\n", " ").strip()
            u_short = u_clean[:42] + ("..." if len(u_clean) > 42 else "")
            a_short = a_clean[:50] + ("..." if len(a_clean) > 50 else "")
            tanda_ujung = " 👈 [Posisi Aktif]" if idx == len(pasangan) - 1 else ""
            baris.append(f"#{idx + 1}.{tanda_ujung}\n👤 Kamu: {u_short}\n🤖 AI: {a_short}")

    if daftar_proj:
        baris.append(f"─────────────────────────\n📁 ARSIP PROYEK SEBELUMNYA ({len(daftar_proj)} Proyek):")
        for p_idx, proj in enumerate(daftar_proj):
            jml_langkah = len(proj["messages"]) // 2
            baris.append(f"📦 Proyek P{p_idx + 1}: {proj['title']} ({jml_langkah} chat - {proj['timestamp']})")

    baris.append(
        "─────────────────────────\n"
        "💡 Cara Melanjutkan atau Menghapus:\n"
        "• Klik ▶️ Lanjut — Memilih & membuka kembali riwayat/proyek tersebut untuk dilanjutkan.\n"
        "• Klik 🗑️ Hapus — Menghapus riwayat yang dipilih."
    )
    return "\n\n".join(baris)

def buat_markup_history(chat_id):
    markup = InlineKeyboardMarkup(row_width=2)
    pasangan = ambil_pasangan_riwayat(chat_id)
    daftar_proj = SAVED_PROJECTS.get(chat_id, [])

    if pasangan:
        for idx, (u_t, _) in enumerate(pasangan):
            cuplikan = u_t.replace("\n", " ").strip()[:14]
            markup.row(
                InlineKeyboardButton(f"▶️ Lanjut #{idx + 1} ({cuplikan})", callback_data=f"reshist_{idx}"),
                InlineKeyboardButton(f"🗑️ Hapus #{idx + 1}", callback_data=f"delhist_{idx}")
            )
        markup.row(
            InlineKeyboardButton("💾 Simpan Proyek & Mulai Topik Baru", callback_data="archive_new")
        )

    if daftar_proj:
        for p_idx, proj in enumerate(daftar_proj):
            judul_pendek = proj["title"][:14]
            markup.row(
                InlineKeyboardButton(f"📂 Buka Proyek P{p_idx + 1} ({judul_pendek})", callback_data=f"resproj_{p_idx}"),
                InlineKeyboardButton(f"🗑️ Hapus P{p_idx + 1}", callback_data=f"delproj_{p_idx}")
            )

    if pasangan or daftar_proj:
        markup.row(InlineKeyboardButton("🔥 Hapus Semua History & Arsip", callback_data="clear_all_hist"))

    markup.row(InlineKeyboardButton("🎛 Kembali ke Menu Utama Model", callback_data="back_main"))
    return markup

def bersihkan_instruksi_sebelumnya(chat_id, user_msg_id=None):
    if user_msg_id:
        try:
            bot.delete_message(chat_id, user_msg_id)
        except Exception:
            pass

    daftar_id_lama = UI_HISTORY_MESSAGES.get(chat_id, [])
    for mid in daftar_id_lama:
        try:
            bot.delete_message(chat_id, mid)
        except Exception:
            pass
    UI_HISTORY_MESSAGES[chat_id] = []

def catat_pesan_ui(chat_id, msg_obj):
    if not msg_obj:
        return
    if chat_id not in UI_HISTORY_MESSAGES:
        UI_HISTORY_MESSAGES[chat_id] = []
    if msg_obj.message_id not in UI_HISTORY_MESSAGES[chat_id]:
        UI_HISTORY_MESSAGES[chat_id].append(msg_obj.message_id)

# 2. Penyisir Model Otomatis (Masb AI, Routeva, BotKeep, OneKey, GonkaRouter, ZenMUX, 9Router, Dahl)
ZENMUX_ACTIVE_BASE = ZENMUX_CANDIDATE_BASES[0]

def sisir_endpoint_umum(base_url, api_key, defaults):
    priorities = ["uncensored", "deepseek", "qwen", "claude", "gpt", "glm", "llama", "coder", "hermes", "dolphin", "gemini"]
    found = []
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        res = requests.get(f"{base_url}/models", headers=headers, timeout=10, verify=False)
        if res.status_code == 200:
            data_json = res.json()
            raw_list = data_json.get("data", data_json) if isinstance(data_json, dict) else data_json
            ids = []
            if isinstance(raw_list, list):
                for m in raw_list:
                    if isinstance(m, dict) and m.get("id"):
                        ids.append(str(m.get("id")))
                    elif isinstance(m, str):
                        ids.append(m)
            for p in priorities:
                for mid in ids:
                    if p in mid.lower() and mid not in found:
                        found.append(mid)
            for mid in ids:
                if mid not in found:
                    found.append(mid)
    except Exception:
        pass
    for d in defaults:
        if d not in found:
            found.append(d)
    return found

def sisir_model_masb():
    defaults = ["deepseek-r1", "deepseek-v3", "qwen-2.5-coder-32b-instruct", "claude-3-7-sonnet", "gpt-4o", "llama-3.3-70b-instruct"]
    return sisir_endpoint_umum(MASB_BASE_URL, MASB_API_KEY, defaults)

def sisir_model_routeva():
    defaults = ["deepseek-r1", "deepseek-v3", "qwen-2.5-coder-32b-instruct", "claude-3-7-sonnet", "gpt-4o", "llama-3.3-70b-instruct"]
    return sisir_endpoint_umum(ROUTEVA_BASE_URL, ROUTEVA_API_KEY, defaults)

def sisir_model_botkeep():
    defaults = ["deepseek-r1", "deepseek-v3", "qwen-2.5-coder-32b", "claude-3-7-sonnet", "gpt-4o", "llama-3.3-70b-instruct"]
    return sisir_endpoint_umum(BOTKEEP_BASE_URL, BOTKEEP_API_KEY, defaults)

def sisir_model_onekey():
    defaults = ["uncensored", "deepseek-r1", "deepseek-v3", "qwen-2.5-coder-32b-instruct", "claude-3-7-sonnet", "gpt-4o", "llama-3.3-70b-instruct"]
    return sisir_endpoint_umum(ONEKEY_BASE_URL, ONEKEY_API_KEY, defaults)

def sisir_model_gonka():
    defaults = ["deepseek-r1", "deepseek-v3", "qwen-2.5-coder-32b-instruct", "claude-3-7-sonnet", "gpt-4o", "llama-3.3-70b-instruct"]
    return sisir_endpoint_umum(GONKA_BASE_URL, GONKA_API_KEY, defaults)

def sisir_model_zenmux():
    global ZENMUX_ACTIVE_BASE
    priorities = ["hy4", "hunyuan", "tencent", "claude", "gpt", "deepseek", "qwen", "coder", "llama"]
    found = []
    if ZENMUX_API_KEY:
        headers = {"Authorization": f"Bearer {ZENMUX_API_KEY}", "User-Agent": "Mozilla/5.0"}
        for base in ZENMUX_CANDIDATE_BASES:
            try:
                res = requests.get(f"{base}/models", headers=headers, timeout=10, verify=False)
                if res.status_code == 200:
                    ids = [str(m.get("id")) for m in res.json().get("data", []) if m.get("id")]
                    if ids:
                        ZENMUX_ACTIVE_BASE = base
                        for p in priorities:
                            for mid in ids:
                                if p in mid.lower() and mid not in found:
                                    found.append(mid)
                        for mid in ids:
                            if mid not in found:
                                found.append(mid)
                        break
            except Exception:
                continue
    for d in ["tencent-hy4", "hunyuan-hy4", "deepseek-v3", "qwen-2.5-coder-32b-instruct", "claude-3-7-sonnet", "gpt-4o"]:
        if d not in found:
            found.append(d)
    return found

def sisir_model_ter():
    defaults = ["glm/glm-5.3-flash", "glm/glm-5.3", "glm-5.3-flash-jb", "glm-mommy", "glm-kratos"]
    return sisir_endpoint_umum(TER_BASE_URL, TER_API_KEY, defaults)

def sisir_model_dahl():
    defaults = ["qwen-3.8-flash", "minimax", "llama-3.1-70b", "deepseek-coder"]
    return sisir_endpoint_umum(DAHL_BASE_URL, DAHL_API_KEY, defaults)

MASB_MODELS = sisir_model_masb()
ROUTEVA_MODELS = sisir_model_routeva()
BOTKEEP_MODELS = sisir_model_botkeep()
ONEKEY_MODELS = sisir_model_onekey()
GONKA_MODELS = sisir_model_gonka()
ZENMUX_MODELS = sisir_model_zenmux()
TER_MODELS = sisir_model_ter()
DAHL_MODELS = sisir_model_dahl()

def get_bestllm_models():
    defaults = ["uncensored", "dolphin-mixtral-8x7b", "nous-hermes-2-mixtral-8x7b-dpo"]
    return sisir_endpoint_umum(BEST_BASE_URL, BEST_API_KEY, defaults)

BEST_MODELS = get_bestllm_models()

def get_openrouter_models():
    available = []
    try:
        res = requests.get(f"{OPENROUTER_BASE_URL}/models", timeout=10)
        if res.status_code == 200:
            free_ids = [m["id"] for m in res.json().get("data", []) if m.get("id", "").endswith(":free")]
            for p in ["dolphin", "hermes", "mythomax", "llama-3"]:
                for fid in free_ids:
                    if p.lower() in fid.lower() and fid not in available:
                        available.append(fid)
            for fid in free_ids:
                if fid not in available:
                    available.append(fid)
    except Exception:
        pass
    available.insert(0, "openrouter/free")
    return available

OR_MODELS = get_openrouter_models() if OPENROUTER_KEY else ["openrouter/free"]

# 3. Katalog Utama & Folder Sub-Kategori
KATALOG_MODEL = {
    "itera": {"provider": "itera", "model_id": "qwen/qwen3.8-27b", "nama": "Itera Qwen 3.8 27B (128K)", "tugas": "Koding, Tool Calling & Teks Panjang (IteraCompute)"},
    "vascoo": {"provider": "vascoo", "model_id": "uncensored-x", "nama": "Vascoo Uncensored-X", "tugas": "Teks & Roleplay Tanpa Sensor (Vascoo)"},
    "chatgpt": {"provider": "openai", "model_id": "gpt-4o", "nama": "ChatGPT 4o (OpenAI)", "tugas": "Serba Bisa, Natural & Pintar"},
    "indo": {"provider": "indo", "model_id": "qwen-uncensored", "nama": "IndoSmart Qwen", "tugas": "Teks Tanpa Sensor (IndoSmart)"},
    "best": {"provider": "bestllm", "model_id": BEST_MODELS[0], "nama": "BestLLM Uncensored", "tugas": "Teks & Roleplay Tanpa Filter"},
    "qwen": {"provider": "bejo", "model_id": "qwen3.8-27b-uncensored", "nama": "Qwen 3.8 27B (Bejoxxx)", "tugas": "Teks Tanpa Sensor & Koding"},
    "deepseek": {"provider": "nocta", "model_id": "deepseek-v4.1", "nama": "DeepSeek v4.1 (Nocta)", "tugas": "Koding, Algoritma & Bug Fixing"},
    "luna": {"provider": "nocta", "model_id": "gpt-5.6-luna", "nama": "GPT-5.6 Luna (Nocta)", "tugas": "Teks Kreatif & Natural"},
    "argon": {"provider": "gemini", "model_id": "gemini-4-argon", "nama": "Gemini 4 Argon", "tugas": "Penalaran Logika & Analisis"},
    "gemini": {"provider": "gemini", "model_id": "gemini-1.5-pro", "nama": "Gemini 1.5 Pro", "tugas": "Dokumen Panjang"},
    "flash": {"provider": "gemini", "model_id": "gemini-1.5-flash", "nama": "Gemini 1.5 Flash", "tugas": "Respon Cepat"},
    "recursive": {"provider": "openrouter", "model_id": "openrouter/free", "nama": "OpenRouter Recursive", "tugas": "Teks Multi-Model Otomatis"},
    "gambar": {"provider": "pollinations", "model_id": "flux-uncensored", "nama": "Pollinations Flux", "tugas": "Gambar & Foto Tanpa Filter"},
    "video": {"provider": "video_engine", "model_id": "director-flux-16-9", "nama": "AI Video Director", "tugas": "Skenario Video & Keyframe"}
}

def segarkan_folder_kategori():
    kunci_lama = [k for k in list(KATALOG_MODEL.keys()) if k.startswith(("masb_", "rv_", "bk_", "ok_", "gonka_", "zm_", "ter_", "dahl_"))]
    for k in kunci_lama:
        del KATALOG_MODEL[k]

    for idx, m_id in enumerate(MASB_MODELS[:12]):
        KATALOG_MODEL[f"masb_{idx}"] = {"provider": "masb", "model_id": m_id, "nama": f"Masb: {m_id}", "tugas": "Masb AI Gateway"}
    for idx, m_id in enumerate(ROUTEVA_MODELS[:12]):
        KATALOG_MODEL[f"rv_{idx}"] = {"provider": "routeva", "model_id": m_id, "nama": f"Routeva: {m_id}", "tugas": "Routeva Tech AI Gateway"}
    for idx, m_id in enumerate(BOTKEEP_MODELS[:12]):
        KATALOG_MODEL[f"bk_{idx}"] = {"provider": "botkeep", "model_id": m_id, "nama": f"BotKeep: {m_id}", "tugas": "Node18 BotKeep Cloud AI"}
    for idx, m_id in enumerate(ONEKEY_MODELS[:12]):
        KATALOG_MODEL[f"ok_{idx}"] = {"provider": "onekey", "model_id": m_id, "nama": f"OneKey: {m_id}", "tugas": "Multi-Model Gateway (OneKeyLLMAPI)"}
    for idx, m_id in enumerate(GONKA_MODELS[:12]):
        KATALOG_MODEL[f"gonka_{idx}"] = {"provider": "gonka", "model_id": m_id, "nama": f"Gonka: {m_id}", "tugas": "High-Frequency Neural Gateway (GonkaRouter)"}
    for idx, m_id in enumerate(ZENMUX_MODELS[:12]):
        KATALOG_MODEL[f"zm_{idx}"] = {"provider": "zenmux", "model_id": m_id, "nama": f"ZenMux: {m_id}", "tugas": "Agen Pengkodean & Multi-Tugas"}
    for idx, m_id in enumerate(TER_MODELS[:12]):
        KATALOG_MODEL[f"ter_{idx}"] = {"provider": "ter", "model_id": m_id, "nama": f"9Router: {m_id}", "tugas": "Model GLM 9Router"}
    for idx, m_id in enumerate(DAHL_MODELS[:12]):
        KATALOG_MODEL[f"dahl_{idx}"] = {"provider": "dahl", "model_id": m_id, "nama": f"Dahl: {m_id}", "tugas": "Open Models (Dahl Inference)"}

segarkan_folder_kategori()

# =========================================================================
# 4. SISTEM DIAGNOSA & LOGIKA PENGECEKAN STATUS MODEL (🟢 AKTIF / 🔴 MATI)
# =========================================================================
def analisis_penyebab_http(status_code, response_text):
    teks_kecil = (response_text or "").lower()
    if status_code in [401, 403]:
        return "API Key Mati / Ditolak Server (401/403). Periksa kembali API Key di GitHub Secrets."
    elif status_code == 402 or any(w in teks_kecil for w in ["insufficient", "quota", "balance", "credit"]):
        return "Kuota / Saldo Token Habis (402). Silakan isi ulang atau ganti API Key baru."
    elif status_code == 429 or any(w in teks_kecil for w in ["rate limit", "too many"]):
        return "Kuota Limit Tercapai / Terlalu Banyak Permintaan (429 Rate Limit)."
    elif status_code == 404 or any(w in teks_kecil for w in ["not found", "does not exist"]):
        return "Model Tidak Ditemukan / Sedang Dinonaktifkan oleh Server (404)."
    elif status_code in [500, 502, 503, 504]:
        return f"Server Down / Mengalami Gangguan Pusat (Error {status_code})."
    else:
        cuplikan = (response_text or "").strip()[:80].replace("\n", " ")
        return f"Gangguan Server (Kode {status_code}): {cuplikan}"

def uji_satu_model_cepat(kode_model):
    info = KATALOG_MODEL.get(kode_model)
    if not info:
        return False, "Model tidak terdaftar di katalog."

    provider = info["provider"]
    model_id = info["model_id"]

    if provider in ["pollinations", "video_engine"]:
        return True, "Layanan Visual Aktif (Gratis / Tanpa Kuota)."

    peta_kunci = {
        "masb": (MASB_API_KEY, "MASB_API_KEY", MASB_BASE_URL),
        "routeva": (ROUTEVA_API_KEY, "ROUTEVA_API_KEY", ROUTEVA_BASE_URL),
        "botkeep": (BOTKEEP_API_KEY, "BOTKEEP_API_KEY", BOTKEEP_BASE_URL),
        "onekey": (ONEKEY_API_KEY, "ONEKEY_API_KEY", ONEKEY_BASE_URL),
        "gonka": (GONKA_API_KEY, "GONKA_API_KEY", GONKA_BASE_URL),
        "itera": (ITERA_API_KEY, "ITERA_API_KEY", ITERA_BASE_URL),
        "vascoo": (VASCOO_API_KEY, "VASCOO_API_KEY", VASCOO_BASE_URL),
        "dahl": (DAHL_API_KEY, "DAHL_API_KEY", DAHL_BASE_URL),
        "ter": (TER_API_KEY, "TER_API_KEY", TER_BASE_URL),
        "zenmux": (ZENMUX_API_KEY, "ZENMUX_API_KEY", ZENMUX_ACTIVE_BASE),
        "indo": (INDO_API_KEY, "INDO_API_KEY", INDO_BASE_URL),
        "openai": (OPENAI_API_KEY, "OPENAI_API_KEY", OPENAI_BASE_URL),
        "bestllm": (BEST_API_KEY, "BEST_API_KEY", BEST_BASE_URL),
        "bejo": (BEJO_API_KEY, "BEJO_API_KEY", BEJO_BASE_URL),
        "nocta": (NOCTA_API_KEY, "NOCTA_API_KEY", NOCTA_BASE_URL),
        "openrouter": (OPENROUTER_KEY, "API_KEY (OpenRouter)", OPENROUTER_BASE_URL)
    }

    if provider == "gemini":
        if not GEMINI_API_KEY or not gemini_client:
            return False, "Variabel GEMINI_API_KEY belum diisi di GitHub Secrets."
        try:
            resp = gemini_client.models.generate_content(model=model_id, contents="ping")
            if resp and resp.text:
                return True, "Model Aktif & Merespons Normal."
            return False, "Respons kosong dari Google Gemini."
        except Exception as e:
            err_s = str(e).lower()
            if "quota" in err_s or "429" in err_s or "exhausted" in err_s:
                return False, "Kuota Limit Gemini Habis (429 Resource Exhausted)."
            elif "key" in err_s or "400" in err_s or "403" in err_s:
                return False, "GEMINI_API_KEY Tidak Valid / Mati."
            elif "not found" in err_s or "404" in err_s:
                return False, f"Model {model_id} belum tersedia untuk akun API Key ini (404)."
            return False, f"Gangguan Gemini: {str(e)[:80]}"

    if provider in peta_kunci:
        kunci, nama_env, base_url = peta_kunci[provider]
        if not kunci:
            return False, f"API Key Kosong ({nama_env} belum dipasang di GitHub Secrets)."

        headers = {"Authorization": f"Bearer {kunci}", "Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
        payload = {"model": model_id, "messages": format_messages_payload("hi"), "max_tokens": 5}
        try:
            res = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=15, verify=False)
            if res.status_code == 200:
                data = res.json()
                if "choices" in data and len(data["choices"]) > 0:
                    return True, "Model Aktif & Merespons Normal (200 OK)."
                if "error" in data:
                    return False, analisis_penyebab_http(400, str(data["error"]))
                return True, "Server Terhubung (200 OK)."
            else:
                return False, analisis_penyebab_http(res.status_code, res.text)
        except requests.exceptions.Timeout:
            return False, "Server Down / Antrean Penuh (Timeout > 15 detik)."
        except requests.exceptions.ConnectionError:
            return False, "Server Down / Port atau Domain Tidak Dapat Dihubungi (Connection Error)."
        except Exception as e:
            return False, f"Kesalahan Jaringan: {str(e)[:70]}"

    return False, "Provider tidak dikenali."

def periksa_kesehatan_serentak(daftar_kode=None):
    global LAST_HEALTH_CHECK
    target_list = daftar_kode if daftar_kode else list(KATALOG_MODEL.keys())
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_map = {executor.submit(uji_satu_model_cepat, kode): kode for kode in target_list}
        for future in as_completed(future_map):
            kode = future_map[future]
            try:
                status_ok, alasan = future.result()
                MODEL_HEALTH_CACHE[kode] = {"active": status_ok, "reason": alasan}
            except Exception as e:
                MODEL_HEALTH_CACHE[kode] = {"active": False, "reason": f"Error pengecekan: {e}"}
    LAST_HEALTH_CHECK = time.time()

def ambil_ikon_status(kode_model, mode_aktif):
    info_sehat = MODEL_HEALTH_CACHE.get(kode_model)
    status_warna = "🟢" if (info_sehat and info_sehat.get("active")) else ("🔴" if info_sehat else "⚪")
    gembok = "🔒" if kode_model == mode_aktif else ""
    return f"{status_warna}{gembok}"

def ambil_status_kategori(awalan):
    kumpulan = [k for k in KATALOG_MODEL if k.startswith(awalan)]
    aktif_jml = sum(1 for k in kumpulan if MODEL_HEALTH_CACHE.get(k, {}).get("active", False))
    total_jml = len(kumpulan)
    ikon = "🟢" if aktif_jml > 0 else "🔴"
    return ikon, aktif_jml, total_jml

# 5. Pembuat Menu Telegram dengan Indikator 🟢 Hijau & 🔴 Merah
def buat_menu_utama(mode_aktif, chat_id=None):
    markup = InlineKeyboardMarkup(row_width=2)

    ikon_masb, akt_masb, tot_masb = ambil_status_kategori("masb_")
    ikon_rv, akt_rv, tot_rv = ambil_status_kategori("rv_")
    ikon_bk, akt_bk, tot_bk = ambil_status_kategori("bk_")
    ikon_ok, akt_ok, tot_ok = ambil_status_kategori("ok_")
    ikon_gk, akt_gk, tot_gk = ambil_status_kategori("gonka_")
    ikon_zm, akt_zm, tot_zm = ambil_status_kategori("zm_")
    ikon_ter, akt_ter, tot_ter = ambil_status_kategori("ter_")
    ikon_dahl, akt_dahl, tot_dahl = ambil_status_kategori("dahl_")

    markup.row(InlineKeyboardButton(f"{ikon_masb}📂 MASB AI ({akt_masb}/{tot_masb} Aktif)", callback_data="cat_masb"))
    markup.row(InlineKeyboardButton(f"{ikon_rv}📂 ROUTEVA TECH ({akt_rv}/{tot_rv} Aktif)", callback_data="cat_routeva"))
    markup.row(InlineKeyboardButton(f"{ikon_bk}📂 BOTKEEP NODE18 ({akt_bk}/{tot_bk} Aktif)", callback_data="cat_botkeep"))
    markup.row(InlineKeyboardButton(f"{ikon_ok}📂 ONEKEY LLM ({akt_ok}/{tot_ok} Aktif)", callback_data="cat_onekey"))
    markup.row(InlineKeyboardButton(f"{ikon_gk}📂 GONKAROUTER ({akt_gk}/{tot_gk} Aktif)", callback_data="cat_gonka"))
    markup.row(InlineKeyboardButton(f"{ikon_zm}📂 ZENMUX ({akt_zm}/{tot_zm} Aktif)", callback_data="cat_zenmux"))
    markup.row(InlineKeyboardButton(f"{ikon_ter}📂 9ROUTER GLM ({akt_ter}/{tot_ter} Aktif)", callback_data="cat_ter"))
    markup.row(InlineKeyboardButton(f"{ikon_dahl}📂 DAHL INFERENCE ({akt_dahl}/{tot_dahl} Aktif)", callback_data="cat_dahl"))

    tombol_list = []
    for kode, info in KATALOG_MODEL.items():
        if kode.startswith(("masb_", "rv_", "bk_", "ok_", "gonka_", "zm_", "ter_", "dahl_")):
            continue
        ikon = ambil_ikon_status(kode, mode_aktif)
        tombol_list.append(InlineKeyboardButton(f"{ikon} {kode.upper()} ({info['nama'][:10]})", callback_data=f"lock_{kode}"))
    markup.add(*tombol_list)

    jml_hist = len(ambil_pasangan_riwayat(chat_id)) if chat_id else 0
    jml_proj = len(SAVED_PROJECTS.get(chat_id, [])) if chat_id else 0
    markup.row(InlineKeyboardButton(f"📜 RIWAYAT & LANJUTKAN PROYEK ({jml_hist} Chat | {jml_proj} Arsip)", callback_data="menu_history"))
    markup.row(InlineKeyboardButton("🔄 CEK ULANG STATUS SEMUA MODEL (PING)", callback_data="ping_all"))
    markup.row(InlineKeyboardButton(f"{'✅ ' if mode_aktif == 'auto' else '🤖 '}MODE OTOMATIS (Hanya Model 🟢)", callback_data="lock_auto"))
    return markup

def buat_submenu_folder(mode_aktif, awalan, callback_refresh):
    markup = InlineKeyboardMarkup(row_width=2)
    tombol = []
    for kode, info in KATALOG_MODEL.items():
        if kode.startswith(awalan):
            ikon = ambil_ikon_status(kode, mode_aktif)
            tombol.append(InlineKeyboardButton(f"{ikon} {info['model_id'][:18]}", callback_data=f"lock_{kode}"))
    markup.add(*tombol)
    markup.row(InlineKeyboardButton("🔄 Cek Status & Sisir Ulang Folder Ini", callback_data=callback_refresh))
    markup.row(InlineKeyboardButton("⬅️ Kembali ke Menu Utama", callback_data="back_main"))
    return markup

def buat_tombol_kembali_menu(kode_model):
    markup = InlineKeyboardMarkup()
    if kode_model.startswith("masb_"):
        markup.row(InlineKeyboardButton("⬅️ Kembali ke Folder Masb AI", callback_data="cat_masb"))
    elif kode_model.startswith("rv_"):
        markup.row(InlineKeyboardButton("⬅️ Kembali ke Folder Routeva", callback_data="cat_routeva"))
    elif kode_model.startswith("bk_"):
        markup.row(InlineKeyboardButton("⬅️ Kembali ke Folder BotKeep Node18", callback_data="cat_botkeep"))
    elif kode_model.startswith("ok_"):
        markup.row(InlineKeyboardButton("⬅️ Kembali ke Folder OneKey LLM", callback_data="cat_onekey"))
    elif kode_model.startswith("gonka_"):
        markup.row(InlineKeyboardButton("⬅️ Kembali ke Folder GonkaRouter", callback_data="cat_gonka"))
    elif kode_model.startswith("zm_"):
        markup.row(InlineKeyboardButton("⬅️ Kembali ke Folder ZenMux", callback_data="cat_zenmux"))
    elif kode_model.startswith("ter_"):
        markup.row(InlineKeyboardButton("⬅️ Kembali ke Folder 9Router", callback_data="cat_ter"))
    elif kode_model.startswith("dahl_"):
        markup.row(InlineKeyboardButton("⬅️ Kembali ke Folder Dahl", callback_data="cat_dahl"))
    markup.row(InlineKeyboardButton("🎛 Kembali ke Menu Utama Model", callback_data="back_main"))
    return markup

def kunci_model_pilihan(chat_id, kode_pilihan):
    WAITING_MODEL_CHOICE[chat_id] = False
    USER_LOCKED_MODEL[chat_id] = kode_pilihan
    if kode_pilihan == "auto":
        return (
            "🔄 STATUS: MODE OTOMATIS AKTIF\n"
            "─────────────────────────\n"
            "Bot otomatis memilih model yang berstatus 🟢 AKTIF sesuai jenis permintaanmu."
        )
    info = KATALOG_MODEL[kode_pilihan]
    return (
        f"🟢🔒 MODEL AKTIF & BERHASIL DIKUNCI!\n"
        f"─────────────────────────\n"
        f"🤖 Pekerja Aktif : {info['nama']}\n"
        f"🆔 ID Model      : {info['model_id']}\n"
        f"🎯 Fokus Tugas   : {info['tugas']}\n"
        f"📡 Kesehatan     : 🟢 Aktif (Siap Bertugas)\n"
        f"─────────────────────────\n"
        f"✅ Sekarang HANYA model ini yang melayani semua pesanmu."
    )

# 6. Eksekutor Pesan Pengguna
def eksekusi_tunggal(kode_model, user_text, instruksi_khusus=None, chat_id=None):
    info = KATALOG_MODEL.get(kode_model)
    if not info:
        return False, "Model tidak ditemukan di katalog.", "Unknown"

    provider = info["provider"]
    model_id = info["model_id"]
    nama_tampil = info["nama"]
    riwayat_user = CHAT_HISTORY.get(chat_id, []) if chat_id else None

    try:
        if provider in ["masb", "routeva", "botkeep", "onekey", "gonka", "itera", "vascoo", "dahl", "ter", "indo", "openai", "bestllm", "bejo", "nocta"]:
            peta_base = {
                "masb": (MASB_BASE_URL, MASB_API_KEY),
                "routeva": (ROUTEVA_BASE_URL, ROUTEVA_API_KEY),
                "botkeep": (BOTKEEP_BASE_URL, BOTKEEP_API_KEY),
                "onekey": (ONEKEY_BASE_URL, ONEKEY_API_KEY),
                "gonka": (GONKA_BASE_URL, GONKA_API_KEY),
                "itera": (ITERA_BASE_URL, ITERA_API_KEY),
                "vascoo": (VASCOO_BASE_URL, VASCOO_API_KEY),
                "dahl": (DAHL_BASE_URL, DAHL_API_KEY),
                "ter": (TER_BASE_URL, TER_API_KEY),
                "indo": (INDO_BASE_URL, INDO_API_KEY),
                "openai": (OPENAI_BASE_URL, OPENAI_API_KEY),
                "bestllm": (BEST_BASE_URL, BEST_API_KEY),
                "bejo": (BEJO_BASE_URL, BEJO_API_KEY),
                "nocta": (NOCTA_BASE_URL, NOCTA_API_KEY)
            }
            base_url, key = peta_base[provider]
            if not key:
                MODEL_HEALTH_CACHE[kode_model] = {"active": False, "reason": f"API Key {provider.upper()} belum dipasang di Secrets."}
                return False, MODEL_HEALTH_CACHE[kode_model]["reason"], nama_tampil

            try:
                isi = call_ai_endpoint(base_url, key, model_id, user_text, instruksi_khusus, riwayat_user)
                if isi and isi.strip():
                    MODEL_HEALTH_CACHE[kode_model] = {"active": True, "reason": "Aktif (200 OK)"}
                    if chat_id:
                        simpan_riwayat_chat(chat_id, user_text, isi.strip())
                    return True, isi.strip(), nama_tampil
                return False, "Respons kosong dari server.", nama_tampil
            except requests.exceptions.HTTPError as he:
                alasan_gagal = analisis_penyebab_http(he.response.status_code, he.response.text)
                MODEL_HEALTH_CACHE[kode_model] = {"active": False, "reason": alasan_gagal}
                return False, alasan_gagal, nama_tampil

        elif provider == "zenmux":
            if not ZENMUX_API_KEY:
                MODEL_HEALTH_CACHE[kode_model] = {"active": False, "reason": "ZENMUX_API_KEY belum dipasang di Secrets."}
                return False, MODEL_HEALTH_CACHE[kode_model]["reason"], nama_tampil
            bases_to_try = [ZENMUX_ACTIVE_BASE] + [b for b in ZENMUX_CANDIDATE_BASES if b != ZENMUX_ACTIVE_BASE]
            last_err = ""
            for base in bases_to_try:
                try:
                    isi = call_ai_endpoint(base, ZENMUX_API_KEY, model_id, user_text, instruksi_khusus, riwayat_user)
                    if isi and isi.strip():
                        MODEL_HEALTH_CACHE[kode_model] = {"active": True, "reason": "Aktif (200 OK)"}
                        if chat_id:
                            simpan_riwayat_chat(chat_id, user_text, isi.strip())
                        return True, isi.strip(), f"ZenMux ({model_id})"
                except requests.exceptions.HTTPError as he:
                    last_err = analisis_penyebab_http(he.response.status_code, he.response.text)
                    if he.response.status_code in [401, 403]:
                        break
                except Exception as ex:
                    last_err = f"Server Down / Timeout: {str(ex)[:50]}"
            MODEL_HEALTH_CACHE[kode_model] = {"active": False, "reason": last_err}
            return False, last_err, nama_tampil

        elif provider == "gemini":
            if not gemini_client:
                MODEL_HEALTH_CACHE[kode_model] = {"active": False, "reason": "GEMINI_API_KEY belum dipasang di Secrets."}
                return False, MODEL_HEALTH_CACHE[kode_model]["reason"], nama_tampil
            payload_msgs = format_messages_payload(user_text, instruksi_khusus, riwayat_user)
            gabungan_teks = "\n\n".join([f"[{m['role'].upper()}]: {m['content']}" for m in payload_msgs])
            resp = gemini_client.models.generate_content(model=model_id, contents=gabungan_teks)
            if resp and resp.text:
                MODEL_HEALTH_CACHE[kode_model] = {"active": True, "reason": "Aktif"}
                if chat_id:
                    simpan_riwayat_chat(chat_id, user_text, resp.text.strip())
                return True, resp.text.strip(), nama_tampil
            return False, "Respons Gemini kosong.", nama_tampil

        elif provider == "openrouter":
            if not OPENROUTER_KEY:
                MODEL_HEALTH_CACHE[kode_model] = {"active": False, "reason": "API_KEY OpenRouter belum dipasang."}
                return False, MODEL_HEALTH_CACHE[kode_model]["reason"], nama_tampil
            for or_m in OR_MODELS[:3]:
                try:
                    isi = call_ai_endpoint(OPENROUTER_BASE_URL, OPENROUTER_KEY, or_m, user_text, instruksi_khusus, riwayat_user)
                    if isi and isi.strip():
                        MODEL_HEALTH_CACHE[kode_model] = {"active": True, "reason": "Aktif"}
                        if chat_id:
                            simpan_riwayat_chat(chat_id, user_text, isi.strip())
                        return True, isi.strip(), f"OpenRouter ({or_m})"
                except Exception:
                    continue
            alasan = "Semua jalur gratis OpenRouter sedang penuh / rate-limit."
            MODEL_HEALTH_CACHE[kode_model] = {"active": False, "reason": alasan}
            return False, alasan, nama_tampil

    except Exception as e:
        alasan = f"Server Down / Gangguan Koneksi: {str(e)[:60]}"
        MODEL_HEALTH_CACHE[kode_model] = {"active": False, "reason": alasan}
        return False, alasan, nama_tampil

    return False, "Gagal mengeksekusi model.", nama_tampil

def kerjakan_gambar(message, prompt_asli):
    bot.send_chat_action(message.chat.id, 'upload_photo')
    msg_wait = bot.reply_to(message, f"🟢🔒 [Model: Flux Uncensored]\n⏳ Merender gambar: {prompt_asli}...")
    safe_prompt = urllib.parse.quote(prompt_asli)
    url = f"https://image.pollinations.ai/prompt/{safe_prompt}?model=flux&seed={random.randint(1, 9999999)}&nologo=true&enhance=true"
    try:
        res = requests.get(url, timeout=60)
        if res.status_code == 200:
            bot.send_photo(message.chat.id, res.content, caption=f"🎨 Hasil: {prompt_asli}\n🟢 [Dikerjakan oleh: Flux Uncensored]")
            try:
                bot.delete_message(message.chat.id, msg_wait.message_id)
            except Exception:
                pass
        else:
            bot.edit_message_text(f"🔴 Gagal membuat gambar (Server Visual Kode {res.status_code}).", chat_id=message.chat.id, message_id=msg_wait.message_id)
    except Exception as e:
        bot.edit_message_text(f"🔴 Error gambar: {e}", chat_id=message.chat.id, message_id=msg_wait.message_id)

def kerjakan_video(message, teks_user):
    bot.send_chat_action(message.chat.id, 'typing')
    msg_wait = bot.reply_to(message, "🟢🔒 [Model: AI Video Director]\n⏳ Menyusun skenario & merender Keyframe...")
    instruksi_video = "Kamu AI Video Director. Buatlah: 1. Skenario Visual detik demi detik, 2. Prompt Teknis Bahasa Inggris untuk engine video AI."
    teks_skenario, penulis = "", "Video Director"

    antrean_video = ["masb_0", "rv_0", "bk_0", "ok_0", "gonka_0", "itera", "vascoo", "dahl_0", "ter_0", "zm_0", "indo", "chatgpt", "qwen", "recursive"]
    for k in antrean_video:
        if k in KATALOG_MODEL:
            ok, hasil, label = eksekusi_tunggal(k, teks_user, instruksi_video, message.chat.id)
            if ok:
                teks_skenario, penulis = hasil, label
                break

    prompt_visual = urllib.parse.quote(f"cinematic movie frame, 16:9 widescreen, {teks_user}")
    frame_url = f"https://image.pollinations.ai/prompt/{prompt_visual}?model=flux&width=1280&height=720&seed={random.randint(1, 999999)}&nologo=true"
    try:
        res_img = requests.get(frame_url, timeout=45)
        if res_img.status_code == 200:
            bot.send_photo(message.chat.id, res_img.content, caption="🎬 Preview Keyframe Video (16:9)")
    except Exception:
        pass
    try:
        bot.delete_message(message.chat.id, msg_wait.message_id)
    except Exception:
        pass
    if teks_skenario:
        kirim_pesan_rapi(message, teks_skenario, f"AI Video Director ({penulis})", "Pembuatan Video")
    else:
        bot.reply_to(message, "🔴 Gagal menyusun skenario video karena model teks sedang tidak aktif.")

# 7. Teks Menu dengan Informasi Diagnostik Lengkap
def teks_menu_utama_str(mode_sekarang):
    info = "OTOMATIS (Hanya Model 🟢)" if mode_sekarang == "auto" else KATALOG_MODEL.get(mode_sekarang, {}).get("nama", "Unknown")
    total_semua = len(KATALOG_MODEL)
    total_hijau = sum(1 for k in KATALOG_MODEL if MODEL_HEALTH_CACHE.get(k, {}).get("active", False))
    total_merah = total_semua - total_hijau

    return (
        f"🎛 PUSAT KONTROL & STATUS KESEHATAN AI\n"
        f"Mode Saat Ini: [{info}]\n"
        f"Status Global: 🟢 {total_hijau} Aktif  |  🔴 {total_merah} Mati\n"
        f"─────────────────────────\n"
        f"Keterangan Indikator Tombol:\n"
        f"• 🟢 = Model Aktif (Klik untuk mengunci 🔒)\n"
        f"• 🔴 = Model Mati (Klik untuk lihat alasan error)\n"
        f"• 📜 = Lihat, hapus, atau pilih lanjutkan proyek dari history\n"
        f"─────────────────────────\n"
        f"👇 Pilih Kategori atau Model di bawah ini:"
    )

def teks_submenu_folder_str(nama_kategori, mode_sekarang, awalan):
    info = "OTOMATIS" if mode_sekarang == "auto" else KATALOG_MODEL.get(mode_sekarang, {}).get("nama", "Unknown")
    baris = []
    for k, v in KATALOG_MODEL.items():
        if k.startswith(awalan):
            sehat = MODEL_HEALTH_CACHE.get(k, {})
            ikon = "🟢" if sehat.get("active") else "🔴"
            ket = "Aktif" if sehat.get("active") else sehat.get("reason", "Belum dicek")[:42]
            gembok = " 🔒" if k == mode_sekarang else ""
            baris.append(f"{ikon}{gembok} {v['model_id']}\n   └ {ket}")
    daftar = "\n".join(baris)
    return (
        f"📂 KATEGORI {nama_kategori}\n"
        f"Mode Saat Ini: [{info}]\n"
        f"─────────────────────────\n"
        f"{daftar}\n"
        f"─────────────────────────\n"
        f"👇 Klik 🟢 untuk mengunci, atau klik 🔴 untuk detail penyebab mati:"
    )

# 8. Perintah /history, /reset, /model, /cek, dan /kuota
@bot.message_handler(commands=['history', 'riwayat'])
def handle_view_history(message):
    chat_id = message.chat.id
    bersihkan_instruksi_sebelumnya(chat_id, message.message_id)
    msg = bot.send_message(
        chat_id,
        teks_menu_history_str(chat_id),
        reply_markup=buat_markup_history(chat_id)
    )
    catat_pesan_ui(chat_id, msg)

@bot.message_handler(commands=['reset', 'clear', 'new'])
def handle_reset_history(message):
    chat_id = message.chat.id
    bersihkan_instruksi_sebelumnya(chat_id, message.message_id)
    diarsipkan = arsipkan_sesi_ke_proyek(chat_id)
    if diarsipkan:
        teks_info = (
            "💾 Proyek sebelumnya telah disimpan ke dalam Arsip History!\n"
            "🧹 Memori aktif sekarang sudah bersih untuk memulai topik/proyek baru.\n\n"
            "💡 Ketik /history kapan saja jika ingin memilih dan melanjutkan kembali proyek yang lama."
        )
    else:
        teks_info = "🧹 Memori percakapan sudah kosong dan siap untuk proyek baru."
    msg = bot.send_message(chat_id, teks_info, reply_markup=buat_markup_history(chat_id))
    catat_pesan_ui(chat_id, msg)

@bot.message_handler(commands=['model', 'cek'])
def handle_command_model(message):
    chat_id, cmd_text = message.chat.id, message.text.strip()
    mode_sekarang = USER_LOCKED_MODEL.get(chat_id, "auto")

    bersihkan_instruksi_sebelumnya(chat_id, message.message_id)

    arg = re.sub(r'[\(\)\[\]\{\}]', '', cmd_text.replace('/model', '').replace('/cek', '').strip().lower())
    if not arg:
        msg_wait = bot.send_message(chat_id, "🔍 Memeriksa status 🟢 Aktif / 🔴 Mati seluruh model AI...")
        catat_pesan_ui(chat_id, msg_wait)
        periksa_kesehatan_serentak()
        WAITING_MODEL_CHOICE[chat_id] = True
        try:
            bot.edit_message_text(
                teks_menu_utama_str(mode_sekarang),
                chat_id=chat_id,
                message_id=msg_wait.message_id,
                reply_markup=buat_menu_utama(mode_sekarang, chat_id)
            )
        except telebot.apihelper.ApiTelegramException as e:
            if "message is not modified" in str(e):
                pass
            else:
                msg_baru = bot.send_message(chat_id, teks_menu_utama_str(mode_sekarang), reply_markup=buat_menu_utama(mode_sekarang, chat_id))
                catat_pesan_ui(chat_id, msg_baru)
        except Exception:
            msg_baru = bot.send_message(chat_id, teks_menu_utama_str(mode_sekarang), reply_markup=buat_menu_utama(mode_sekarang, chat_id))
            catat_pesan_ui(chat_id, msg_baru)
        return

    if arg in ["history", "riwayat"]:
        msg_h = bot.send_message(chat_id, teks_menu_history_str(chat_id), reply_markup=buat_markup_history(chat_id))
        catat_pesan_ui(chat_id, msg_h)
        return

    if arg in ["masb", "ai"]:
        msg_wait = bot.send_message(chat_id, "🔍 Memeriksa kesehatan model di dalam Masb AI...")
        catat_pesan_ui(chat_id, msg_wait)
        periksa_kesehatan_serentak([k for k in KATALOG_MODEL if k.startswith("masb_")])
        try:
            bot.edit_message_text(
                teks_submenu_folder_str("MASB AI", mode_sekarang, "masb_"),
                chat_id=chat_id,
                message_id=msg_wait.message_id,
                reply_markup=buat_submenu_folder(mode_sekarang, "masb_", "refresh_masb")
            )
        except telebot.apihelper.ApiTelegramException as e:
            if "message is not modified" in str(e):
                pass
        return

    if arg in ["routeva", "rv"]:
        msg_wait = bot.send_message(chat_id, "🔍 Memeriksa kesehatan model di dalam Routeva Tech...")
        catat_pesan_ui(chat_id, msg_wait)
        periksa_kesehatan_serentak([k for k in KATALOG_MODEL if k.startswith("rv_")])
        try:
            bot.edit_message_text(
                teks_submenu_folder_str("ROUTEVA TECH", mode_sekarang, "rv_"),
                chat_id=chat_id,
                message_id=msg_wait.message_id,
                reply_markup=buat_submenu_folder(mode_sekarang, "rv_", "refresh_routeva")
            )
        except telebot.apihelper.ApiTelegramException as e:
            if "message is not modified" in str(e):
                pass
        return

    if arg in ["botkeep", "bk", "node18"]:
        msg_wait = bot.send_message(chat_id, "🔍 Memeriksa kesehatan model di dalam BotKeep Node18...")
        catat_pesan_ui(chat_id, msg_wait)
        periksa_kesehatan_serentak([k for k in KATALOG_MODEL if k.startswith("bk_")])
        try:
            bot.edit_message_text(
                teks_submenu_folder_str("BOTKEEP NODE18", mode_sekarang, "bk_"),
                chat_id=chat_id,
                message_id=msg_wait.message_id,
                reply_markup=buat_submenu_folder(mode_sekarang, "bk_", "refresh_botkeep")
            )
        except telebot.apihelper.ApiTelegramException as e:
            if "message is not modified" in str(e):
                pass
        return

    if arg in ["onekey", "ok"]:
        msg_wait = bot.send_message(chat_id, "🔍 Memeriksa kesehatan model di dalam OneKeyLLMAPI...")
        catat_pesan_ui(chat_id, msg_wait)
        periksa_kesehatan_serentak([k for k in KATALOG_MODEL if k.startswith("ok_")])
        try:
            bot.edit_message_text(
                teks_submenu_folder_str("ONEKEY LLM API", mode_sekarang, "ok_"),
                chat_id=chat_id,
                message_id=msg_wait.message_id,
                reply_markup=buat_submenu_folder(mode_sekarang, "ok_", "refresh_onekey")
            )
        except telebot.apihelper.ApiTelegramException as e:
            if "message is not modified" in str(e):
                pass
        return

    if arg == "gonka":
        msg_wait = bot.send_message(chat_id, "🔍 Memeriksa kesehatan model di dalam GonkaRouter...")
        catat_pesan_ui(chat_id, msg_wait)
        periksa_kesehatan_serentak([k for k in KATALOG_MODEL if k.startswith("gonka_")])
        try:
            bot.edit_message_text(
                teks_submenu_folder_str("GONKAROUTER AI", mode_sekarang, "gonka_"),
                chat_id=chat_id,
                message_id=msg_wait.message_id,
                reply_markup=buat_submenu_folder(mode_sekarang, "gonka_", "refresh_gonka")
            )
        except telebot.apihelper.ApiTelegramException as e:
            if "message is not modified" in str(e):
                pass
        return

    kode_cocok = arg if arg in KATALOG_MODEL or arg == "auto" else next((k for k, v in KATALOG_MODEL.items() if arg == v["model_id"].lower() or arg in v["model_id"].lower()), None)
    if kode_cocok:
        if kode_cocok == "auto":
            msg_auto = bot.send_message(chat_id, kunci_model_pilihan(chat_id, "auto"))
            catat_pesan_ui(chat_id, msg_auto)
            return
        msg_tes = bot.send_message(chat_id, f"🔍 Menguji kesehatan model [{KATALOG_MODEL[kode_cocok]['nama']}]...")
        catat_pesan_ui(chat_id, msg_tes)
        ok, alasan = uji_satu_model_cepat(kode_cocok)
        MODEL_HEALTH_CACHE[kode_cocok] = {"active": ok, "reason": alasan}
        if ok:
            try:
                bot.edit_message_text(kunci_model_pilihan(chat_id, kode_cocok), chat_id=chat_id, message_id=msg_tes.message_id)
            except telebot.apihelper.ApiTelegramException as e:
                if "message is not modified" in str(e):
                    pass
        else:
            info_m = KATALOG_MODEL[kode_cocok]
            pesan_mati = (
                f"🔴 MODEL TIDAK AKTIF (GAGAL DIKUNCI)\n"
                f"─────────────────────────\n"
                f"🤖 Nama Model : {info_m['nama']}\n"
                f"🆔 ID Model   : {info_m['model_id']}\n"
                f"⚠️ Penyebab   : {alasan}\n"
                f"─────────────────────────\n"
                f"💡 Silakan pilih model lain yang berstatus 🟢 Hijau."
            )
            try:
                bot.edit_message_text(
                    pesan_mati,
                    chat_id=chat_id,
                    message_id=msg_tes.message_id,
                    reply_markup=buat_tombol_kembali_menu(kode_cocok)
                )
            except telebot.apihelper.ApiTelegramException as e:
                if "message is not modified" in str(e):
                    pass
    else:
        WAITING_MODEL_CHOICE[chat_id] = True
        msg_err = bot.send_message(chat_id, f"❌ Model '{arg}' tidak ditemukan.", reply_markup=buat_menu_utama(mode_sekarang, chat_id))
        catat_pesan_ui(chat_id, msg_err)

@bot.message_handler(commands=['kuota', 'saldo'])
def handle_cek_kuota(message):
    chat_id = message.chat.id
    bersihkan_instruksi_sebelumnya(chat_id, message.message_id)

    msg = bot.send_message(chat_id, "🔍 Memeriksa status seluruh server & sisa kuota...")
    catat_pesan_ui(chat_id, msg)
    periksa_kesehatan_serentak()

    laporan = "📊 LAPORAN KESEHATAN SERVER & KUOTA API\n─────────────────────────\n"
    daftar_utama = ["masb_0", "rv_0", "bk_0", "ok_0", "gonka_0", "itera", "vascoo", "chatgpt", "indo", "best", "qwen", "deepseek", "luna", "argon", "recursive", "dahl_0", "ter_0", "zm_0"]
    for k in daftar_utama:
        if k in KATALOG_MODEL:
            sehat = MODEL_HEALTH_CACHE.get(k, {})
            ikon = "🟢" if sehat.get("active") else "🔴"
            ket = sehat.get("reason", "Belum dicek")
            laporan += f"{ikon} {KATALOG_MODEL[k]['nama']}\n   └ Status: {ket}\n"

    try:
        bot.edit_message_text(laporan[:4000], chat_id=chat_id, message_id=msg.message_id)
    except telebot.apihelper.ApiTelegramException as e:
        if "message is not modified" in str(e):
            pass

# 9. Handler Klik Tombol
@bot.callback_query_handler(func=lambda call: True)
def handle_semua_tombol(call):
    global MASB_MODELS, ROUTEVA_MODELS, BOTKEEP_MODELS, ONEKEY_MODELS, GONKA_MODELS, ZENMUX_MODELS, TER_MODELS, DAHL_MODELS
    chat_id, data = call.message.chat.id, call.data
    msg_id = call.message.message_id
    mode_sekarang = USER_LOCKED_MODEL.get(chat_id, "auto")

    try:
        if data == "copy_raw_code":
            daftar_blok = LAST_CODE_BLOCKS.get(chat_id, [])
            if not daftar_blok:
                bot.answer_callback_query(call.id, "⚠️ Tidak ada source code terakhir yang tersimpan.", show_alert=True)
                return
            bot.answer_callback_query(call.id, "📋 Menampilkan Source Code Utuh!")
            for idx, b in enumerate(daftar_blok):
                bahasa = b["lang"]
                kode_mentah = b["code"]
                judul_blok = f"📋 <b>SOURCE CODE #{idx + 1} ({bahasa.upper()})</b>:\n\n"
                if len(kode_mentah) <= 3700:
                    html_kode = f'{judul_blok}<pre><code class="language-{bahasa}">{html.escape(kode_mentah)}</code></pre>'
                    bot.send_message(chat_id, html_kode, parse_mode="HTML")
                else:
                    eks = tentukan_ekstensi_file(bahasa, kode_mentah)
                    nama_file = f"source_code_{idx + 1}.{eks}"
                    bio = io.BytesIO(kode_mentah.encode("utf-8"))
                    bio.name = nama_file
                    bot.send_document(chat_id, bio, caption=f"📄 File '{nama_file}' ({len(kode_mentah)} karakter):")
                    potongan_k = pecah_pesan_aman_kode(f"```{bahasa}\n{kode_mentah}\n```", batas=3600)
                    for p_i, pot_k in enumerate(potongan_k):
                        bot.send_message(chat_id, f"<b>Bagian {p_i + 1}/{len(potongan_k)}:</b>\n" + format_ke_html_telegram(pot_k), parse_mode="HTML")
            return

        elif data == "dl_raw_code":
            daftar_blok = LAST_CODE_BLOCKS.get(chat_id, [])
            if not daftar_blok:
                bot.answer_callback_query(call.id, "⚠️ Tidak ada source code terakhir.", show_alert=True)
                return
            bot.answer_callback_query(call.id, "📥 Mengirimkan file source code...")
            for idx, b in enumerate(daftar_blok):
                eks = tentukan_ekstensi_file(b["lang"], b["code"])
                nama_file = f"source_code_{idx + 1}.{eks}"
                bio = io.BytesIO(b["code"].encode("utf-8"))
                bio.name = nama_file
                bot.send_document(chat_id, bio, caption=f"📥 File Source Code #{idx + 1} ({nama_file}).")
            return

        daftar_ui = UI_HISTORY_MESSAGES.get(chat_id, [])
        for old_id in list(daftar_ui):
            if old_id != msg_id:
                try:
                    bot.delete_message(chat_id, old_id)
                except Exception:
                    pass
        UI_HISTORY_MESSAGES[chat_id] = [msg_id]

        if data == "menu_history":
            bot.answer_callback_query(call.id, "📜 Membuka daftar riwayat & proyek...")
            try:
                bot.edit_message_text(
                    teks_menu_history_str(chat_id),
                    chat_id=chat_id,
                    message_id=msg_id,
                    reply_markup=buat_markup_history(chat_id)
                )
            except telebot.apihelper.ApiTelegramException as e:
                if "message is not modified" in str(e):
                    pass
            return

        elif data.startswith("reshist_"):
            idx_pilih = int(data.replace("reshist_", ""))
            pasangan_terpilih = lanjutkan_dari_titik_riwayat(chat_id, idx_pilih)
            if pasangan_terpilih:
                u_t, a_t = pasangan_terpilih
                blok_tersimpan = ekstrak_blok_kode(a_t)
                if blok_tersimpan:
                    LAST_CODE_BLOCKS[chat_id] = blok_tersimpan
                bot.answer_callback_query(call.id, f"▶️ Proyek #{idx_pilih + 1} diaktifkan untuk dilanjutkan!")
                teks_resume = (
                    f"▶️ <b>PROYEK / RIWAYAT #{idx_pilih + 1} DIPILIH & DILANJUTKAN!</b>\n"
                    f"─────────────────────────\n"
                    f"👤 <b>Instruksi Kamu Sebelumnya:</b>\n{html.escape(u_t[:400])}\n\n"
                    f"🤖 <b>Jawaban / Kodingan Terakhir AI:</b>\n{format_ke_html_telegram(a_t[:2600])}\n"
                    f"─────────────────────────\n"
                    f"✅ <b>Silakan ketik instruksi
