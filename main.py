import os
import time
import re
import telebot
from telebot import apihelper
import requests
import urllib.parse
import random
import urllib3
from google import genai

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 1. Kredensial dari GitHub Secrets (Tanpa Hardcode)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
PROXY_URL = os.environ.get("PROXY_URL", "").strip()
BEJO_API_KEY = os.environ.get("BEJO_API_KEY", "").strip()
NOCTA_API_KEY = os.environ.get("NOCTA_API_KEY", "").strip()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
OPENROUTER_KEY = os.environ.get("API_KEY", "").strip()

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN kosong! Harap isi di GitHub Secrets.")

# Endpoint Server
BEJO_URL = "https://bejoxxx.tech/v1/chat/completions"
NOCTA_URL = "https://nocta-digital.web.id/v1/chat/completions"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Inisialisasi Gemini
gemini_client = None
if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Info Gemini: {e}")

# 2. Pengecekan Proxy
use_proxy = False
if PROXY_URL:
    try:
        test = requests.get("https://api.telegram.org", proxies={"http": PROXY_URL, "https": PROXY_URL}, timeout=8)
        if test.status_code == 200:
            use_proxy = True
            apihelper.proxy = {'http': PROXY_URL, 'https': PROXY_URL}
    except Exception:
        print("Proxy dilewati, memakai koneksi langsung GitHub.")

bot = telebot.TeleBot(BOT_TOKEN)

# Penyimpanan Mode Pilihan Pengguna (Agar tidak bertabrakan antar user)
USER_MODE = {}

# Daftar Model Cadangan OpenRouter
def get_openrouter_models():
    priorities = ["cognitivecomputations/dolphin", "nousresearch/hermes", "gryphe/mythomax", "meta-llama/llama-3"]
    available = []
    try:
        res = requests.get("https://openrouter.ai/api/v1/models", timeout=10)
        if res.status_code == 200:
            all_m = res.json().get("data", [])
            free_ids = [m["id"] for m in all_m if m.get("id", "").endswith(":free")]
            for p in priorities:
                for fid in free_ids:
                    if p.lower() in fid.lower() and fid not in available:
                        available.append(fid)
            for fid in free_ids:
                if fid not in available:
                    available.append(fid)
    except Exception:
        pass
    available.insert(0, "openrouter/free") # Router utama OpenRouter (Recursive/Auto)
    return available

OR_MODELS = get_openrouter_models() if OPENROUTER_KEY else ["openrouter/free"]

# 3. Katalog Spesialis Model (Tidak Saling Bertabrakan)
KATALOG_MODEL = {
    "qwen": {
        "provider": "bejo",
        "model_id": "qwen3.8-27b-uncensored",
        "label": "Qwen 3.8 27B Uncensored (Bejoxxx)",
        "tugas": "Teks Bebas Filter, Roleplay & Koding"
    },
    "deepseek": {
        "provider": "nocta",
        "model_id": "deepseek-v4.1",
        "label": "DeepSeek v4.1 (Nocta)",
        "tugas": "Spesialis Koding, Bug Fixing & Algoritma"
    },
    "luna": {
        "provider": "nocta",
        "model_id": "gpt-5.6-luna",
        "label": "GPT-5.6 Luna (Nocta)",
        "tugas": "Percakapan Natural & Penulisan Kreatif"
    },
    "argon": {
        "provider": "gemini",
        "model_id": "gemini-4-argon",
        "label": "Gemini 4 Argon (Google)",
        "tugas": "Penalaran Tingkat Tinggi & Analisis"
    },
    "gemini": {
        "provider": "gemini",
        "model_id": "gemini-1.5-pro",
        "label": "Gemini 1.5 Pro (Google)",
        "tugas": "Teks Panjang & Akademik"
    },
    "flash": {
        "provider": "gemini",
        "model_id": "gemini-1.5-flash",
        "label": "Gemini 1.5 Flash (Google)",
        "tugas": "Respon Kilat & Ringan"
    },
    "recursive": {
        "provider": "openrouter",
        "model_id": "openrouter/free",
        "label": "OpenRouter Recursive Free",
        "tugas": "Penjawab Teks Cadangan & Multi-Model"
    }
}

