import os
import time
import re
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

# Daftar Endpoint Server
ONEKEY_BASE_URL = "https://api.onekeyllmapi.com/v1"
GONKA_BASE_URL = "https://api.gonkarouter.io/v1"
ITERA_CHAT_URL = "https://api.iteracompute.com/v1/chat/completions"
VASCOO_CHAT_URL = "https://api.vascoo.my.id/v1/chat/completions"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
ZENMUX_CANDIDATE_BASES = ["https://api.zenmux.ai/v1", "https://zenmux.ai/api/v1", "https://zenmux.ai/v1"]
TER_BASE_URL = "https://ter.biz.id/v1"
DAHL_BASE_URL = "https://inference.dahl.global/v1"
BEST_CHAT_URL = "https://api.bestllmapi.com/v1/chat/completions"
INDO_CHAT_URL = "https://indosmartrouter.cloud/v1/chat/completions"
BEJO_URL = "https://bejoxxx.tech/v1/chat/completions"
NOCTA_URL = "https://nocta-digital.web.id/v1/chat/completions"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

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

# Penyimpanan Riwayat ID Pesan Menu/Instruksi Sebelumnya (Untuk Dihapus Otomatis)
UI_HISTORY_MESSAGES = {}

# Penyimpanan Status Kesehatan Model (🟢 Aktif / 🔴 Mati beserta alasannya)
MODEL_HEALTH_CACHE = {}
LAST_HEALTH_CHECK = 0

# Fungsi Pembersih Pesan Instruksi/Menu Sebelumnya Agar Tidak Menumpuk
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

# 2. Penyisir Model Otomatis (OneKey, GonkaRouter, ZenMux, 9Router, Dahl, BestLLM, OpenRouter)
ZENMUX_ACTIVE_BASE = ZENMUX_CANDIDATE_BASES[0]

def sisir_model_onekey():
    priorities = ["uncensored", "deepseek", "qwen", "claude", "gpt-4o", "llama-3", "coder", "hermes", "dolphin", "mythomax", "gemini"]
    defaults = [
        "uncensored",
        "deepseek-r1",
        "deepseek-v3",
        "qwen-2.5-coder-32b-instruct",
        "claude-3-7-sonnet",
        "gpt-4o",
        "llama-3.3-70b-instruct",
        "dolphin-mixtral-8x7b"
    ]
    found = []
    if ONEKEY_API_KEY:
        try:
            headers = {"Authorization": f"Bearer {ONEKEY_API_KEY}", "User-Agent": "Mozilla/5.0"}
            res = requests.get(f"{ONEKEY_BASE_URL}/models", headers=headers, timeout=10, verify=False)
            if res.status_code == 200:
                ids = [str(m.get("id")) for m in res.json().get("data", []) if m.get("id")]
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

def sisir_model_gonka():
    priorities = ["uncensored", "deepseek", "qwen", "claude", "gpt-4o", "llama-3.3", "coder", "hermes", "dolphin", "gemini"]
    defaults = [
        "deepseek-r1",
        "deepseek-v3",
        "qwen-2.5-coder-32b-instruct",
        "qwen-2.5-72b-instruct",
        "claude-3-7-sonnet",
        "gpt-4o",
        "llama-3.3-70b-instruct"
    ]
    found = []
    if GONKA_API_KEY:
        try:
            headers = {"Authorization": f"Bearer {GONKA_API_KEY}", "User-Agent": "Mozilla/5.0"}
            res = requests.get(f"{GONKA_BASE_URL}/models", headers=headers, timeout=10, verify=False)
            if res.status_code == 200:
                ids = [str(m.get("id")) for m in res.json().get("data", []) if m.get("id")]
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
                                if p in mid.lower() and mid not in found:
                                    found.append(mid)
                        for mid in ids:
                            if mid not in found:
                                found.append(mid)
                        break
            except Exception:
                continue
    defaults = ["tencent-hy4", "hunyuan-hy4", "deepseek-v3", "qwen-2.5-coder-32b-instruct", "claude-3-7-sonnet", "gpt-4o"]
    for d in defaults:
        if d not in found:
            found.append(d)
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
                    if d in ids and d not in found:
                        found.append(d)
                for mid in ids:
                    if mid not in found:
                        found.append(mid)
        except Exception:
            pass
    for d in defaults:
        if d not in found:
            found.append(d)
    return found

