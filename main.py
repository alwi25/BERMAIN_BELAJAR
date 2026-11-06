import os
import time
import re
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

# Daftar Endpoint Server
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
ZENMUX_CANDIDATE_BASES = ["https://api.zenmux.ai/v1", "https://zenmux.ai/api/v1", "https://zenmux.ai/v1"]
TER_BASE_URL = "https://ter.biz.id/v1"
BEST_CHAT_URL = "https://api.bestllmapi.com/v1/chat/completions"
INDO_CHAT_URL = "https://indosmartrouter.cloud/v1/chat/completions"
BEJO_URL = "https://bejoxxx.tech/v1/chat/completions"
NOCTA_URL = "https://nocta-digital.web.id/v1/chat/completions"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

gemini_client = None
if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
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

# 2. Penyisir Model (ZenMux, 9Router, BestLLM, OpenRouter)
ZENMUX_ACTIVE_BASE = ZENMUX_CANDIDATE_BASES[0]

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
                    data = res.json().get("data", [])
                    ids = [str(m.get("id")) for m in data if m.get("id")]
                    if ids:
                        ZENMUX_ACTIVE_BASE = base
                        for p in priorities:
                            for mid in ids:
                                if p in mid.lower() and mid not in found: found.append(mid)
                        for mid in ids:
                            if mid not in found: found.append(mid)
                        break
            except: continue
    defaults = ["tencent-hy4", "hunyuan-hy4", "deepseek-v3", "qwen-2.5-coder-32b-instruct", "claude-3-7-sonnet", "gpt-4o"]
    for d in defaults:
        if d not in found: found.append(d)
    return found

def sisir_model_ter():
    defaults = ["glm/glm-5.3-flash", "glm/glm-5.3", "glm-5.3-flash-jb", "glm-mommy", "glm-kratos"]
    found = []
    if TER_API_KEY:
        try:
            res = requests.get(f"{TER_BASE_URL}/models", headers={"Authorization": f"Bearer {TER_API_KEY}"}, timeout=10, verify=False)
            if res.status_code == 200:
                ids = [str(m.get("id")) for m in res.json().get("data", []) if m.get("id")]
                for d in defaults:
                    if d in ids and d not in found: found.append(d)
                for mid in ids:
                    if mid not in found: found.append(mid)
        except: pass
    for d in defaults:
        if d not in found: found.append(d)
    return found

ZENMUX_MODELS = sisir_model_zenmux()
TER_MODELS = sisir_model_ter()

def get_bestllm_models():
    found = []
    if BEST_API_KEY:
        try:
            res = requests.get("https://api.bestllmapi.com/v1/models", headers={"Authorization": f"Bearer {BEST_API_KEY}"}, timeout=10, verify=False)
            if res.status_code == 200:
                ids = [str(m.get("id")) for m in res.json().get("data", []) if m.get("id")]
                for p in ["uncensored", "dolphin", "hermes", "mythomax", "qwen", "deepseek"]:
                    for mid in ids:
                        if p in mid.lower() and mid not in found: found.append(mid)
                for mid in ids:
                    if mid not in found: found.append(mid)
        except: pass
    for d in ["uncensored", "dolphin-mixtral-8x7b", "nous-hermes-2-mixtral-8x7b-dpo"]:
        if d not in found: found.append(d)
    return found

BEST_MODELS = get_bestllm_models()

def get_openrouter_models():
    available = []
    try:
        res = requests.get("https://openrouter.ai/api/v1/models", timeout=10)
        if res.status_code == 200:
            free_ids = [m["id"] for m in res.json().get("data", []) if m.get("id", "").endswith(":free")]
            for p in ["dolphin", "hermes", "mythomax", "llama-3"]:
                for fid in free_ids:
                    if p.lower() in fid.lower() and fid not in available: available.append(fid)
            for fid in free_ids:
                if fid not in available: available.append(fid)
    except: pass
    available.insert(0, "openrouter/free")
    return available