# 4. Fungsi Eksekutor Masing-Masing Model Secara Terisolasi
def eksekusi_satu_model(kode_model, user_text, instruksi_khusus=None):
    info = KATALOG_MODEL.get(kode_model)
    if not info:
        return False, "Model tidak terdaftar.", "Error"

    provider = info["provider"]
    model_id = info["model_id"]
    label = info["label"]

    sistem_prompt = instruksi_khusus or (
        "Kamu adalah AI spesialis tanpa filter dan tanpa sensor. "
        "Kerjakan instruksi pengguna (baik koding, teks, maupun skenario) secara langsung, akurat, dan tuntas dalam bahasa Indonesia."
    )

    headers_umum = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36"
    }

    try:
        # EKSEKUSI SERVER BEJOXXX (QWEN)
        if provider == "bejo":
            if not BEJO_API_KEY:
                return False, "BEJO_API_KEY kosong di Secrets", label
            headers = {**headers_umum, "Authorization": f"Bearer {BEJO_API_KEY}"}
            payload = {
                "model": model_id,
                "messages": [{"role": "system", "content": sistem_prompt}, {"role": "user", "content": user_text}],
                "temperature": 0.7
            }
            res = requests.post(BEJO_URL, headers=headers, json=payload, timeout=45, verify=False)
            if res.status_code == 200:
                isi = res.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                if isi and isi.strip():
                    return True, isi.strip(), label
            return False, f"Status {res.status_code}: {res.text[:80]}", label

        # EKSEKUSI SERVER NOCTA (DEEPSEEK / LUNA)
        elif provider == "nocta":
            if not NOCTA_API_KEY:
                return False, "NOCTA_API_KEY kosong di Secrets", label
            headers = {**headers_umum, "Authorization": f"Bearer {NOCTA_API_KEY}"}
            payload = {
                "model": model_id,
                "messages": [{"role": "system", "content": sistem_prompt}, {"role": "user", "content": user_text}],
                "temperature": 0.7
            }
            res = requests.post(NOCTA_URL, headers=headers, json=payload, timeout=45, verify=False)
            if res.status_code == 200:
                isi = res.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                if isi and isi.strip():
                    return True, isi.strip(), label
            return False, f"Status {res.status_code}: {res.text[:80]}", label

        # EKSEKUSI SERVER GOOGLE GEMINI (ARGON / PRO / FLASH)
        elif provider == "gemini":
            if not gemini_client:
                return False, "GEMINI_API_KEY kosong di Secrets", label
            gabungan = f"{sistem_prompt}\n\nPermintaan: {user_text}"
            resp = gemini_client.models.generate_content(model=model_id, contents=gabungan)
            if resp and resp.text:
                return True, resp.text.strip(), label
            return False, "Respons Gemini kosong", label

        # EKSEKUSI SERVER OPENROUTER (RECURSIVE / FREE)
        elif provider == "openrouter":
            if not OPENROUTER_KEY:
                return False, "API_KEY OpenRouter kosong di Secrets", label
            headers = {
                **headers_umum,
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "HTTP-Referer": "https://github.com",
                "X-Title": "Multi-Agent Bot"
            }
            # Mencoba antrean model di OpenRouter sampai dapat yang aktif
            for or_m in OR_MODELS[:4]:
                payload = {
                    "model": or_m,
                    "messages": [{"role": "system", "content": sistem_prompt}, {"role": "user", "content": user_text}]
                }
                res = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=45, verify=False)
                if res.status_code == 200:
                    data = res.json()
                    isi = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    model_aktual = data.get("model", or_m)
                    if isi and isi.strip():
                        return True, isi.strip(), f"OpenRouter ({model_aktual})"
            return False, "Server OpenRouter sedang sibuk", label

    except Exception as e:
        return False, f"Koneksi gagal ({str(e)[:70]})", label

    return False, "Gagal tidak diketahui", label

# 5. Fungsi Menjalankan Antrean Berdasarkan Jenis Tugas
def jalankan_antrean_tugas(urutan_kode, user_text, instruksi_khusus=None):
    catatan_error = []
    for kode in urutan_kode:
        ok, hasil, label_dipakai = eksekusi_satu_model(kode, user_text, instruksi_khusus)
        if ok:
            return True, hasil, label_dipakai, catatan_error
        catatan_error.append(f"• {kode.upper()}: {hasil}")
    return False, "", "Gagal Semua", catatan_error