def sisir_model_dahl():
    defaults = ["qwen-3.8-flash", "minimax", "llama-3.1-70b", "deepseek-coder"]
    found = []
    if DAHL_API_KEY:
        try:
            res = requests.get(f"{DAHL_BASE_URL}/models", headers={"Authorization": f"Bearer {DAHL_API_KEY}"}, timeout=10, verify=False)
            if res.status_code == 200:
                ids = [str(m.get("id")) for m in res.json().get("data", []) if m.get("id")]
                for d in defaults:
                    for mid in ids:
                        if d in mid.lower() and mid not in found:
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

ONEKEY_MODELS = sisir_model_onekey()
GONKA_MODELS = sisir_model_gonka()
ZENMUX_MODELS = sisir_model_zenmux()
TER_MODELS = sisir_model_ter()
DAHL_MODELS = sisir_model_dahl()

def get_bestllm_models():
    found = []
    if BEST_API_KEY:
        try:
            res = requests.get("https://api.bestllmapi.com/v1/models", headers={"Authorization": f"Bearer {BEST_API_KEY}"}, timeout=10, verify=False)
            if res.status_code == 200:
                ids = [str(m.get("id")) for m in res.json().get("data", []) if m.get("id")]
                for p in ["uncensored", "dolphin", "hermes", "mythomax", "qwen", "deepseek"]:
                    for mid in ids:
                        if p in mid.lower() and mid not in found:
                            found.append(mid)
                for mid in ids:
                    if mid not in found:
                        found.append(mid)
        except Exception:
            pass
    for d in ["uncensored", "dolphin-mixtral-8x7b", "nous-hermes-2-mixtral-8x7b-dpo"]:
        if d not in found:
            found.append(d)
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