OR_MODELS = get_openrouter_models() if OPENROUTER_KEY else ["openrouter/free"]

# 3. Katalog Utama & Folder Sub-Kategori
KATALOG_MODEL = {
    "chatgpt": {"provider": "openai", "model_id": "gpt-4o", "nama": "ChatGPT 4o (OpenAI)", "tugas": "Serba Bisa, Natural & Pintar"},
    "indo": {"provider": "indo", "model_id": "qwen-uncensored", "nama": "IndoSmart Qwen Uncensored", "tugas": "Teks Tanpa Sensor (IndoSmart)"},
    "best": {"provider": "bestllm", "model_id": BEST_MODELS[0], "nama": "BestLLM Uncensored", "tugas": "Teks & Roleplay Tanpa Filter"},
    "qwen": {"provider": "bejo", "model_id": "qwen3.8-27b-uncensored", "nama": "Qwen 3.8 27B Uncensored", "tugas": "Teks Tanpa Sensor & Koding"},
    "deepseek": {"provider": "nocta", "model_id": "deepseek-v4.1", "nama": "DeepSeek v4.1 (Nocta)", "tugas": "Koding, Algoritma & Bug Fixing"},
    "luna": {"provider": "nocta", "model_id": "gpt-5.6-luna", "nama": "GPT-5.6 Luna (Nocta)", "tugas": "Teks Kreatif & Natural"},
    "argon": {"provider": "gemini", "model_id": "gemini-4-argon", "nama": "Gemini 4 Argon", "tugas": "Penalaran Logika & Analisis"},
    "gemini": {"provider": "gemini", "model_id": "gemini-1.5-pro", "nama": "Gemini 1.5 Pro", "tugas": "Dokumen Panjang"},
    "flash": {"provider": "gemini", "model_id": "gemini-1.5-flash", "nama": "Gemini 1.5 Flash", "tugas": "Respon Cepat"},
    "recursive": {"provider": "openrouter", "model_id": "openrouter/free", "nama": "OpenRouter Recursive", "tugas": "Teks Multi-Model Otomatis"},
    "gambar": {"provider": "pollinations", "model_id": "flux-uncensored", "nama": "Pollinations Flux Uncensored", "tugas": "Gambar & Foto Tanpa Filter"},
    "video": {"provider": "video_engine", "model_id": "director-flux-16-9", "nama": "AI Video Director", "tugas": "Skenario Video & Keyframe"}
}

def segarkan_folder_kategori():
    kunci_lama = [k for k in KATALOG_MODEL.keys() if k.startswith("zm_") or k.startswith("ter_")]
    for k in kunci_lama: del KATALOG_MODEL[k]
    
    for idx, m_id in enumerate(ZENMUX_MODELS[:15]):
        KATALOG_MODEL[f"zm_{idx}"] = {
            "provider": "zenmux", "model_id": m_id, "nama": f"ZenMux: {m_id}",
            "tugas": "Agen Pengkodean & Multi-Tugas" if "hy4" in m_id.lower() or "coder" in m_id.lower() else "Model AI ZenMux"
        }
    for idx, m_id in enumerate(TER_MODELS[:15]):
        KATALOG_MODEL[f"ter_{idx}"] = {
            "provider": "ter", "model_id": m_id, "nama": f"9Router: {m_id}",
            "tugas": "Roleplay & Jailbreak" if "jb" in m_id.lower() or "mommy" in m_id.lower() or "kratos" in m_id.lower() else "Model GLM 9Router"
        }

segarkan_folder_kategori()

