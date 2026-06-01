import streamlit as st
import sqlite3
import time
import random
import json
from datetime import datetime

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
QUESTION_TIME = 20  # seconds per question
MAX_SCORE = 1000    # max points for instant correct answer

st.set_page_config(
    page_title="🎲 Quiz Arena",
    page_icon="🎲",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────
# SAMPLE QUESTIONS (replace with your content)
# ─────────────────────────────────────────────
QUESTIONS = {
    1: {
        "q": "Merkez Bankası'nın temel para politikası aracı hangisidir?",
        "options": ["Döviz rezervi", "Politika faizi", "Zorunlu karşılık", "Açık piyasa işlemleri"],
        "answer": 1,
    },
    2: {
        "q": "Bir bankanın sermaye yeterliliği rasyosu neyi ölçer?",
        "options": ["Likidite gücü", "Kredi kalitesi", "Risklere karşı sermaye tamponunu", "Mevduat büyümesini"],
        "answer": 2,
    },
    3: {
        "q": "IBAN kısaltmasının açılımı nedir?",
        "options": ["International Bank Account Number", "Internal Banking Authorization Node", "Integrated Balance Audit Network", "Inter-Bank Allocation Notation"],
        "answer": 0,
    },
    4: {
        "q": "Repo işleminde ne gerçekleşir?",
        "options": ["Hisse senedi alım satımı", "Kısa vadeli menkul kıymet karşılığı borçlanma", "Döviz swapı", "Uzun vadeli kredi açılması"],
        "answer": 1,
    },
    5: {
        "q": "Enflasyon oranı faiz oranından yüksekse reel faiz ne olur?",
        "options": ["Pozitif", "Negatif", "Sıfır", "Değişmez"],
        "answer": 1,
    },
    6: {
        "q": "Kredi temerrüt swapı (CDS) ne amaçla kullanılır?",
        "options": ["Kur riskinden korunmak", "Kredi riskini transfer etmek", "Faiz arbitrajı", "Likidite sağlamak"],
        "answer": 1,
    },
    7: {
        "q": "Basel III düzenlemeleri öncelikle neyi hedefler?",
        "options": ["Banka karlılığını artırmak", "Bankacılık sektörü dayanıklılığını güçlendirmek", "Kredi faizlerini düşürmek", "Mevduat güvencesini kaldırmak"],
        "answer": 1,
    },
    8: {
        "q": "Bir tahvilin kuponu nedir?",
        "options": ["Tahvilin satış fiyatı", "Periyodik faiz ödemesi", "Vade sonu değeri", "İhraç maliyeti"],
        "answer": 1,
    },
    9: {
        "q": "Likidite riski ne anlama gelir?",
        "options": ["Piyasa fiyatlarının dalgalanması", "Yükümlülükleri karşılayacak nakit bulunamaması", "Kredi geri ödenmemesi", "Operasyonel aksaklıklar"],
        "answer": 1,
    },
    10: {
        "q": "Swap işleminin temel amacı nedir?",
        "options": ["Spekülatif kazanç", "Nakit akışlarını değiştirmek / riskten korunmak", "Mevduat toplamak", "Sermaye artırmak"],
        "answer": 1,
    },
    11: {
        "q": "Bir şirketin öz kaynak karlılığı (ROE) nasıl hesaplanır?",
        "options": ["Net Kar / Toplam Varlıklar", "Net Kar / Öz Kaynak", "FAVÖK / Gelir", "Brüt Kar / Net Satışlar"],
        "answer": 1,
    },
    12: {
        "q": "Menkul kıymetleştirme sürecinde ne yapılır?",
        "options": ["Hisse senedi ihraç edilir", "Varlıklar havuzlanarak tahvile dönüştürülür", "Merkez Bankası'na başvurulur", "Döviz pozisyonu kapatılır"],
        "answer": 1,
    },
}

# ─────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────
DB = "quiz_game.db"

def get_conn():
    return sqlite3.connect(DB, check_same_thread=False)

def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                score INTEGER DEFAULT 0,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS game_state (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_name TEXT,
                question_no INTEGER,
                answer_idx INTEGER,
                is_correct INTEGER,
                response_ms INTEGER,
                score_gained INTEGER,
                answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Default game state
        defaults = {
            "status": "lobby",       # lobby | rolling | question | result | finished
            "current_question": "0",
            "question_start": "0",
            "dice_result": "0",
        }
        for k, v in defaults.items():
            conn.execute("INSERT OR IGNORE INTO game_state (key, value) VALUES (?, ?)", (k, v))
        conn.commit()

def get_state(key):
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM game_state WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

def set_state(key, value):
    with get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO game_state (key, value) VALUES (?, ?)", (key, str(value)))
        conn.commit()

def get_players():
    with get_conn() as conn:
        return conn.execute("SELECT name, score FROM players ORDER BY score DESC").fetchall()

def add_player(name):
    try:
        with get_conn() as conn:
            conn.execute("INSERT INTO players (name) VALUES (?)", (name,))
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def submit_answer(player_name, question_no, answer_idx, response_ms):
    q = QUESTIONS.get(question_no)
    if not q:
        return False, 0
    is_correct = int(answer_idx == q["answer"])
    score_gained = 0
    if is_correct:
        score_gained = max(100, int(MAX_SCORE * (1 - response_ms / (QUESTION_TIME * 1000 * 1.2))))
    with get_conn() as conn:
        # Prevent duplicate answers
        existing = conn.execute(
            "SELECT id FROM answers WHERE player_name=? AND question_no=?",
            (player_name, question_no)
        ).fetchone()
        if existing:
            return False, 0
        conn.execute(
            "INSERT INTO answers (player_name, question_no, answer_idx, is_correct, response_ms, score_gained) VALUES (?,?,?,?,?,?)",
            (player_name, question_no, answer_idx, is_correct, response_ms, score_gained)
        )
        if is_correct:
            conn.execute("UPDATE players SET score = score + ? WHERE name=?", (score_gained, player_name))
        conn.commit()
    return is_correct, score_gained

def get_question_results(question_no):
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT player_name, is_correct, score_gained, response_ms
            FROM answers WHERE question_no=?
            ORDER BY score_gained DESC, response_ms ASC
        """, (question_no,)).fetchall()
    return rows

def has_answered(player_name, question_no):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM answers WHERE player_name=? AND question_no=?",
            (player_name, question_no)
        ).fetchone()
    return row is not None

def reset_game():
    with get_conn() as conn:
        conn.execute("DELETE FROM players")
        conn.execute("DELETE FROM answers")
        conn.execute("UPDATE game_state SET value='lobby' WHERE key='status'")
        conn.execute("UPDATE game_state SET value='0' WHERE key='current_question'")
        conn.execute("UPDATE game_state SET value='0' WHERE key='question_start'")
        conn.execute("UPDATE game_state SET value='0' WHERE key='dice_result'")
        conn.commit()

# ─────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────
def inject_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Fredoka+One&family=Nunito:wght@400;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Nunito', sans-serif;
    }

    .stApp {
        background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
        min-height: 100vh;
    }

    .big-title {
        font-family: 'Fredoka One', cursive;
        font-size: 3.5rem;
        color: #FFD700;
        text-align: center;
        text-shadow: 0 0 30px rgba(255,215,0,0.5);
        margin-bottom: 0.2rem;
    }

    .subtitle {
        text-align: center;
        color: #a78bfa;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }

    .card {
        background: rgba(255,255,255,0.07);
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 20px;
        padding: 2rem;
        backdrop-filter: blur(10px);
        margin-bottom: 1.5rem;
    }

    .question-text {
        font-family: 'Fredoka One', cursive;
        font-size: 1.8rem;
        color: white;
        text-align: center;
        line-height: 1.4;
        margin-bottom: 1.5rem;
    }

    .dice-display {
        font-size: 8rem;
        text-align: center;
        animation: bounce 0.6s infinite alternate;
    }

    @keyframes bounce {
        from { transform: translateY(0px) rotate(-5deg); }
        to   { transform: translateY(-15px) rotate(5deg); }
    }

    .dice-static {
        font-size: 6rem;
        text-align: center;
    }

    .score-badge {
        background: linear-gradient(135deg, #FFD700, #FFA500);
        color: #1a1a2e;
        font-family: 'Fredoka One', cursive;
        font-size: 1.4rem;
        padding: 0.4rem 1.2rem;
        border-radius: 50px;
        display: inline-block;
        font-weight: bold;
    }

    .player-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: rgba(255,255,255,0.06);
        border-radius: 12px;
        padding: 0.7rem 1.2rem;
        margin-bottom: 0.5rem;
        border-left: 4px solid #7c3aed;
    }

    .player-row.top1 { border-left-color: #FFD700; background: rgba(255,215,0,0.1); }
    .player-row.top2 { border-left-color: #C0C0C0; background: rgba(192,192,192,0.08); }
    .player-row.top3 { border-left-color: #CD7F32; background: rgba(205,127,50,0.08); }

    .player-name { color: white; font-weight: 700; font-size: 1.1rem; }
    .player-score { color: #FFD700; font-family: 'Fredoka One', cursive; font-size: 1.2rem; }
    .rank-badge { font-size: 1.4rem; margin-right: 0.5rem; }

    .timer-bar-wrap {
        background: rgba(255,255,255,0.1);
        border-radius: 50px;
        height: 14px;
        margin: 1rem 0;
        overflow: hidden;
    }

    .status-pill {
        display: inline-block;
        padding: 0.3rem 1rem;
        border-radius: 50px;
        font-size: 0.85rem;
        font-weight: 700;
        margin-bottom: 1rem;
    }
    .pill-lobby    { background: #3b82f6; color: white; }
    .pill-question { background: #10b981; color: white; }
    .pill-result   { background: #f59e0b; color: white; }
    .pill-finished { background: #ef4444; color: white; }

    .answer-btn {
        width: 100%;
        padding: 1rem;
        border-radius: 14px;
        font-family: 'Nunito', sans-serif;
        font-size: 1.1rem;
        font-weight: 700;
        cursor: pointer;
        border: none;
        margin-bottom: 0.6rem;
        transition: transform 0.1s;
    }
    .answer-btn:hover { transform: scale(1.02); }

    .correct-answer { background: #10b981; color: white; }
    .wrong-answer   { background: #ef4444; color: white; }
    .neutral-answer { background: rgba(255,255,255,0.12); color: white; }

    .waiting-msg {
        text-align: center;
        color: #a78bfa;
        font-size: 1.2rem;
        font-weight: 600;
        padding: 2rem;
    }

    .stButton > button {
        background: linear-gradient(135deg, #7c3aed, #4f46e5);
        color: white;
        border: none;
        border-radius: 12px;
        font-family: 'Nunito', sans-serif;
        font-weight: 700;
        font-size: 1rem;
        padding: 0.7rem 2rem;
        width: 100%;
        transition: opacity 0.2s;
    }
    .stButton > button:hover { opacity: 0.85; }

    .stTextInput > div > div > input {
        background: rgba(255,255,255,0.1) !important;
        color: white !important;
        border: 1px solid rgba(255,255,255,0.2) !important;
        border-radius: 12px !important;
        font-family: 'Nunito', sans-serif !important;
        font-size: 1.1rem !important;
    }

    div[data-testid="stMetricValue"] {
        color: #FFD700 !important;
        font-family: 'Fredoka One', cursive !important;
    }

    .confetti { font-size: 2rem; }
    </style>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# HELPER: Timer progress bar
# ─────────────────────────────────────────────
def timer_bar(elapsed, total):
    pct = max(0, min(100, int((1 - elapsed/total) * 100)))
    color = "#10b981" if pct > 50 else "#f59e0b" if pct > 20 else "#ef4444"
    st.markdown(f"""
    <div class="timer-bar-wrap">
        <div style="height:100%; width:{pct}%; background:{color};
             border-radius:50px; transition: width 1s linear;"></div>
    </div>
    <p style="text-align:center; color:#a78bfa; font-size:0.9rem; margin-top:-0.5rem;">
        ⏱ {max(0, total - int(elapsed))} saniye kaldı
    </p>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# DICE FACE EMOJI
# ─────────────────────────────────────────────
DICE_FACES = {1:"⚀", 2:"⚁", 3:"⚂", 4:"⚃", 5:"⚄", 6:"⚅"}

def dice_emoji(n):
    """Map question number to a dice face (1-6, loop if needed)"""
    return DICE_FACES.get(((n - 1) % 6) + 1, "🎲")

# ─────────────────────────────────────────────
# HOST VIEW
# ─────────────────────────────────────────────
def host_view():
    st.markdown('<div class="big-title">🎲 Quiz Arena</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">HOST PANELİ</div>', unsafe_allow_html=True)

    status = get_state("status")
    current_q = int(get_state("current_question") or 0)
    question_start = float(get_state("question_start") or 0)

    players = get_players()

    # ── LOBBY ──────────────────────────────────
    if status == "lobby":
        st.markdown('<span class="status-pill pill-lobby">🟦 Lobi — Oyuncular katılıyor</span>', unsafe_allow_html=True)

        # ── QR + JOIN URL ──
        if "app_url" not in st.session_state:
            st.session_state.app_url = ""

        if not st.session_state.app_url:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("### 🔗 Uygulama URL'ini Girin")
            st.markdown("<p style='color:#a78bfa;'>Oyuncuların QR koduyla katılabilmesi için Streamlit Cloud URL'ini bir kez girin.</p>", unsafe_allow_html=True)
            url_input = st.text_input("", placeholder="https://xxx.streamlit.app", label_visibility="collapsed")
            if st.button("✅ URL'i Kaydet"):
                if url_input.strip().startswith("http"):
                    st.session_state.app_url = url_input.strip().rstrip("/")
                    st.rerun()
                else:
                    st.error("Geçerli bir URL girin (https:// ile başlamalı)")
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            join_url = st.session_state.app_url
            try:
                import qrcode, io, base64
                qr = qrcode.QRCode(version=2, box_size=7, border=3)
                qr.add_data(join_url)
                qr.make(fit=True)
                img = qr.make_image(fill_color="#1a1a2e", back_color="white")
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                qr_b64 = base64.b64encode(buf.getvalue()).decode()
                qr_html = f'<img src="data:image/png;base64,{qr_b64}" style="width:200px; border-radius:12px;"/>'
            except ImportError:
                qr_html = '<p style="color:#ef4444; font-size:0.9rem;">⚠️ requirements.txt'e <b>qrcode[pil]</b> ekle</p>'

            qcol, icol = st.columns([1, 2])
            with qcol:
                st.markdown(f"""
                <div class="card" style="text-align:center;">
                    <p style="color:#a78bfa; font-size:0.9rem; margin-bottom:0.5rem;">📱 QR Kodu Okut</p>
                    {qr_html}
                    <p style="color:#FFD700; font-family:'Fredoka One',cursive; font-size:0.85rem; margin-top:0.7rem; word-break:break-all;">{join_url}</p>
                </div>
                """, unsafe_allow_html=True)
            with icol:
                st.markdown("""
                <div class="card">
                    <h3 style="color:white;">📋 Nasıl Katılırım?</h3>
                    <ol style="color:#a78bfa; font-size:1rem; line-height:2.2rem;">
                        <li>Telefonunla QR kodu okut</li>
                        <li>Açılan sayfada adını yaz</li>
                        <li><b style="color:#FFD700;">Katıl!</b> butonuna bas</li>
                        <li>Host oyunu başlatınca sorular gelir</li>
                    </ol>
                    <p style="color:rgba(255,255,255,0.3); font-size:0.75rem;">Sidebar'dan mod değiştirmen gerekmez — link doğrudan oyuncu ekranını açar.</p>
                </div>
                """, unsafe_allow_html=True)
            if st.button("🔗 URL'i Değiştir"):
                st.session_state.app_url = ""
                st.rerun()

        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown(f"### 👥 Katılan Oyuncular ({len(players)})")
            if players:
                for name, score in players:
                    st.markdown(f"<div class='player-row'><span class='player-name'>👤 {name}</span></div>", unsafe_allow_html=True)
            else:
                st.markdown("<div class='waiting-msg'>Henüz kimse katılmadı…</div>", unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("### ⚙️ Kontroller")
            if len(players) >= 1:
                if st.button("🎲 Oyunu Başlat!"):
                    set_state("status", "rolling")
                    set_state("current_question", 1)
                    st.rerun()
            else:
                st.info("En az 1 oyuncu bekleniyor…")

            st.markdown("---")
            if st.button("🔄 Oyunu Sıfırla"):
                reset_game()
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        time.sleep(3)
        st.rerun()

    # ── ROLLING ────────────────────────────────
    elif status == "rolling":
        q_no = current_q
        st.markdown(f'<span class="status-pill pill-lobby">🎲 Soru {q_no} / {len(QUESTIONS)}</span>', unsafe_allow_html=True)

        col1, col2 = st.columns([1, 1])
        with col1:
            st.markdown('<div class="card" style="text-align:center">', unsafe_allow_html=True)
            st.markdown(f'<div class="dice-display">{dice_emoji(q_no)}</div>', unsafe_allow_html=True)
            st.markdown(f'<h2 style="color:white; font-family:Fredoka One;">Zar: <span style="color:#FFD700;">{q_no}</span></h2>', unsafe_allow_html=True)
            st.markdown(f'<p style="color:#a78bfa;">→ {q_no}. soruya geçiliyor</p>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            if st.button(f"▶️ {q_no}. Soruyu Göster"):
                set_state("status", "question")
                set_state("question_start", time.time())
                st.rerun()

        with col2:
            _leaderboard_widget(players)

    # ── QUESTION ───────────────────────────────
    elif status == "question":
        q = QUESTIONS.get(current_q)
        elapsed = time.time() - question_start

        st.markdown(f'<span class="status-pill pill-question">🟢 Soru {current_q} / {len(QUESTIONS)} — Cevaplanıyor</span>', unsafe_allow_html=True)

        col1, col2 = st.columns([3, 2])
        with col1:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown(f'<div class="dice-static">{dice_emoji(current_q)} {current_q}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="question-text">{q["q"]}</div>', unsafe_allow_html=True)

            timer_bar(elapsed, QUESTION_TIME)

            for i, opt in enumerate(q["options"]):
                labels = ["A", "B", "C", "D"]
                colors = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444"]
                st.markdown(f"""
                <div style="background:{colors[i]}22; border:2px solid {colors[i]};
                     border-radius:12px; padding:0.8rem 1.2rem; margin-bottom:0.5rem; color:white; font-size:1rem; font-weight:600;">
                    <b>{labels[i]})</b> {opt}
                </div>
                """, unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            answers_so_far = get_question_results(current_q)
            st.markdown(f'<div class="card"><h3 style="color:white;">📊 Cevaplar: {len(answers_so_far)} / {len(players)}</h3>', unsafe_allow_html=True)
            if answers_so_far:
                correct = sum(1 for r in answers_so_far if r[1])
                st.markdown(f'<p style="color:#10b981;">✅ Doğru: {correct}</p>', unsafe_allow_html=True)
                st.markdown(f'<p style="color:#ef4444;">❌ Yanlış: {len(answers_so_far)-correct}</p>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        # Auto-advance when time is up
        if elapsed >= QUESTION_TIME:
            set_state("status", "result")
            st.rerun()

        if st.button("⏭️ Süreyi Bitir & Sonucu Göster"):
            set_state("status", "result")
            st.rerun()

        time.sleep(2)
        st.rerun()

    # ── RESULT ─────────────────────────────────
    elif status == "result":
        q = QUESTIONS.get(current_q)
        results = get_question_results(current_q)
        correct_idx = q["answer"]

        st.markdown(f'<span class="status-pill pill-result">📊 Soru {current_q} Sonuçları</span>', unsafe_allow_html=True)

        col1, col2 = st.columns([3, 2])
        with col1:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown(f'<div class="question-text">{q["q"]}</div>', unsafe_allow_html=True)
            for i, opt in enumerate(q["options"]):
                labels = ["A", "B", "C", "D"]
                is_correct = (i == correct_idx)
                style = "background:#10b981; border:2px solid #10b981;" if is_correct else "background:rgba(255,255,255,0.05); border:2px solid rgba(255,255,255,0.1);"
                icon = "✅" if is_correct else ""
                st.markdown(f"""
                <div style="{style} border-radius:12px; padding:0.8rem 1.2rem; margin-bottom:0.5rem; color:white; font-size:1rem; font-weight:600;">
                    <b>{labels[i]})</b> {opt} {icon}
                </div>
                """, unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            # Top answerers
            if results:
                st.markdown('<div class="card"><h3 style="color:#FFD700;">🏆 Bu Sorunun Birincileri</h3>', unsafe_allow_html=True)
                for i, (pname, is_c, score_g, rms) in enumerate(results[:5]):
                    medal = ["🥇","🥈","🥉","4️⃣","5️⃣"][i]
                    color = "#10b981" if is_c else "#ef4444"
                    st.markdown(f"""
                    <div style="display:flex; justify-content:space-between; padding:0.5rem 0.8rem;
                         background:rgba(255,255,255,0.05); border-radius:10px; margin-bottom:0.4rem;">
                        <span style="color:white;">{medal} {pname}</span>
                        <span style="color:{color}; font-weight:700;">+{score_g} puan ({rms}ms)</span>
                    </div>
                    """, unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            players_updated = get_players()
            _leaderboard_widget(players_updated)

        # Next question or finish
        next_q = current_q + 1
        if next_q <= len(QUESTIONS):
            if st.button(f"🎲 Sonraki Soru ({next_q})"):
                set_state("current_question", next_q)
                set_state("status", "rolling")
                st.rerun()
        else:
            if st.button("🏁 Oyunu Bitir & Kazananı İlan Et!"):
                set_state("status", "finished")
                st.rerun()

    # ── FINISHED ───────────────────────────────
    elif status == "finished":
        st.markdown('<div class="big-title">🏆 OYUN BİTTİ!</div>', unsafe_allow_html=True)
        st.balloons()
        players_final = get_players()
        if players_final:
            winner = players_final[0]
            st.markdown(f"""
            <div style="text-align:center; padding:2rem;">
                <div style="font-size:5rem;">🥇</div>
                <div style="font-family:'Fredoka One',cursive; font-size:2.5rem; color:#FFD700;">{winner[0]}</div>
                <div style="color:white; font-size:1.4rem;">{winner[1]} puan ile kazandı!</div>
            </div>
            """, unsafe_allow_html=True)
        _leaderboard_widget(players_final, show_all=True)
        if st.button("🔄 Yeni Oyun Başlat"):
            reset_game()
            st.rerun()


def _leaderboard_widget(players, show_all=False):
    medals = ["🥇","🥈","🥉"]
    top_classes = ["top1","top2","top3"]
    limit = len(players) if show_all else 8
    st.markdown('<div class="card"><h3 style="color:white;">📊 Skor Tablosu</h3>', unsafe_allow_html=True)
    if not players:
        st.markdown('<div class="waiting-msg">Henüz skor yok</div>', unsafe_allow_html=True)
    for i, (name, score) in enumerate(players[:limit]):
        medal = medals[i] if i < 3 else f"{i+1}."
        cls = top_classes[i] if i < 3 else ""
        st.markdown(f"""
        <div class='player-row {cls}'>
            <span><span class='rank-badge'>{medal}</span><span class='player-name'>{name}</span></span>
            <span class='player-score'>{score}</span>
        </div>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────
# PLAYER VIEW
# ─────────────────────────────────────────────
def player_view():
    inject_css()

    # Session init
    if "player_name" not in st.session_state:
        st.session_state.player_name = ""
    if "joined" not in st.session_state:
        st.session_state.joined = False
    if "last_answer" not in st.session_state:
        st.session_state.last_answer = {}  # q_no -> (is_correct, score_gained)

    st.markdown('<div class="big-title">🎲 Quiz Arena</div>', unsafe_allow_html=True)

    # ── JOIN ────────────────────────────────────
    if not st.session_state.joined:
        st.markdown('<div class="subtitle">Oyuna katılmak için isminizi girin</div>', unsafe_allow_html=True)
        col = st.columns([1, 2, 1])[1]
        with col:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            name = st.text_input("", placeholder="Adınız…", label_visibility="collapsed")
            if st.button("🚀 Katıl!"):
                if name.strip():
                    ok = add_player(name.strip())
                    if ok:
                        st.session_state.player_name = name.strip()
                        st.session_state.joined = True
                        st.rerun()
                    else:
                        st.error("Bu isim zaten alınmış, başka bir isim deneyin.")
                else:
                    st.warning("Lütfen bir isim girin.")
            st.markdown('</div>', unsafe_allow_html=True)
        return

    # ── JOINED ──────────────────────────────────
    pname = st.session_state.player_name
    status = get_state("status")
    current_q = int(get_state("current_question") or 0)
    question_start = float(get_state("question_start") or 0)

    # Player score
    with get_conn() as conn:
        row = conn.execute("SELECT score FROM players WHERE name=?", (pname,)).fetchone()
        my_score = row[0] if row else 0

    st.markdown(f"""
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;">
        <span style="color:white; font-size:1.1rem;">👤 <b>{pname}</b></span>
        <span class="score-badge">⭐ {my_score} puan</span>
    </div>
    """, unsafe_allow_html=True)

    if status == "lobby":
        st.markdown('<div class="card"><div class="waiting-msg">⏳ Oyun başlaması bekleniyor…<br><br>Host oyunu başlatacak!</div></div>', unsafe_allow_html=True)
        time.sleep(3)
        st.rerun()

    elif status == "rolling":
        q_no = current_q
        st.markdown(f'<div class="card"><div style="text-align:center"><div class="dice-display">{dice_emoji(q_no)}</div><h2 style="color:#FFD700; font-family:Fredoka One;">Zar: {q_no}</h2><p style="color:#a78bfa;">{q_no}. soru geliyor, hazır ol!</p></div></div>', unsafe_allow_html=True)
        time.sleep(2)
        st.rerun()

    elif status == "question":
        q = QUESTIONS.get(current_q)
        elapsed = time.time() - question_start
        already = has_answered(pname, current_q)

        st.markdown(f'<div class="card"><div class="question-text">{q["q"]}</div>', unsafe_allow_html=True)
        timer_bar(elapsed, QUESTION_TIME)
        st.markdown('</div>', unsafe_allow_html=True)

        if already:
            last = st.session_state.last_answer.get(current_q)
            if last:
                if last[0]:
                    st.success(f"✅ Doğru! +{last[1]} puan kazandın!")
                else:
                    st.error("❌ Yanlış cevap.")
            else:
                st.info("✅ Cevabın kaydedildi!")
        else:
            labels = ["A", "B", "C", "D"]
            colors = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444"]
            cols = st.columns(2)
            for i, opt in enumerate(q["options"]):
                with cols[i % 2]:
                    if st.button(f"{labels[i]}) {opt}", key=f"ans_{current_q}_{i}"):
                        rms = int((time.time() - question_start) * 1000)
                        is_c, sg = submit_answer(pname, current_q, i, rms)
                        st.session_state.last_answer[current_q] = (is_c, sg)
                        st.rerun()

        time.sleep(2)
        st.rerun()

    elif status == "result":
        q = QUESTIONS.get(current_q)
        correct_idx = q["answer"]
        last = st.session_state.last_answer.get(current_q)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f'<div class="question-text">{q["q"]}</div>', unsafe_allow_html=True)
        for i, opt in enumerate(q["options"]):
            labels = ["A", "B", "C", "D"]
            is_correct = (i == correct_idx)
            style = "background:#10b981; border:2px solid #10b981;" if is_correct else "background:rgba(255,255,255,0.05); border:2px solid rgba(255,255,255,0.1);"
            icon = "✅" if is_correct else ""
            st.markdown(f"""
            <div style="{style} border-radius:12px; padding:0.8rem 1.2rem; margin-bottom:0.5rem; color:white; font-size:1rem; font-weight:600;">
                <b>{labels[i]})</b> {opt} {icon}
            </div>
            """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        if last:
            if last[0]:
                st.success(f"🎉 Bu soruda {last[1]} puan kazandın!")
            else:
                st.error("❌ Bu soruda puan kazanamadın.")

        st.markdown('<div class="waiting-msg">⏳ Sonraki soru için bekle…</div>', unsafe_allow_html=True)
        time.sleep(3)
        st.rerun()

    elif status == "finished":
        st.markdown('<div class="big-title">🏆 OYUN BİTTİ!</div>', unsafe_allow_html=True)
        players_final = get_players()
        _leaderboard_widget(players_final, show_all=True)


# ─────────────────────────────────────────────
# MAIN ROUTER
# ─────────────────────────────────────────────
def main():
    init_db()
    inject_css()

    # Query param routing (robust across Streamlit versions)
    try:
        params = st.query_params
        # Streamlit >= 1.30: params is a dict-like object
        if hasattr(params, "to_dict"):
            mode = params.to_dict().get("mode", "player")
        elif isinstance(params, dict):
            mode = params.get("mode", "player")
        else:
            mode = getattr(params, "mode", "player")
            if isinstance(mode, list):
                mode = mode[0]
    except Exception:
        mode = "player"

    # Sidebar override (fallback if URL params don't work)
    with st.sidebar:
        st.markdown("### 🎛️ Mod Seç")
        sidebar_mode = st.radio(
            "",
            ["👤 Oyuncu", "🖥️ Host"],
            index=1 if mode == "host" else 0,
            label_visibility="collapsed"
        )
        if sidebar_mode == "🖥️ Host":
            mode = "host"
        else:
            mode = "player"

        st.markdown("---")
        st.markdown("**Host URL:** `?mode=host`")
        st.markdown("**Oyuncu URL:** *(normal link)*")

    if mode == "host":
        host_view()
    else:
        player_view()

if __name__ == "__main__":
    main()