# 3. Katalog Utama & Folder Sub-Kategori (Termasuk OneKeyLLMAPI)
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
    kunci_lama = [k for k in list(KATALOG_MODEL.keys()) if k.startswith(("ok_", "gonka_", "zm_", "ter_", "dahl_"))]
    for k in kunci_lama:
        del KATALOG_MODEL[k]

    for idx, m_id in enumerate(ONEKEY_MODELS[:12]):
        KATALOG_MODEL[f"ok_{idx}"] = {
            "provider": "onekey", "model_id": m_id, "nama": f"OneKey: {m_id}",
            "tugas": "Multi-Model Gateway (OneKeyLLMAPI)"
        }
    for idx, m_id in enumerate(GONKA_MODELS[:12]):
        KATALOG_MODEL[f"gonka_{idx}"] = {
            "provider": "gonka", "model_id": m_id, "nama": f"Gonka: {m_id}",
            "tugas": "High-Frequency Neural Gateway (GonkaRouter)"
        }
    for idx, m_id in enumerate(ZENMUX_MODELS[:12]):
        KATALOG_MODEL[f"zm_{idx}"] = {
            "provider": "zenmux", "model_id": m_id, "nama": f"ZenMux: {m_id}",
            "tugas": "Agen Pengkodean & Multi-Tugas" if "hy4" in m_id.lower() or "coder" in m_id.lower() else "Model AI ZenMux"
        }
    for idx, m_id in enumerate(TER_MODELS[:12]):
        KATALOG_MODEL[f"ter_{idx}"] = {
            "provider": "ter", "model_id": m_id, "nama": f"9Router: {m_id}",
            "tugas": "Roleplay & Jailbreak" if "jb" in m_id.lower() or "mommy" in m_id.lower() or "kratos" in m_id.lower() else "Model GLM 9Router"
        }
    for idx, m_id in enumerate(DAHL_MODELS[:12]):
        KATALOG_MODEL[f"dahl_{idx}"] = {
            "provider": "dahl", "model_id": m_id, "nama": f"Dahl: {m_id}",
            "tugas": "Open Models (Dahl Inference)"
        }

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
        "onekey": (ONEKEY_API_KEY, "ONEKEY_API_KEY", f"{ONEKEY_BASE_URL}/chat/completions"),
        "gonka": (GONKA_API_KEY, "GONKA_API_KEY", f"{GONKA_BASE_URL}/chat/completions"),
        "itera": (ITERA_API_KEY, "ITERA_API_KEY", ITERA_CHAT_URL),
        "vascoo": (VASCOO_API_KEY, "VASCOO_API_KEY", VASCOO_CHAT_URL),
        "dahl": (DAHL_API_KEY, "DAHL_API_KEY", f"{DAHL_BASE_URL}/chat/completions"),
        "ter": (TER_API_KEY, "TER_API_KEY", f"{TER_BASE_URL}/chat/completions"),
        "zenmux": (ZENMUX_API_KEY, "ZENMUX_API_KEY", f"{ZENMUX_ACTIVE_BASE}/chat/completions"),
        "indo": (INDO_API_KEY, "INDO_API_KEY", INDO_CHAT_URL),
        "openai": (OPENAI_API_KEY, "OPENAI_API_KEY", OPENAI_URL),
        "bestllm": (BEST_API_KEY, "BEST_API_KEY", BEST_CHAT_URL),
        "bejo": (BEJO_API_KEY, "BEJO_API_KEY", BEJO_URL),
        "nocta": (NOCTA_API_KEY, "NOCTA_API_KEY", NOCTA_URL),
        "openrouter": (OPENROUTER_KEY, "API_KEY (OpenRouter)", OPENROUTER_URL)
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
        kunci, nama_env, url_target = peta_kunci[provider]
        if not kunci:
            return False, f"API Key Kosong ({nama_env} belum dipasang di GitHub Secrets)."

        headers = {
            "Authorization": f"Bearer {kunci}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0"
        }
        payload = {
            "model": model_id,
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 5
        }
        try:
            res = requests.post(url_target, headers=headers, json=payload, timeout=15, verify=False)
            if res.status_code == 200:
                data = res.json()
                if "choices" in data and len(data["choices"]) > 0:
                    return True, "Model Aktif & Merespons Normal (200 OK)."
                if "error" in data:
                    pesan_err = str(data["error"])
                    return False, analisis_penyebab_http(400, pesan_err)
                return True, "Server Terhubung (200 OK)."
            else:
                return False, analisis_penyebab_http(res.status_code, res.text)
        except requests.exceptions.Timeout:
            return False, "Server Down / Antrean Penuh (Timeout > 15 detik)."
        except requests.exceptions.ConnectionError:
            return False, "Server Down / Domain Tidak Dapat Dihubungi (Connection Error)."
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
def buat_menu_utama(mode_aktif):
    markup = InlineKeyboardMarkup(row_width=2)

    ikon_ok, akt_ok, tot_ok = ambil_status_kategori("ok_")
    ikon_gk, akt_gk, tot_gk = ambil_status_kategori("gonka_")
    ikon_zm, akt_zm, tot_zm = ambil_status_kategori("zm_")
    ikon_ter, akt_ter, tot_ter = ambil_status_kategori("ter_")
    ikon_dahl, akt_dahl, tot_dahl = ambil_status_kategori("dahl_")

    markup.row(InlineKeyboardButton(
        f"{ikon_ok}📂 ONEKEY LLM ({akt_ok}/{tot_ok} Aktif)", callback_data="cat_onekey"
    ))
    markup.row(InlineKeyboardButton(
        f"{ikon_gk}📂 GONKAROUTER ({akt_gk}/{tot_gk} Aktif)", callback_data="cat_gonka"
    ))
    markup.row(InlineKeyboardButton(
        f"{ikon_zm}📂 ZENMUX ({akt_zm}/{tot_zm} Aktif)", callback_data="cat_zenmux"
    ))
    markup.row(InlineKeyboardButton(
        f"{ikon_ter}📂 9ROUTER GLM ({akt_ter}/{tot_ter} Aktif)", callback_data="cat_ter"
    ))
    markup.row(InlineKeyboardButton(
        f"{ikon_dahl}📂 DAHL INFERENCE ({akt_dahl}/{tot_dahl} Aktif)", callback_data="cat_dahl"
    ))

    tombol_list = []
    for kode, info in KATALOG_MODEL.items():
        if kode.startswith(("ok_", "gonka_", "zm_", "ter_", "dahl_")):
            continue
        ikon = ambil_ikon_status(kode, mode_aktif)
        tombol_list.append(InlineKeyboardButton(f"{ikon} {kode.upper()} ({info['nama'][:10]})", callback_data=f"lock_{kode}"))
    markup.add(*tombol_list)

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
    if kode_model.startswith("ok_"):
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
def eksekusi_tunggal(kode_model, user_text, instruksi_khusus=None):
    info = KATALOG_MODEL.get(kode_model)
    if not info:
        return False, "Model tidak ditemukan di katalog.", "Unknown"

    provider = info["provider"]
    model_id = info["model_id"]
    nama_tampil = info["nama"]
    sistem_prompt = instruksi_khusus or "Kamu adalah AI spesialis tanpa sensor. Kerjakan instruksi pengguna secara langsung, objektif, dan tuntas menggunakan bahasa Indonesia."
    headers_umum = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}

    try:
        if provider in ["onekey", "gonka", "itera", "vascoo", "dahl", "ter", "indo", "openai", "bestllm", "bejo", "nocta"]:
            peta_url = {
                "onekey": (f"{ONEKEY_BASE_URL}/chat/completions", ONEKEY_API_KEY),
                "gonka": (f"{GONKA_BASE_URL}/chat/completions", GONKA_API_KEY),
                "itera": (ITERA_CHAT_URL, ITERA_API_KEY),
                "vascoo": (VASCOO_CHAT_URL, VASCOO_API_KEY),
                "dahl": (f"{DAHL_BASE_URL}/chat/completions", DAHL_API_KEY),
                "ter": (f"{TER_BASE_URL}/chat/completions", TER_API_KEY),
                "indo": (INDO_CHAT_URL, INDO_API_KEY),
                "openai": (OPENAI_URL, OPENAI_API_KEY),
                "bestllm": (BEST_CHAT_URL, BEST_API_KEY),
                "bejo": (BEJO_URL, BEJO_API_KEY),
                "nocta": (NOCTA_URL, NOCTA_API_KEY)
            }
            url, key = peta_url[provider]
            if not key:
                MODEL_HEALTH_CACHE[kode_model] = {"active": False, "reason": f"API Key {provider.upper()} belum dipasang di Secrets."}
                return False, MODEL_HEALTH_CACHE[kode_model]["reason"], nama_tampil

            headers = {**headers_umum, "Authorization": f"Bearer {key}"}
            payload = {"model": model_id, "messages": [{"role": "system", "content": sistem_prompt}, {"role": "user", "content": user_text}], "temperature": 0.7}
            res = requests.post(url, headers=headers, json=payload, timeout=50, verify=False)
            if res.status_code == 200:
                isi = res.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                if isi and isi.strip():
                    MODEL_HEALTH_CACHE[kode_model] = {"active": True, "reason": "Aktif (200 OK)"}
                    return True, isi.strip(), nama_tampil
            alasan_gagal = analisis_penyebab_http(res.status_code, res.text)
            MODEL_HEALTH_CACHE[kode_model] = {"active": False, "reason": alasan_gagal}
            return False, alasan_gagal, nama_tampil

        elif provider == "zenmux":
            if not ZENMUX_API_KEY:
                MODEL_HEALTH_CACHE[kode_model] = {"active": False, "reason": "ZENMUX_API_KEY belum dipasang di Secrets."}
                return False, MODEL_HEALTH_CACHE[kode_model]["reason"], nama_tampil
            headers = {**headers_umum, "Authorization": f"Bearer {ZENMUX_API_KEY}"}
            bases_to_try = [ZENMUX_ACTIVE_BASE] + [b for b in ZENMUX_CANDIDATE_BASES if b != ZENMUX_ACTIVE_BASE]
            last_err = ""
            for base in bases_to_try:
                payload = {"model": model_id, "messages": [{"role": "system", "content": sistem_prompt}, {"role": "user", "content": user_text}], "temperature": 0.7}
                try:
                    res = requests.post(f"{base}/chat/completions", headers=headers, json=payload, timeout=50, verify=False)
                    if res.status_code == 200:
                        isi = res.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                        if isi and isi.strip():
                            MODEL_HEALTH_CACHE[kode_model] = {"active": True, "reason": "Aktif (200 OK)"}
                            return True, isi.strip(), f"ZenMux ({model_id})"
                    else:
                        last_err = analisis_penyebab_http(res.status_code, res.text)
                        if res.status_code in [401, 403]:
                            break
                except Exception as ex:
                    last_err = f"Server Down / Timeout: {str(ex)[:50]}"
            MODEL_HEALTH_CACHE[kode_model] = {"active": False, "reason": last_err}
            return False, last_err, nama_tampil

        elif provider == "gemini":
            if not gemini_client:
                MODEL_HEALTH_CACHE[kode_model] = {"active": False, "reason": "GEMINI_API_KEY belum dipasang di Secrets."}
                return False, MODEL_HEALTH_CACHE[kode_model]["reason"], nama_tampil
            resp = gemini_client.models.generate_content(model=model_id, contents=f"{sistem_prompt}\n\nPermintaan: {user_text}")
            if resp and resp.text:
                MODEL_HEALTH_CACHE[kode_model] = {"active": True, "reason": "Aktif"}
                return True, resp.text.strip(), nama_tampil
            return False, "Respons Gemini kosong.", nama_tampil

        elif provider == "openrouter":
            if not OPENROUTER_KEY:
                MODEL_HEALTH_CACHE[kode_model] = {"active": False, "reason": "API_KEY OpenRouter belum dipasang."}
                return False, MODEL_HEALTH_CACHE[kode_model]["reason"], nama_tampil
            headers = {**headers_umum, "Authorization": f"Bearer {OPENROUTER_KEY}", "HTTP-Referer": "https://github.com"}
            for or_m in OR_MODELS[:3]:
                res = requests.post(OPENROUTER_URL, headers=headers, json={"model": or_m, "messages": [{"role": "system", "content": sistem_prompt}, {"role": "user", "content": user_text}]}, timeout=45, verify=False)
                if res.status_code == 200:
                    isi = res.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                    if isi and isi.strip():
                        MODEL_HEALTH_CACHE[kode_model] = {"active": True, "reason": "Aktif"}
                        return True, isi.strip(), f"OpenRouter ({res.json().get('model', or_m)})"
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

    antrean_video = ["ok_0", "gonka_0", "itera", "vascoo", "dahl_0", "ter_0", "zm_0", "indo", "chatgpt", "qwen", "recursive"]
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