# 4. Pembuat Menu Telegram
def buat_menu_utama(mode_aktif):
    markup = InlineKeyboardMarkup(row_width=2)
    jum_zm = len([k for k in KATALOG_MODEL if k.startswith("zm_")])
    jum_ter = len([k for k in KATALOG_MODEL if k.startswith("ter_")])
    
    markup.row(InlineKeyboardButton(f"{'🔒📂' if mode_aktif.startswith('zm_') else '📂'} KATEGORI ZENMUX ({jum_zm} Model)", callback_data="cat_zenmux"))
    markup.row(InlineKeyboardButton(f"{'🔒📂' if mode_aktif.startswith('ter_') else '📂'} KATEGORI 9ROUTER GLM ({jum_ter} Model)", callback_data="cat_ter"))
    
    tombol_list = []
    for kode, info in KATALOG_MODEL.items():
        if kode.startswith("zm_") or kode.startswith("ter_"): continue
        tanda = "🔒 " if kode == mode_aktif else "🤖 "
        tombol_list.append(InlineKeyboardButton(f"{tanda}{kode.upper()} ({info['nama'][:10]})", callback_data=f"lock_{kode}"))
    markup.add(*tombol_list)
    markup.row(InlineKeyboardButton(f"{'✅ ' if mode_aktif == 'auto' else '🔄 '}MODE OTOMATIS", callback_data="lock_auto"))
    return markup

def buat_submenu_folder(mode_aktif, awalan, callback_refresh):
    markup = InlineKeyboardMarkup(row_width=2)
    tombol = []
    for kode, info in KATALOG_MODEL.items():
        if kode.startswith(awalan):
            tanda = "🔒 " if kode == mode_aktif else "⚡ "
            tombol.append(InlineKeyboardButton(f"{tanda}{info['model_id'][:20]}", callback_data=f"lock_{kode}"))
    markup.add(*tombol)
    markup.row(InlineKeyboardButton("🔄 Sisir Ulang Model", callback_data=callback_refresh))
    markup.row(InlineKeyboardButton("⬅️ Kembali ke Menu Utama", callback_data="back_main"))
    return markup

def kunci_model_pilihan(chat_id, kode_pilihan):
    WAITING_MODEL_CHOICE[chat_id] = False
    USER_LOCKED_MODEL[chat_id] = kode_pilihan
    if kode_pilihan == "auto": return "🔄 STATUS: MODE OTOMATIS AKTIF\nSemua model siap bekerja otomatis."
    info = KATALOG_MODEL[kode_pilihan]
    return f"🔒 MODEL TERKUNCI & AKTIF!\n🤖 Pekerja Aktif : {info['nama']}\n🆔 ID Model : {info['model_id']}\n✅ HANYA model ini yang aktif melayani pesanmu."