# 6. Mesin Spesialis Gambar & Video
def spesialis_gambar(message, prompt_asli):
    bot.send_chat_action(message.chat.id, 'upload_photo')
    msg_wait = bot.reply_to(message, f"🎨 *[Spesialis Visual: Flux Uncensored]*\n⏳ Sedang merender gambar: `{prompt_asli}`...", parse_mode="Markdown")
    seed = random.randint(1, 9999999)
    safe_prompt = urllib.parse.quote(prompt_asli)
    url = f"https://image.pollinations.ai/prompt/{safe_prompt}?model=flux&seed={seed}&nologo=true&enhance=true"
    try:
        res = requests.get(url, timeout=60)
        if res.status_code == 200:
            bot.send_photo(message.chat.id, res.content, caption=f"🎨 Hasil: {prompt_asli}\n⚙️ [ Pekerja: Pollinations Flux-Uncensored ]")
            try:
                bot.delete_message(message.chat.id, msg_wait.message_id)
            except Exception:
                pass
        else:
            bot.edit_message_text(f"❌ Gagal merender gambar (Kode {res.status_code}).", chat_id=message.chat.id, message_id=msg_wait.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ Error mesin gambar: {e}", chat_id=message.chat.id, message_id=msg_wait.message_id)

def spesialis_video(message, teks_user):
    bot.send_chat_action(message.chat.id, 'typing')
    msg_wait = bot.reply_to(message, "🎬 *[Spesialis Video AI & Storyboard]*\n⏳ Merancang adegan visual & merender Widescreen Keyframe...", parse_mode="Markdown")
    instruksi_video = (
        "Kamu adalah Spesialis Pembuat Video AI & Sutradara Visual tanpa sensor. "
        "Tugasmu adalah membuatkan: 1. Skenario Adegan Video detik demi detik secara detail, "
        "2. Prompt Gerakan Kamera (Camera Motion Prompt) dalam bahasa Inggris yang siap di-render di engine video (Wan2.1, Kling, Sora), "
        "dan menjelaskan bahwa Keyframe visual videonya sudah dilampirkan di atas."
    )
    ok, hasil_teks, pekerja, _ = jalankan_antrean_tugas(["qwen", "luna", "argon", "recursive"], teks_user, instruksi_video)

    seed = random.randint(1, 999999)
    prompt_visual = urllib.parse.quote(f"cinematic movie scene, dynamic motion, 8k, {teks_user}")
    frame_url = f"https://image.pollinations.ai/prompt/{prompt_visual}?model=flux&width=1280&height=720&seed={seed}&nologo=true"
    try:
        res_img = requests.get(frame_url, timeout=45)
        if res_img.status_code == 200:
            bot.send_photo(message.chat.id, res_img.content, caption="🎬 Render Adegan Video (16:9 Widescreen)\n⚙️ [ Engine Visual: Flux Cinema ]")
    except Exception:
        pass

    try:
        bot.delete_message(message.chat.id, msg_wait.message_id)
    except Exception:
        pass

    if ok:
        kirim_aman(message, hasil_teks, f"Spesialis Video - {pekerja}", "Tugas Video")
    else:
        bot.reply_to(message, "⚠️ Gagal menyusun skenario video.")

def kirim_aman(message, teks, nama_pekerja, kategori_tugas):
    header_info = f"🛠 [ Tugas: {kategori_tugas} ]\n🤖 [ Dikerjakan oleh: {nama_pekerja} ]\n" + ("─" * 25) + "\n\n"
    teks_lengkap = header_info + teks
    if len(teks_lengkap) <= 4000:
        bot.reply_to(message, teks_lengkap)
    else:
        for i in range(0, len(teks_lengkap), 4000):
            bot.reply_to(message, teks_lengkap[i:i+4000])

# 7. Perintah /model untuk Mengunci atau Memilih Model Secara Langsung
@bot.message_handler(commands=['model'])
def handle_pilih_model(message):
    chat_id = message.chat.id
    arg = message.text.replace('/model', '').strip().lower()
    arg = re.sub(r'[\(\)\[\]]', '', arg) # Bersihkan tanda kurung jika user ketik /model (qwen)

    mode_saat_ini = USER_MODE.get(chat_id, "auto")

    if not arg:
        daftar = (
            f"⚙️ **Pengaturan Model Saat Ini:** `{mode_saat_ini.upper()}`\n\n"
            "Gunakan perintah di bawah ini untuk memanggil/mengunci model tertentu agar bertugas:\n"
            "• `/model auto` — Otomatis sesuai jenis tugas (Rekomendasi)\n"
            "• `/model qwen` — Kunci **Qwen 3.8 27B Uncensored** (Bejoxxx)\n"
            "• `/model deepseek` — Kunci **DeepSeek v4.1** (Spesialis Koding)\n"
            "• `/model luna` — Kunci **GPT-5.6 Luna** (Nocta)\n"
            "• `/model argon` — Kunci **Gemini 4 Argon** (Penalaran Tinggi)\n"
            "• `/model gemini` — Kunci **Gemini 1.5 Pro**\n"
            "• `/model flash` — Kunci **Gemini 1.5 Flash**\n"
            "• `/model recursive` — Kunci **OpenRouter Recursive/Free**\n"
            "• `/model gambar` — Kunci Mode **Pembuat Gambar**\n"
            "• `/model video` — Kunci Mode **Pembuat Video**"
        )
        bot.reply_to(message, daftar, parse_mode="Markdown")
        return

    pilihan_valid = list(KATALOG_MODEL.keys()) + ["auto", "gambar", "video"]
    if arg in pilihan_valid:
        USER_MODE[chat_id] = arg
        if arg == "auto":
            bot.reply_to(message, "✅ Mode diubah ke **OTOMATIS**. Setiap pesan akan dikerjakan oleh model yang paling ahli di bidangnya!", parse_mode="Markdown")
        elif arg in ["gambar", "video"]:
            bot.reply_to(message, f"✅ Mode dikunci ke **SPESIALIS {arg.upper()}**. Kirim deskripsi apa saja, dan model {arg} yang akan langsung mengerjakannya!", parse_mode="Markdown")
        else:
            detail = KATALOG_MODEL[arg]
            bot.reply_to(
                message,
                f"✅ **Model Berhasil Dikunci!**\n\n"
                f"🤖 **Pekerja Onsite:** `{detail['label']}`\n"
                f"🎯 **Keahlian:** {detail['tugas']}\n\n"
                f"Sekarang semua pesanmu akan langsung ditangani oleh model ini. Ketik `/model auto` jika ingin kembali otomatis.",
                parse_mode="Markdown"
            )
    else:
        bot.reply_to(message, f"❌ Nama model `{arg}` tidak dikenali. Ketik `/model` untuk melihat daftar nama model yang benar.", parse_mode="Markdown")

@bot.message_handler(commands=['start', 'help', 'status'])
def send_welcome(message):
    mode = USER_MODE.get(message.chat.id, "auto").upper()
    pesan = (
        f"🤖 **Smart Specialist AI Bot Aktif!** (Mode: `{mode}`)\n\n"
        "Bot ini membagi pekerjaan secara otomatis sesuai keahlian model:\n"
        "💻 **Tugas Koding:** `deepseek-v4.1` / `qwen3.8-27b`\n"
        "🔓 **Teks Uncensored:** `qwen3.8-27b-uncensored` / `gpt-5.6-luna`\n"
        "🧠 **Analisis & Logika:** `gemini-4-argon`\n"
        "🔄 **Teks Recursive:** `openrouter/free`\n"
        "🎨 **Tugas Gambar:** `Pollinations Flux`\n"
        "🎬 **Tugas Video:** `AI Video Director + Keyframe`\n\n"
        "📌 **Ingin memanggil 1 model spesifik?**\n"
        "Ketik `/model qwen` atau `/model recursive` atau `/model deepseek` (Ketik `/model` untuk daftar lengkap)."
    )
    bot.reply_to(message, pesan, parse_mode="Markdown")

# 8. Otak Pendeteksi Jenis Pekerjaan Otomatis (Task Classifier)
def deteksi_jenis_pekerjaan(teks):
    t = teks.lower()

    # 1. Cek apakah meminta pembuatan Video
    if re.search(r"\b(buatkan video|bikin video|bisa buat video|bisa bikin video|generate video|video tentang|animasikan)\b", t):
        return "video"

    # 2. Cek apakah meminta pembuatan Gambar / Foto
    if re.search(r"^(buatkan|bikin|tolong buatkan|coba buat|lukiskan|gambarin|generate)\s+(gambar|foto|ilustrasi|lukisan)\b", t) or t.startswith("gambar "):
        return "gambar"

    # 3. Cek apakah meminta pekerjaan Koding / Pemrograman
    kata_koding = ["koding", "coding", "script", "python", "html", "javascript", "php", "css", "error", "bug", "buatkan kode", "source code", "github", "yml", "api", "fungsi", "sql", "database", "bot"]
    if any(k in t for k in kata_koding):
        return "koding"

    # 4. Cek apakah meminta pekerjaan Recursive / OpenRouter secara spesifik di dalam kalimat
    if "recursive" in t or "openrouter" in t:
        return "recursive_task"

    # 5. Cek apakah meminta Analisis / Matematika / Penalaran Rumit
    kata_analisis = ["analisis", "hitung", "rumus", "jelaskan secara ilmiah", "bandingkan", "strategi", "rangkum", "kesimpulan"]
    if any(k in t for k in kata_analisis):
        return "analisis"

    # 6. Default: Teks Bebas / Chat Uncensored / Roleplay
    return "teks_bebas"

# 9. Handler Utama: Mengarahkan Tugas Tanpa Tabrakan
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    if not message.text:
        return

    chat_id = message.chat.id
    teks = message.text.strip()
    mode_pilihan = USER_MODE.get(chat_id, "auto")

    # JALUR A: JIKA PENGGUNA MENGUNCI MODEL TERTENTU LEWAT /model
    if mode_pilihan != "auto":
        if mode_pilihan == "gambar":
            spesialis_gambar(message, teks)
            return
        elif mode_pilihan == "video":
            spesialis_video(message, teks)
            return
        else:
            bot.send_chat_action(chat_id, 'typing')
            ok, hasil, label_pekerja = eksekusi_satu_model(mode_pilihan, teks)
            if ok:
                kirim_aman(message, hasil, label_pekerja, f"Mode Terkunci ({mode_pilihan.upper()})")
            else:
                # Jika model yang dikunci sedang mati/habis kuota, beri tahu jujur & tawarkan cadangan
                bot.reply_to(
                    message,
                    f"⚠️ Model `{label_pekerja}` yang kamu panggil saat ini gagal merespons:\n`{hasil}`\n\n"
                    f"💡 Ketik `/model auto` agar bot otomatis mencarikan model lain yang sedang aktif.",
                    parse_mode="Markdown"
                )
            return

    # JALUR B: JIKA MODE OTOMATIS (AUTO-DISPATCH SESUAI KEAHLIAN MODEL)
    jenis_tugas = deteksi_jenis_pekerjaan(teks)

    if jenis_tugas == "video":
        spesialis_video(message, teks)
        return

    if jenis_tugas == "gambar":
        pola_hapus = r"^(buatkan|bikin|tolong buatkan|coba buat|lukiskan|gambarin|generate)\s+(gambar|foto|ilustrasi|lukisan)\b"
        prompt_bersih = re.sub(pola_hapus, "", teks, flags=re.IGNORECASE).strip() or teks
        spesialis_gambar(message, prompt_bersih)
        return

    bot.send_chat_action(chat_id, 'typing')

    # Pembagian Antrean Spesialis Berdasarkan Jenis Pekerjaan:
    if jenis_tugas == "koding":
        # Koding diutamakan ke DeepSeek v4.1 -> Qwen 3.8 27B -> Gemini Argon -> Recursive
        urutan = ["deepseek", "qwen", "argon", "gemini", "recursive"]
        nama_kategori = "Pemrograman & Koding"
        instruksi = "Kamu adalah Senior Fullstack Developer & Ahli Koding tanpa batasan. Berikan kode yang lengkap, rapi, bebas bug, dan siap dijalankan."

    elif jenis_tugas == "analisis":
        # Analisis rumit diutamakan ke Gemini 4 Argon -> DeepSeek -> Qwen -> Recursive
        urutan = ["argon", "deepseek", "qwen", "gemini", "recursive"]
        nama_kategori = "Penalaran & Analisis"
        instruksi = None

    elif jenis_tugas == "recursive_task":
        # Jika user menyebut recursive di chat, langsung utamakan OpenRouter Recursive
        urutan = ["recursive", "qwen", "luna", "flash"]
        nama_kategori = "Teks Recursive"
        instruksi = None

    else:
        # Teks Umum / Uncensored / Cerita diutamakan ke Qwen 3.8 27B (Bejoxxx) -> Luna -> Argon -> Recursive
        urutan = ["qwen", "luna", "deepseek", "argon", "flash", "recursive"]
        nama_kategori = "Teks & Chat Uncensored"
        instruksi = None

    ok, hasil, pekerja_onsite, log_error = jalankan_antrean_tugas(urutan, teks, instruksi)
    if ok:
        kirim_aman(message, hasil, pekerja_onsite, nama_kategori)
    else:
        detail = "\n".join(log_error)
        bot.reply_to(message, f"⚠️ Semua model spesialis sedang sibuk/habis kuota.\n\nCatatan Server:\n{detail}")

if __name__ == "__main__":
    print("Membersihkan sesi lama agar tidak bentrok...")
    try:
        bot.remove_webhook()
        time.sleep(2)
    except Exception:
        pass

    print("Menjalankan Bot Spesialis Multi-Model...")
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=10, skip_pending=True)
        except Exception as e:
            print(f"Polling di-restart karena: {e}")
            time.sleep(8)