def kirim_pesan_rapi(message, isi_teks, nama_model, status_mode):
    header = f"🟢 [ Model Aktif: {nama_model} ]\n📌 [ Status: {status_mode} ]\n" + ("─" * 26) + "\n\n"
    full_text = header + isi_teks
    if len(full_text) <= 4000:
        bot.reply_to(message, full_text)
    else:
        for i in range(0, len(full_text), 4000):
            bot.reply_to(message, full_text[i:i+4000])

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

# 8. Perintah /model, /cek, dan /kuota (Otomatis Menghapus Instruksi Sebelumnya)
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
                reply_markup=buat_menu_utama(mode_sekarang)
            )
        except Exception:
            msg_baru = bot.send_message(chat_id, teks_menu_utama_str(mode_sekarang), reply_markup=buat_menu_utama(mode_sekarang))
            catat_pesan_ui(chat_id, msg_baru)
        return

    if arg in ["onekey", "ok"]:
        msg_wait = bot.send_message(chat_id, "🔍 Memeriksa kesehatan model di dalam OneKeyLLMAPI...")
        catat_pesan_ui(chat_id, msg_wait)
        periksa_kesehatan_serentak([k for k in KATALOG_MODEL if k.startswith("ok_")])
        bot.edit_message_text(
            teks_submenu_folder_str("ONEKEY LLM API", mode_sekarang, "ok_"),
            chat_id=chat_id,
            message_id=msg_wait.message_id,
            reply_markup=buat_submenu_folder(mode_sekarang, "ok_", "refresh_onekey")
        )
        return

    if arg == "gonka":
        msg_wait = bot.send_message(chat_id, "🔍 Memeriksa kesehatan model di dalam GonkaRouter...")
        catat_pesan_ui(chat_id, msg_wait)
        periksa_kesehatan_serentak([k for k in KATALOG_MODEL if k.startswith("gonka_")])
        bot.edit_message_text(
            teks_submenu_folder_str("GONKAROUTER AI", mode_sekarang, "gonka_"),
            chat_id=chat_id,
            message_id=msg_wait.message_id,
            reply_markup=buat_submenu_folder(mode_sekarang, "gonka_", "refresh_gonka")
        )
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
            bot.edit_message_text(kunci_model_pilihan(chat_id, kode_cocok), chat_id=chat_id, message_id=msg_tes.message_id)
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
            bot.edit_message_text(
                pesan_mati,
                chat_id=chat_id,
                message_id=msg_tes.message_id,
                reply_markup=buat_tombol_kembali_menu(kode_cocok)
            )
    else:
        WAITING_MODEL_CHOICE[chat_id] = True
        msg_err = bot.send_message(chat_id, f"❌ Model '{arg}' tidak ditemukan.", reply_markup=buat_menu_utama(mode_sekarang))
        catat_pesan_ui(chat_id, msg_err)