# 5. Eksekutor Model Tersentralisasi
def eksekusi_tunggal(kode_model, user_text, instruksi_khusus=None):
    info = KATALOG_MODEL.get(kode_model)
    if not info: return False, "Model tidak ditemukan di katalog.", "Unknown"

    provider = info["provider"]
    model_id = info["model_id"]
    nama_tampil = info["nama"]
    sistem_prompt = instruksi_khusus or "Kamu adalah AI spesialis. Kerjakan instruksi pengguna secara langsung, objektif, dan tuntas menggunakan bahasa Indonesia."
    headers_umum = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}

    try:
        # EKSEKUSI 9ROUTER GLM (ter.biz.id)
        if provider == "ter":
            if not TER_API_KEY: return False, "TER_API_KEY belum diisi di Secrets.", nama_tampil
            headers = {**headers_umum, "Authorization": f"Bearer {TER_API_KEY}"}
            payload = {"model": model_id, "messages": [{"role": "system", "content": sistem_prompt}, {"role": "user", "content": user_text}], "temperature": 0.7}
            res = requests.post(f"{TER_BASE_URL}/chat/completions", headers=headers, json=payload, timeout=45, verify=False)
            if res.status_code == 200:
                isi = res.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                if isi and isi.strip(): return True, isi.strip(), f"9Router ({model_id})"
            return False, f"Server 9Router gagal (Kode {res.status_code})", nama_tampil

        # EKSEKUSI ZENMUX AI
        elif provider == "zenmux":
            if not ZENMUX_API_KEY: return False, "ZENMUX_API_KEY kosong.", nama_tampil
            headers = {**headers_umum, "Authorization": f"Bearer {ZENMUX_API_KEY}"}
            bases_to_try = [ZENMUX_ACTIVE_BASE] + [b for b in ZENMUX_CANDIDATE_BASES if b != ZENMUX_ACTIVE_BASE]
            last_err = ""
            for base in bases_to_try:
                payload = {"model": model_id, "messages": [{"role": "system", "content": sistem_prompt}, {"role": "user", "content": user_text}], "temperature": 0.7}
                try:
                    res = requests.post(f"{base}/chat/completions", headers=headers, json=payload, timeout=50, verify=False)
                    if res.status_code == 200:
                        isi = res.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                        if isi and isi.strip(): return True, isi.strip(), f"ZenMux ({model_id})"
                    else:
                        last_err = f"Kode {res.status_code}"
                        if res.status_code == 401: return False, "API Key ZenMux ditolak", nama_tampil
                except Exception as ex: last_err = str(ex)[:50]
            return False, f"Gagal di ZenMux ({last_err})", nama_tampil

        # EKSEKUSI LAINNYA (INDO, BEST, BEJO, NOCTA, OPENAI)
        elif provider in ["indo", "openai", "bestllm", "bejo", "nocta"]:
            if provider == "indo": url, key = INDO_CHAT_URL, INDO_API_KEY
            elif provider == "openai": url, key = OPENAI_URL, OPENAI_API_KEY
            elif provider == "bestllm": url, key = BEST_CHAT_URL, BEST_API_KEY
            elif provider == "bejo": url, key = BEJO_URL, BEJO_API_KEY
            else: url, key = NOCTA_URL, NOCTA_API_KEY
            
            if not key: return False, f"API Key untuk {provider} kosong.", nama_tampil
            headers = {**headers_umum, "Authorization": f"Bearer {key}"}
            res = requests.post(url, headers=headers, json={"model": model_id, "messages": [{"role": "system", "content": sistem_prompt}, {"role": "user", "content": user_text}], "temperature": 0.7}, timeout=45, verify=False)
            if res.status_code == 200:
                isi = res.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                if isi and isi.strip(): return True, isi.strip(), nama_tampil
            return False, f"Server {provider} gagal", nama_tampil

        # EKSEKUSI GEMINI
        elif provider == "gemini":
            if not gemini_client: return False, "GEMINI_API_KEY kosong.", nama_tampil
            resp = gemini_client.models.generate_content(model=model_id, contents=f"{sistem_prompt}\n\nPermintaan: {user_text}")
            if resp and resp.text: return True, resp.text.strip(), nama_tampil
            return False, "Respons Gemini kosong.", nama_tampil

        # EKSEKUSI OPENROUTER
        elif provider == "openrouter":
            if not OPENROUTER_KEY: return False, "API_KEY OpenRouter kosong.", nama_tampil
            headers = {**headers_umum, "Authorization": f"Bearer {OPENROUTER_KEY}", "HTTP-Referer": "https://github.com"}
            for or_m in OR_MODELS[:3]:
                res = requests.post(OPENROUTER_URL, headers=headers, json={"model": or_m, "messages": [{"role": "system", "content": sistem_prompt}, {"role": "user", "content": user_text}]}, timeout=45, verify=False)
                if res.status_code == 200:
                    isi = res.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                    if isi and isi.strip(): return True, isi.strip(), f"OpenRouter ({res.json().get('model', or_m)})"
            return False, "Server OpenRouter sibuk.", nama_tampil

    except Exception as e:
        return False, f"Kendala jaringan: {str(e)[:50]}", nama_tampil
    return False, "Gagal mengeksekusi model.", nama_tampil

def kerjakan_gambar(message, prompt_asli):
    bot.send_chat_action(message.chat.id, 'upload_photo')
    msg_wait = bot.reply_to(message, f"🔒 [Model: Flux Uncensored]\n⏳ Merender gambar: {prompt_asli}...")
    safe_prompt = urllib.parse.quote(prompt_asli)
    url = f"https://image.pollinations.ai/prompt/{safe_prompt}?model=flux&seed={random.randint(1, 9999999)}&nologo=true&enhance=true"
    try:
        res = requests.get(url, timeout=60)
        if res.status_code == 200:
            bot.send_photo(message.chat.id, res.content, caption=f"🎨 Hasil: {prompt_asli}\n🔒 [Dikerjakan oleh: Flux Uncensored]")
            try: bot.delete_message(message.chat.id, msg_wait.message_id)
            except: pass
        else: bot.edit_message_text(f"❌ Gagal membuat gambar.", chat_id=message.chat.id, message_id=msg_wait.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ Error gambar: {e}", chat_id=message.chat.id, message_id=msg_wait.message_id)

def kerjakan_video(message, teks_user):
    bot.send_chat_action(message.chat.id, 'typing')
    msg_wait = bot.reply_to(message, "🔒 [Model: AI Video Director]\n⏳ Menyusun skenario & merender Keyframe...")
    instruksi_video = "Kamu AI Video Director. Buatlah: 1. Skenario Visual, 2. Prompt Teknis Bahasa Inggris untuk engine video AI."
    teks_skenario, penulis = "", "Video Director"
    
    # Prioritaskan GLM Unchained atau ZenMux untuk skenario video
    antrean_video = ["ter_0", "zm_0", "indo", "chatgpt", "qwen", "recursive"]
    for k in antrean_video:
        if k in KATALOG_MODEL:
            ok, hasil, label = eksekusi_tunggal(k, teks_user, instruksi_video)
            if ok:
                teks_skenario, penulis = hasil, label
                break
                
    prompt_visual = urllib.parse.quote(f"cinematic movie frame, 16:9 widescreen, {teks_user}")
    frame_url = f"https://image.pollinations.ai/prompt/{prompt_visual}?model=flux&width=1280&height=720&seed={random.randint(1, 999999)}&nologo=true"
    try:
        res_img = requests.get(frame_url, timeout=45)
        if res_img.status_code == 200:
            bot.send_photo(message.chat.id, res_img.content, caption="🎬 Preview Keyframe Video (16:9)")
    except: pass
    try: bot.delete_message(message.chat.id, msg_wait.message_id)
    except: pass
    if teks_skenario: kirim_pesan_rapi(message, teks_skenario, f"AI Video Director ({penulis})", "Pembuatan Video")
    else: bot.reply_to(message, "⚠️ Gagal menyusun skenario video.")

def kirim_pesan_rapi(message, isi_teks, nama_model, status_mode):
    header = f"🔒 [ Model Aktif: {nama_model} ]\n📌 [ Status: {status_mode} ]\n" + ("─" * 26) + "\n\n"
    full_text = header + isi_teks
    if len(full_text) <= 4000: bot.reply_to(message, full_text)
    else:
        for i in range(0, len(full_text), 4000): bot.reply_to(message, full_text[i:i+4000])

# 6. Fitur Cek Kuota
@bot.message_handler(commands=['kuota', 'saldo'])
def handle_cek_kuota(message):
    bot.send_chat_action(message.chat.id, 'typing')
    msg = bot.reply_to(message, "🔍 Memeriksa sisa pemakaian dan kuota...")
    laporan = "📊 **LAPORAN SISA KUOTA & PEMAKAIAN API**\n─────────────────────────\n"
    
    laporan += f"🌐 **9Router GLM:** {'Terpasang & Siap' if TER_API_KEY else 'Belum Terpasang'}\n"
    laporan += f"🌐 **ZenMux AI:** {'Terpasang & Siap' if ZENMUX_API_KEY else 'Belum Terpasang'}\n"
    laporan += f"🌐 **IndoSmartRouter:** {'Terpasang & Siap' if INDO_API_KEY else 'Belum Terpasang'}\n"
    laporan += f"🌐 **OpenAI (ChatGPT):** {'Terpasang' if OPENAI_API_KEY else 'Belum Terpasang'}\n"
    laporan += f"🌐 **BestLLM:** {'Terpasang' if BEST_API_KEY else 'Belum Terpasang'}\n"
    
    def cek_saldo_custom(nama_server, chat_url, api_key):
        if not api_key: return f"⚙️ **{nama_server}:** API Key belum dipasang.\n"
        try:
            url_sub = chat_url.replace("/chat/completions", "/dashboard/billing/subscription")
            res = requests.get(url_sub, headers={"Authorization": f"Bearer {api_key}"}, timeout=10, verify=False)
            if res.status_code == 200 and res.json().get("hard_limit_usd"):
                hard_limit = res.json().get("hard_limit_usd")
                url_usage = chat_url.replace("/chat/completions", "/dashboard/billing/usage")
                res_u = requests.get(url_usage, headers={"Authorization": f"Bearer {api_key}"}, timeout=10, verify=False)
                used = (res_u.json().get("total_usage", 0) / 100.0) if res_u.status_code == 200 else 0.0
                return f"⚙️ **{nama_server}:** Sisa ${float(hard_limit) - used:.2f} (Terpakai: ${used:.2f})\n"
            return f"⚙️ **{nama_server}:** API Aktif.\n"
        except: return f"⚙️ **{nama_server}:** API Terpasang.\n"

    laporan += cek_saldo_custom("Bejoxxx", BEJO_URL, BEJO_API_KEY)
    laporan += cek_saldo_custom("Nocta Digital", NOCTA_URL, NOCTA_API_KEY)
    bot.edit_message_text(laporan, chat_id=message.chat.id, message_id=msg.message_id, parse_mode="Markdown")

def teks_menu_utama_str(mode_sekarang):
    info = "OTOMATIS" if mode_sekarang == "auto" else KATALOG_MODEL.get(mode_sekarang, {}).get("nama", "Unknown")
    return (
        f"🎛 **PUSAT KONTROL MODEL AI**\nStatus: `[{info}]`\n─────────────────────────\n"
        f"📂 Klik Folder **9ROUTER GLM** untuk varian Unchained Jailbreak.\n"
        f"📂 Klik Folder **ZENMUX** untuk Tencent HY4 & DeepSeek.\n\n"
        f"🤖 **Model Langsung Lainnya:**\n"
        f"• `chatgpt` — ChatGPT 4o\n"
        f"• `indo` — IndoSmart Qwen\n"
        f"• `qwen` — Qwen 3.8 27B\n"
        f"• `gambar` / `video` — Spesialis Visual\n─────────────────────────\n👇 Pilih menu di bawah:"
    )

def teks_submenu_folder_str(nama_kategori, mode_sekarang, awalan):
    info = "OTOMATIS" if mode_sekarang == "auto" else KATALOG_MODEL.get(mode_sekarang, {}).get("nama", "Unknown")
    daftar = "\n".join([f"{'🔒' if k==mode_sekarang else '•'} `{v['model_id']}`" for k, v in KATALOG_MODEL.items() if k.startswith(awalan)])
    return f"📂 **KATEGORI {nama_kategori}**\nStatus: `[{info}]`\n─────────────────────────\nDaftar Model:\n{daftar}\n─────────────────────────\n👇 Klik model untuk mengunci:"

@bot.message_handler(commands=['model'])
def handle_command_model(message):
    chat_id, cmd_text = message.chat.id, message.text.strip()
    mode_sekarang = USER_LOCKED_MODEL.get(chat_id, "auto")
    
    arg = re.sub(r'[\(\)\[\]\{\}]', '', cmd_text.replace('/model', '').strip().lower())
    if not arg:
        WAITING_MODEL_CHOICE[chat_id] = True
        bot.reply_to(message, teks_menu_utama_str(mode_sekarang), reply_markup=buat_menu_utama(mode_sekarang), parse_mode="Markdown")
        return
    
    kode_cocok = arg if arg in KATALOG_MODEL or arg == "auto" else next((k for k, v in KATALOG_MODEL.items() if arg == v["model_id"].lower() or arg in v["model_id"].lower()), None)
    if kode_cocok: bot.reply_to(message, kunci_model_pilihan(chat_id, kode_cocok))
    else:
        WAITING_MODEL_CHOICE[chat_id] = True
        bot.reply_to(message, f"❌ Model '{arg}' tidak ditemukan.", reply_markup=buat_menu_utama(mode_sekarang))

@bot.callback_query_handler(func=lambda call: True)
def handle_semua_tombol(call):
    global ZENMUX_MODELS, TER_MODELS
    chat_id, data = call.message.chat.id, call.data
    mode_sekarang = USER_LOCKED_MODEL.get(chat_id, "auto")

    try:
        if data == "cat_zenmux":
            bot.edit_message_text(teks_submenu_folder_str("ZENMUX AI", mode_sekarang, "zm_"), chat_id=chat_id, message_id=call.message.message_id, reply_markup=buat_submenu_folder(mode_sekarang, "zm_", "refresh_zm"), parse_mode="Markdown")
        elif data == "cat_ter":
            bot.edit_message_text(teks_submenu_folder_str("9ROUTER GLM", mode_sekarang, "ter_"), chat_id=chat_id, message_id=call.message.message_id, reply_markup=buat_submenu_folder(mode_sekarang, "ter_", "refresh_ter"), parse_mode="Markdown")
        elif data == "refresh_zm":
            ZENMUX_MODELS = sisir_model_zenmux()
            segarkan_folder_kategori()
            bot.edit_message_text(teks_submenu_folder_str("ZENMUX AI", mode_sekarang, "zm_"), chat_id=chat_id, message_id=call.message.message_id, reply_markup=buat_submenu_folder(mode_sekarang, "zm_", "refresh_zm"), parse_mode="Markdown")
        elif data == "refresh_ter":
            TER_MODELS = sisir_model_ter()
            segarkan_folder_kategori()
            bot.edit_message_text(teks_submenu_folder_str("9ROUTER GLM", mode_sekarang, "ter_"), chat_id=chat_id, message_id=call.message.message_id, reply_markup=buat_submenu_folder(mode_sekarang, "ter_", "refresh_ter"), parse_mode="Markdown")
        elif data == "back_main":
            bot.edit_message_text(teks_menu_utama_str(mode_sekarang), chat_id=chat_id, message_id=call.message.message_id, reply_markup=buat_menu_utama(mode_sekarang), parse_mode="Markdown")
        elif data.startswith("lock_"):
            kode_dipilih = data.replace("lock_", "")
            if kode_dipilih in KATALOG_MODEL or kode_dipilih == "auto":
                bot.answer_callback_query(call.id, f"Terkunci: {kode_dipilih.upper()}")
                bot.edit_message_text(kunci_model_pilihan(chat_id, kode_dipilih), chat_id=chat_id, message_id=call.message.message_id)
    except: pass

@bot.message_handler(commands=['start', 'help', 'status'])
def handle_start(message):
    chat_id = message.chat.id
    mode = USER_LOCKED_MODEL.get(chat_id, "auto")
    ket_mode = "OTOMATIS" if mode == "auto" else f"TERKUNCI PADA [{KATALOG_MODEL.get(mode, {}).get('nama', mode)}]"
    bot.reply_to(message, f"🤖 Bot Multi-Model (GLM Unchained & ZenMux) Siap!\n🔒 Mode Aktif: {ket_mode}\n\n📌 Ketik /model untuk membuka Folder AI.")

def deteksi_tugas_auto(teks):
    t = teks.lower()
    if re.search(r"\b(buatkan video|bikin video|bisa buat video|generate video|video tentang)\b", t): return "video"
    if re.search(r"^(buatkan|bikin|tolong buatkan|coba buat|lukiskan|gambarin|generate)\s+(gambar|foto|ilustrasi|lukisan)\b", t) or t.startswith("gambar "): return "gambar"
    if any(k in t for k in ["koding", "coding", "script", "python", "html", "javascript", "php", "error", "bug", "buatkan kode"]): return "koding"
    if "recursive" in t or "openrouter" in t: return "recursive"
    return "teks"

@bot.message_handler(func=lambda message: True)
def handle_pesan_utama(message):
    if not message.text: return
    chat_id, teks = message.chat.id, message.text.strip()
    teks_bersih = re.sub(r'[\(\)\[\]\/]', '', teks.lower()).strip()

    if WAITING_MODEL_CHOICE.get(chat_id, False):
        kode_ketik = teks_bersih if teks_bersih in KATALOG_MODEL or teks_bersih == "auto" else next((k for k, v in KATALOG_MODEL.items() if teks_bersih == v["model_id"].lower() or (len(teks_bersih) >= 3 and teks_bersih in v["model_id"].lower())), None)
        if kode_ketik:
            bot.reply_to(message, kunci_model_pilihan(chat_id, kode_ketik))
            return
        else: WAITING_MODEL_CHOICE[chat_id] = False

    mode_terkunci = USER_LOCKED_MODEL.get(chat_id, "auto")
    if mode_terkunci != "auto":
        if mode_terkunci == "gambar": kerjakan_gambar(message, teks); return
        elif mode_terkunci == "video": kerjakan_video(message, teks); return
        else:
            bot.send_chat_action(chat_id, 'typing')
            ok, hasil, nama_pekerja = eksekusi_tunggal(mode_terkunci, teks)
            if ok: kirim_pesan_rapi(message, hasil, nama_pekerja, f"Terkunci ({KATALOG_MODEL[mode_terkunci]['model_id']})")
            else: bot.reply_to(message, f"⚠️ Model belum merespons:\n{hasil}\n💡 Ketik /model auto untuk mode otomatis.")
            return

    tugas = deteksi_tugas_auto(teks)
    if tugas == "video": kerjakan_video(message, teks); return
    if tugas == "gambar":
        prompt_img = re.sub(r"^(buatkan|bikin|tolong buatkan|coba buat|lukiskan|gambarin|generate)\s+(gambar|foto|ilustrasi|lukisan)\b", "", teks, flags=re.IGNORECASE).strip() or teks
        kerjakan_gambar(message, prompt_img)
        return

    bot.send_chat_action(chat_id, 'typing')
    
    # Auto-Router: Jika teks biasa, prioritaskan GLM Unchained (ter_0 atau ter_2) lalu IndoSmart Qwen
    if tugas == "koding": antrean, label_tugas = ["chatgpt", "zm_0", "deepseek", "indo", "qwen", "argon"], "Auto - Koding"
    elif tugas == "recursive": antrean, label_tugas = ["recursive", "chatgpt", "indo", "ter_0", "best"], "Auto - Recursive"
    else: antrean, label_tugas = ["ter_0", "ter_2", "indo", "chatgpt", "qwen", "zm_0", "luna", "deepseek"], "Auto - GLM/Teks Uncensored"

    for kode in antrean:
        if kode in KATALOG_MODEL:
            ok, hasil, nama_pekerja = eksekusi_tunggal(kode, teks)
            if ok:
                kirim_pesan_rapi(message, hasil, nama_pekerja, label_tugas)
                return

    bot.reply_to(message, "⚠️ Seluruh server penuh atau API Key belum lengkap. Ketik /model untuk memilih manual.")

if __name__ == "__main__":
    try:
        bot.remove_webhook()
        time.sleep(2)
    except: pass
    while True:
        try: bot.infinity_polling(timeout=20, long_polling_timeout=10, skip_pending=True)
        except: time.sleep(8)