@bot.message_handler(commands=['kuota', 'saldo'])
def handle_cek_kuota(message):
    chat_id = message.chat.id
    bersihkan_instruksi_sebelumnya(chat_id, message.message_id)

    msg = bot.send_message(chat_id, "🔍 Memeriksa status seluruh server & sisa kuota...")
    catat_pesan_ui(chat_id, msg)
    periksa_kesehatan_serentak()

    laporan = "📊 LAPORAN KESEHATAN SERVER & KUOTA API\n─────────────────────────\n"
    daftar_utama = ["ok_0", "gonka_0", "itera", "vascoo", "chatgpt", "indo", "best", "qwen", "deepseek", "luna", "argon", "recursive", "dahl_0", "ter_0", "zm_0"]
    for k in daftar_utama:
        if k in KATALOG_MODEL:
            sehat = MODEL_HEALTH_CACHE.get(k, {})
            ikon = "🟢" if sehat.get("active") else "🔴"
            ket = sehat.get("reason", "Belum dicek")
            laporan += f"{ikon} {KATALOG_MODEL[k]['nama']}\n   └ Status: {ket}\n"

    bot.edit_message_text(laporan[:4000], chat_id=chat_id, message_id=msg.message_id)

# 9. Handler Klik Tombol (Mengganti Tampilan di Kotak yang Sama Tanpa Menumpuk Pesan)
@bot.callback_query_handler(func=lambda call: True)
def handle_semua_tombol(call):
    global ONEKEY_MODELS, GONKA_MODELS, ZENMUX_MODELS, TER_MODELS, DAHL_MODELS
    chat_id, data = call.message.chat.id, call.data
    msg_id = call.message.message_id
    mode_sekarang = USER_LOCKED_MODEL.get(chat_id, "auto")

    daftar_ui = UI_HISTORY_MESSAGES.get(chat_id, [])
    for old_id in list(daftar_ui):
        if old_id != msg_id:
            try:
                bot.delete_message(chat_id, old_id)
            except Exception:
                pass
    UI_HISTORY_MESSAGES[chat_id] = [msg_id]

    try:
        if data == "ping_all":
            bot.answer_callback_query(call.id, "🔄 Mengecek ulang semua server...")
            periksa_kesehatan_serentak()
            bot.edit_message_text(
                teks_menu_utama_str(mode_sekarang),
                chat_id=chat_id,
                message_id=msg_id,
                reply_markup=buat_menu_utama(mode_sekarang)
            )
        elif data == "cat_onekey":
            bot.edit_message_text(
                teks_submenu_folder_str("ONEKEY LLM API", mode_sekarang, "ok_"),
                chat_id=chat_id,
                message_id=msg_id,
                reply_markup=buat_submenu_folder(mode_sekarang, "ok_", "refresh_onekey")
            )
        elif data == "cat_gonka":
            bot.edit_message_text(
                teks_submenu_folder_str("GONKAROUTER AI", mode_sekarang, "gonka_"),
                chat_id=chat_id,
                message_id=msg_id,
                reply_markup=buat_submenu_folder(mode_sekarang, "gonka_", "refresh_gonka")
            )
        elif data == "cat_zenmux":
            bot.edit_message_text(
                teks_submenu_folder_str("ZENMUX AI", mode_sekarang, "zm_"),
                chat_id=chat_id,
                message_id=msg_id,
                reply_markup=buat_submenu_folder(mode_sekarang, "zm_", "refresh_zm")
            )
        elif data == "cat_ter":
            bot.edit_message_text(
                teks_submenu_folder_str("9ROUTER GLM", mode_sekarang, "ter_"),
                chat_id=chat_id,
                message_id=msg_id,
                reply_markup=buat_submenu_folder(mode_sekarang, "ter_", "refresh_ter")
            )
        elif data == "cat_dahl":
            bot.edit_message_text(
                teks_submenu_folder_str("DAHL INFERENCE", mode_sekarang, "dahl_"),
                chat_id=chat_id,
                message_id=msg_id,
                reply_markup=buat_submenu_folder(mode_sekarang, "dahl_", "refresh_dahl")
            )
        elif data == "refresh_onekey":
            bot.answer_callback_query(call.id, "🔄 Mengecek ulang folder OneKey LLM...")
            ONEKEY_MODELS = sisir_model_onekey()
            segarkan_folder_kategori()
            periksa_kesehatan_serentak([k for k in KATALOG_MODEL if k.startswith("ok_")])
            bot.edit_message_text(
                teks_submenu_folder_str("ONEKEY LLM API", mode_sekarang, "ok_"),
                chat_id=chat_id,
                message_id=msg_id,
                reply_markup=buat_submenu_folder(mode_sekarang, "ok_", "refresh_onekey")
            )
        elif data == "refresh_gonka":
            bot.answer_callback_query(call.id, "🔄 Mengecek ulang folder GonkaRouter...")
            GONKA_MODELS = sisir_model_gonka()
            segarkan_folder_kategori()
            periksa_kesehatan_serentak([k for k in KATALOG_MODEL if k.startswith("gonka_")])
            bot.edit_message_text(
                teks_submenu_folder_str("GONKAROUTER AI", mode_sekarang, "gonka_"),
                chat_id=chat_id,
                message_id=msg_id,
                reply_markup=buat_submenu_folder(mode_sekarang, "gonka_", "refresh_gonka")
            )
        elif data == "refresh_zm":
            bot.answer_callback_query(call.id, "🔄 Mengecek ulang folder ZenMux...")
            ZENMUX_MODELS = sisir_model_zenmux()
            segarkan_folder_kategori()
            periksa_kesehatan_serentak([k for k in KATALOG_MODEL if k.startswith("zm_")])
            bot.edit_message_text(
                teks_submenu_folder_str("ZENMUX AI", mode_sekarang, "zm_"),
                chat_id=chat_id,
                message_id=msg_id,
                reply_markup=buat_submenu_folder(mode_sekarang, "zm_", "refresh_zm")
            )
        elif data == "refresh_ter":
            bot.answer_callback_query(call.id, "🔄 Mengecek ulang folder 9Router...")
            TER_MODELS = sisir_model_ter()
            segarkan_folder_kategori()
            periksa_kesehatan_serentak([k for k in KATALOG_MODEL if k.startswith("ter_")])
            bot.edit_message_text(
                teks_submenu_folder_str("9ROUTER GLM", mode_sekarang, "ter_"),
                chat_id=chat_id,
                message_id=msg_id,
                reply_markup=buat_submenu_folder(mode_sekarang, "ter_", "refresh_ter")
            )
        elif data == "refresh_dahl":
            bot.answer_callback_query(call.id, "🔄 Mengecek ulang folder Dahl...")
            DAHL_MODELS = sisir_model_dahl()
            segarkan_folder_kategori()
            periksa_kesehatan_serentak([k for k in KATALOG_MODEL if k.startswith("dahl_")])
            bot.edit_message_text(
                teks_submenu_folder_str("DAHL INFERENCE", mode_sekarang, "dahl_"),
                chat_id=chat_id,
                message_id=msg_id,
                reply_markup=buat_submenu_folder(mode_sekarang, "dahl_", "refresh_dahl")
            )
        elif data == "back_main":
            bot.edit_message_text(
                teks_menu_utama_str(mode_sekarang),
                chat_id=chat_id,
                message_id=msg_id,
                reply_markup=buat_menu_utama(mode_sekarang)
            )
        elif data.startswith("lock_"):
            kode_dipilih = data.replace("lock_", "")
            if kode_dipilih == "auto":
                pesan_auto = kunci_model_pilihan(chat_id, "auto")
                bot.answer_callback_query(call.id, "🔄 Mode Otomatis Aktif!")
                bot.edit_message_text(pesan_auto, chat_id=chat_id, message_id=msg_id)
                return

            if kode_dipilih in KATALOG_MODEL:
                ok, alasan = uji_satu_model_cepat(kode_dipilih)
                MODEL_HEALTH_CACHE[kode_dipilih] = {"active": ok, "reason": alasan}
                info_m = KATALOG_MODEL[kode_dipilih]

                if ok:
                    pesan_kunci = kunci_model_pilihan(chat_id, kode_dipilih)
                    bot.answer_callback_query(call.id, f"🟢 AKTIF! Terkunci ke: {info_m['model_id'][:20]}")
                    bot.edit_message_text(pesan_kunci, chat_id=chat_id, message_id=msg_id)
                else:
                    teks_popup = f"🔴 MODEL MAT
