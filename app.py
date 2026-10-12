import streamlit as st
import pandas as pd
import altair as alt
import psycopg2
from datetime import datetime
from html import escape
import io
import warnings
import urllib.request
import json

warnings.filterwarnings('ignore')

st.set_page_config(page_title="النظام المالي المتكامل", page_icon="💎", layout="wide")

# ==========================================
#          الثيم (داكن / فاتح)
# ==========================================
DARK = dict(bg="#0B0D17", surface="#141829", surface2="#1B2038", line="#262C4A",
            text="#E8EAF6", muted="#8D94B8", accent="#7C5CFF", accent2="#22D3EE",
            ok="#34D399", warn="#FBBF24", bad="#FB7185", shadow="0 10px 30px rgba(0,0,0,.40)")
LIGHT = dict(bg="#F4F3FB", surface="#FFFFFF", surface2="#EEECF9", line="#E1DEF2",
             text="#1B1740", muted="#6A6791", accent="#6A47F5", accent2="#0891B2",
             ok="#059669", warn="#D97706", bad="#E11D48", shadow="0 8px 24px rgba(40,30,100,.08)")

st.session_state.setdefault("dark_mode", True)
T = DARK if st.session_state["dark_mode"] else LIGHT
CHART_COLORS = ["#7C5CFF", "#22D3EE", "#34D399", "#FBBF24", "#FB7185", "#A78BFA", "#38BDF8", "#F97316"]

THEME_VARS = (
    ":root{"
    f"--bg:{T['bg']};--surface:{T['surface']};--surface2:{T['surface2']};--line:{T['line']};"
    f"--text:{T['text']};--muted:{T['muted']};--accent:{T['accent']};--accent2:{T['accent2']};"
    f"--ok:{T['ok']};--warn:{T['warn']};--bad:{T['bad']};--shadow:{T['shadow']};"
    "}"
)

STATIC_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Readex+Pro:wght@300;400;500;600;700&display=swap');

/* الخط والاتجاه */
.stApp, .stApp p, .stApp label, .stApp input, .stApp textarea, .stApp button,
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp li,
[data-testid="stMarkdownContainer"], [data-testid="stMetricValue"], [data-testid="stMetricLabel"]{
    font-family:'Readex Pro', sans-serif !important;
}
.stApp{ background:var(--bg); }
.stApp p, .stApp label, .stApp li, [data-testid="stMarkdownContainer"], .stApp h1, .stApp h2, .stApp h3, .stApp h4{ color:var(--text); }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p{ color:var(--muted) !important; }
[data-testid="stMain"], [data-testid="stSidebar"]{ direction:rtl; text-align:right; }
[data-testid="stHeader"]{ background:transparent; }
[data-testid="stHeader"] *{ color:var(--muted); }
#MainMenu, footer{ visibility:hidden; }
.block-container{ padding-top:2rem; padding-bottom:3rem; max-width:1180px; }
h1{ font-weight:600 !important; }
h2, h3{ font-weight:500 !important; }
hr{ border-color:var(--line) !important; }

/* الشريط الجانبي */
[data-testid="stSidebar"]{ background:var(--surface); border-left:1px solid var(--line); }
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3{ font-size:1.1rem; }

/* الحقول */
.stTextInput input, .stNumberInput input, .stDateInput input, .stTextArea textarea,
div[data-baseweb="select"] > div, div[data-baseweb="input"], div[data-baseweb="base-input"]{
    background:var(--surface2) !important;
    border-color:var(--line) !important;
    border-radius:12px !important;
    color:var(--text) !important;
}
.stTextInput input:focus, .stNumberInput input:focus, .stDateInput input:focus{
    box-shadow:0 0 0 3px color-mix(in srgb, var(--accent) 30%, transparent) !important;
}
div[data-baseweb="select"] *{ color:var(--text) !important; }
.stNumberInput button{ background:var(--surface2) !important; color:var(--text) !important; border-color:var(--line) !important; }
span[data-baseweb="tag"]{ background:var(--accent) !important; color:#fff !important; border-radius:8px; }
span[data-baseweb="tag"] *{ color:#fff !important; }
div[data-baseweb="popover"] > div, div[data-baseweb="popover"] ul, div[data-baseweb="menu"], div[data-baseweb="calendar"]{
    background:var(--surface2) !important; color:var(--text) !important; border-radius:12px;
}
div[data-baseweb="popover"] li, div[data-baseweb="calendar"] *{ color:var(--text) !important; }
div[data-baseweb="popover"] li:hover{ background:var(--line) !important; }
[data-testid="stCheckbox"] span, [data-testid="stRadio"] label p{ color:var(--text) !important; }

/* الأزرار */
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button{
    background:linear-gradient(135deg, var(--accent), color-mix(in srgb, var(--accent) 70%, var(--accent2)));
    color:#fff !important;
    border:none;
    border-radius:12px;
    padding:.55rem 1.1rem;
    font-weight:500;
    transition:filter .15s ease, transform .1s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover{ filter:brightness(1.1); color:#fff; }
.stButton > button:active, .stDownloadButton > button:active{ transform:scale(.98); }
.stButton > button:focus-visible, .stDownloadButton > button:focus-visible{ outline:3px solid var(--accent2); outline-offset:2px; }

/* التابات (أقراص) */
.stTabs [data-baseweb="tab-list"]{ gap:.4rem; background:var(--surface); border:1px solid var(--line); border-radius:999px; padding:.3rem; width:fit-content; max-width:100%; overflow-x:auto; }
.stTabs [data-baseweb="tab"]{ border-radius:999px; padding:.45rem 1.1rem; color:var(--muted); height:auto; }
.stTabs [data-baseweb="tab"] p{ color:inherit !important; font-weight:500; }
.stTabs [aria-selected="true"]{ background:var(--accent); color:#fff; }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"]{ display:none; }

/* المؤشرات */
[data-testid="stMetric"]{ background:var(--surface); border:1px solid var(--line); border-radius:16px; padding:1rem 1.25rem; box-shadow:var(--shadow); }
[data-testid="stMetricLabel"] p{ color:var(--muted) !important; font-weight:400; }
[data-testid="stMetricValue"]{ font-weight:600; font-size:1.6rem; color:var(--text); }

/* التنبيهات والنماذج والشات */
[data-testid="stAlert"]{ background:var(--surface2) !important; border:1px solid var(--line); border-radius:14px; }
[data-testid="stAlert"] *{ color:var(--text) !important; }
[data-testid="stForm"]{ background:var(--surface); border:1px solid var(--line); border-radius:18px; padding:1.5rem; box-shadow:var(--shadow); }
[data-testid="stChatMessage"]{ background:var(--surface); border:1px solid var(--line); border-radius:16px; }
[data-testid="stChatInput"], [data-testid="stChatInput"] textarea{ background:var(--surface2) !important; color:var(--text) !important; border-radius:14px; }

/* الإجمالي وبطاقات المحافظ */
.total{ display:flex; align-items:baseline; gap:1rem; flex-wrap:wrap; margin:.25rem 0 1rem; }
.total .t-label{ color:var(--muted); font-size:.95rem; }
.total .t-amt{ font-size:3rem; font-weight:600; letter-spacing:-0.02em; line-height:1.1; color:var(--text); }
.total .t-amt small{ font-size:1.05rem; font-weight:400; color:var(--muted); margin-right:.4rem; }
.total .t-amt.neg{ color:var(--bad); }
.wallet-row{ display:grid; grid-template-columns:repeat(3, 1fr); gap:1rem; margin-bottom:1.5rem; }
.wcard{ position:relative; border-radius:20px; padding:1.1rem 1.3rem 1.3rem; color:#fff; min-height:132px; overflow:hidden; box-shadow:var(--shadow); }
.wcard::before{ content:""; position:absolute; width:180px; height:180px; border-radius:50%; background:rgba(255,255,255,.10); left:-50px; top:-70px; }
.wcard .wc-top{ display:flex; justify-content:space-between; align-items:center; font-weight:500; position:relative; }
.wcard .chip{ width:34px; height:24px; border-radius:6px; background:linear-gradient(135deg,#F5D98B,#C9A24B); opacity:.9; }
.wcard .wc-amt{ position:relative; margin-top:1.6rem; font-size:1.65rem; font-weight:600; letter-spacing:-0.01em; }
.wcard .wc-amt small{ font-size:.85rem; font-weight:400; opacity:.8; margin-right:.3rem; }
.w-cash{ background:linear-gradient(135deg,#10B981,#0E7490); }
.w-visa{ background:linear-gradient(135deg,#7C5CFF,#4338CA); }
.w-voda{ background:linear-gradient(135deg,#EF4444,#9F1239); }

/* ترتيب الأقسام */
.rank{ background:var(--surface); border:1px solid var(--line); border-radius:16px; padding:.4rem 1.1rem; }
.rank-row{ padding:.75rem 0; border-top:1px solid var(--line); }
.rank-row:first-child{ border-top:none; }
.rank-head{ display:flex; justify-content:space-between; font-size:.95rem; margin-bottom:.45rem; }
.rank-head .r-val{ color:var(--muted); font-variant-numeric:tabular-nums; }
.bar-track{ height:7px; background:var(--surface2); border-radius:99px; overflow:hidden; }
.bar-fill{ height:100%; border-radius:99px; }
.bar-fill.ok{ background:var(--ok); } .bar-fill.warn{ background:var(--warn); } .bar-fill.bad{ background:var(--bad); }

/* الجداول (متوافقة مع الوضعين) */
.tbl-wrap{ max-height:460px; overflow:auto; border:1px solid var(--line); border-radius:16px; background:var(--surface); }
.tbl{ width:100%; border-collapse:collapse; font-size:.92rem; }
.tbl th{ position:sticky; top:0; background:var(--surface2); color:var(--muted); font-weight:500; text-align:right; padding:.7rem .95rem; white-space:nowrap; }
.tbl td{ padding:.65rem .95rem; border-top:1px solid var(--line); color:var(--text); white-space:nowrap; }
.tbl td.num{ font-variant-numeric:tabular-nums; font-weight:500; }
.tbl tr:hover td{ background:var(--surface2); }
.tbl-empty{ color:var(--muted); padding:1.2rem; text-align:center; }

@media (max-width:760px){
    .wallet-row{ grid-template-columns:1fr; }
    .total .t-amt{ font-size:2.2rem; }
}
"""
st.markdown(f"<style>{THEME_VARS}{STATIC_CSS}</style>", unsafe_allow_html=True)

# ---------- أدوات العرض ----------
HEADERS = {"date": "التاريخ", "category": "القسم", "amount": "المبلغ", "description": "الوصف",
           "wallet": "المحفظة", "person": "الشخص", "type": "النوع", "goal_name": "الهدف",
           "target": "المطلوب", "saved": "المدخّر", "from_wallet": "من", "to_wallet": "إلى",
           "timestamp": "الوقت", "username": "المستخدم", "ip_address": "IP",
           "device_info": "الجهاز", "location": "الموقع"}
NUM_COLS = {"amount", "target", "saved"}

def render_table(df, max_rows=300):
    df = df.drop(columns=['id', 'month_year'], errors='ignore')
    if df.empty:
        st.markdown('<div class="tbl-wrap"><div class="tbl-empty">لا توجد بيانات لعرضها.</div></div>', unsafe_allow_html=True)
        return
    df = df.head(max_rows)
    head = "".join(f"<th>{escape(HEADERS.get(c, c))}</th>" for c in df.columns)
    rows = ""
    for _, r in df.iterrows():
        cells = ""
        for c in df.columns:
            v = r[c]
            if pd.isna(v):
                txt, cls = "", ""
            elif c in NUM_COLS:
                txt, cls = f"{float(v):,.2f}", "num"
            else:
                txt, cls = escape(str(v)), ""
            cells += f'<td class="{cls}">{txt}</td>'
        rows += f"<tr>{cells}</tr>"
    st.markdown(f'<div class="tbl-wrap"><table class="tbl"><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>', unsafe_allow_html=True)

def style_chart(chart, height):
    return (chart.properties(height=height)
            .configure(background="transparent")
            .configure_view(strokeWidth=0)
            .configure_axis(labelColor=T['muted'], titleColor=T['muted'], gridColor=T['line'],
                            domainColor=T['line'], tickColor=T['line'], labelFontSize=12)
            .configure_legend(labelColor=T['text'], titleColor=T['muted'], labelFontSize=12))

# ==========================================
#             نظام الأمان والاتصال
# ==========================================
if "authenticated" not in st.session_state:
    st.session_state.update({"authenticated": False, "role": None})

def logout():
    st.session_state.update({"authenticated": False, "role": None})

def get_connection():
    return psycopg2.connect(st.secrets["DATABASE_URL"])

def init_db():
    try:
        conn = get_connection()
        conn.autocommit = True
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS access_logs (id SERIAL PRIMARY KEY, timestamp TEXT, username TEXT, ip_address TEXT, device_info TEXT, location TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS expenses (id SERIAL PRIMARY KEY, date TEXT, category TEXT, amount REAL, description TEXT, wallet TEXT DEFAULT 'نقدي')''')
        c.execute('''CREATE TABLE IF NOT EXISTS income (id SERIAL PRIMARY KEY, date TEXT, amount REAL, description TEXT, wallet TEXT DEFAULT 'نقدي')''')
        c.execute('''CREATE TABLE IF NOT EXISTS budgets (category TEXT UNIQUE, limit_amount REAL)''')
        c.execute('''CREATE TABLE IF NOT EXISTS debts (id SERIAL PRIMARY KEY, date TEXT, person TEXT, amount REAL, type TEXT, description TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS savings (id SERIAL PRIMARY KEY, goal_name TEXT, target REAL, saved REAL)''')
        c.execute('''CREATE TABLE IF NOT EXISTS transfers (id SERIAL PRIMARY KEY, date TEXT, from_wallet TEXT, to_wallet TEXT, amount REAL)''')
        try: c.execute("ALTER TABLE expenses ADD COLUMN wallet TEXT DEFAULT 'نقدي'")
        except: pass
        try: c.execute("ALTER TABLE income ADD COLUMN wallet TEXT DEFAULT 'نقدي'")
        except: pass
        c.close()
        conn.close()
    except: pass

init_db()

if not st.session_state["authenticated"]:
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown("<div style='height:7vh'></div>", unsafe_allow_html=True)
        st.title("💎 تسجيل الدخول")
        st.caption("ادخل ببياناتك لمتابعة محافظك ومصاريفك.")
        with st.form("login_form"):
            username = st.text_input("اسم المستخدم")
            password = st.text_input("كلمة المرور", type="password")
            submitted = st.form_submit_button("دخول", use_container_width=True)
        st.toggle("🌙 الوضع الداكن", key="dark_mode")
        if submitted:
            is_admin = (username == st.secrets.get("APP_USERNAME") and password == st.secrets.get("APP_PASSWORD"))
            is_guest = (username == st.secrets.get("GUEST_USERNAME") and password == st.secrets.get("GUEST_PASSWORD"))

            if is_admin or is_guest:
                st.session_state.update({"authenticated": True, "role": "admin" if is_admin else "guest"})
                try:
                    headers = st.context.headers
                    ip = headers.get("X-Forwarded-For", "غير متوفر").split(",")[0].strip()
                    user_agent = headers.get("User-Agent", "غير متوفر")
                    location = "غير متوفر"
                    if ip != "غير متوفر":
                        try:
                            req = urllib.request.Request(f"http://ip-api.com/json/{ip}", headers={'User-Agent': 'Mozilla/5.0'})
                            with urllib.request.urlopen(req, timeout=3) as response:
                                data = json.loads(response.read().decode())
                                if data.get("status") == "success": location = f"{data.get('country', '')} - {data.get('city', '')}"
                        except: pass
                    with get_connection() as log_conn:
                        log_conn.autocommit = True
                        with log_conn.cursor() as log_c:
                            log_c.execute("INSERT INTO access_logs (timestamp, username, ip_address, device_info, location) VALUES (%s, %s, %s, %s, %s)",
                                          (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), username, ip, user_agent, location))
                except: pass
                st.rerun()
            else:
                st.error("اسم المستخدم أو كلمة المرور غير صحيحة. راجع البيانات وحاول مرة تانية.")
    st.stop()

# ==========================================
#         البرنامج الرئيسي
# ==========================================
st.sidebar.toggle("🌙 الوضع الداكن", key="dark_mode")
st.sidebar.button("تسجيل الخروج 🚪", on_click=logout, use_container_width=True)
st.sidebar.markdown("---")

wallets = ["نقدي", "فيزا", "فودافون كاش"]
default_categories = ["طعام ومشروبات", "مواصلات", "فواتير واشتراكات", "استثمارات", "كورسات وتعليم", "ترفيه", "أخرى"]

def safe_read_sql(query, conn):
    try: return pd.read_sql(query, conn)
    except: return pd.DataFrame()

try:
    with get_connection() as read_conn:
        df_exp = safe_read_sql("SELECT * FROM expenses ORDER BY date DESC, id DESC", read_conn)
        df_inc = safe_read_sql("SELECT * FROM income ORDER BY date DESC, id DESC", read_conn)
        df_budgets = safe_read_sql("SELECT * FROM budgets", read_conn)
        df_debts = safe_read_sql("SELECT * FROM debts ORDER BY date DESC", read_conn)
        df_savings = safe_read_sql("SELECT * FROM savings", read_conn)
        df_logs = safe_read_sql("SELECT * FROM access_logs ORDER BY id DESC LIMIT 50", read_conn)
        df_transfers = safe_read_sql("SELECT * FROM transfers ORDER BY date DESC, id DESC", read_conn)

        db_categories = df_exp['category'].unique().tolist() if not df_exp.empty and 'category' in df_exp.columns else []
        all_categories = sorted(list(set(default_categories + db_categories))) + ["➕ إضافة بند جديد..."]
except Exception as e:
    st.error("تعذّر الاتصال بقاعدة البيانات. تأكد من رابط DATABASE_URL في الإعدادات وحاول تاني.")
    st.stop()

st.title("💎 النظام المالي المتكامل")

# ==========================================
#        إدارة العمليات (القائمة الجانبية)
# ==========================================
st.sidebar.title("إدارة الأموال 💼")

if st.session_state["role"] == "admin":
    operation = st.sidebar.selectbox("ماذا تريد أن تفعل؟",
        ["💸 إضافة مصروف", "💵 إضافة رصيد", "🔄 تحويل بين المحافظ", "🎯 تحديد ميزانية", "🤝 إضافة دين/سلفة", "🐷 هدف توفير", "✏️ تعديل وحذف"])
    st.sidebar.markdown("---")

    if operation == "💸 إضافة مصروف":
        date_input = st.sidebar.date_input("التاريخ", datetime.today())
        cat_sel = st.sidebar.selectbox("القسم", all_categories)
        category_input = st.sidebar.text_input("اسم البند الجديد") if cat_sel == "➕ إضافة بند جديد..." else cat_sel
        wallet_out = st.sidebar.selectbox("خصم من", wallets)
        amount_input = st.sidebar.number_input("المبلغ", min_value=0.0, format="%.2f")
        desc_input = st.sidebar.text_input("الوصف (اختياري)")
        if st.sidebar.button("حفظ المصروف ✅", use_container_width=True):
            if amount_input > 0 and category_input.strip() != "":
                with get_connection() as conn:
                    conn.autocommit = True
                    with conn.cursor() as c:
                        c.execute("INSERT INTO expenses (date, category, amount, description, wallet) VALUES (%s, %s, %s, %s, %s)",
                                  (date_input.strftime("%Y-%m-%d"), category_input.strip(), amount_input, desc_input, wallet_out))
                st.sidebar.success("تم الحفظ!")
                st.rerun()

    elif operation == "💵 إضافة رصيد":
        inc_date = st.sidebar.date_input("التاريخ", datetime.today())
        wallet_in = st.sidebar.selectbox("إضافة إلى", wallets)
        inc_amt = st.sidebar.number_input("المبلغ", min_value=0.0, format="%.2f")
        inc_desc = st.sidebar.text_input("مصدر الرصيد")
        if st.sidebar.button("إضافة رصيد ✅", use_container_width=True):
            if inc_amt > 0:
                with get_connection() as conn:
                    conn.autocommit = True
                    with conn.cursor() as c:
                        c.execute("INSERT INTO income (date, amount, description, wallet) VALUES (%s, %s, %s, %s)",
                                  (inc_date.strftime("%Y-%m-%d"), inc_amt, inc_desc, wallet_in))
                st.sidebar.success("تم إضافة الرصيد!")
                st.rerun()

    elif operation == "🔄 تحويل بين المحافظ":
        t_date = st.sidebar.date_input("التاريخ", datetime.today())
        wallet_from = st.sidebar.selectbox("من محفظة (تُخصم منها)", wallets, index=0)
        wallet_to = st.sidebar.selectbox("إلى محفظة (تُضاف إليها)", wallets, index=1)
        t_amount = st.sidebar.number_input("المبلغ المحول", min_value=0.0, format="%.2f")

        if st.sidebar.button("تنفيذ التحويل ✅", use_container_width=True):
            if t_amount > 0 and wallet_from != wallet_to:
                with get_connection() as conn:
                    conn.autocommit = True
                    with conn.cursor() as c:
                        c.execute("INSERT INTO transfers (date, from_wallet, to_wallet, amount) VALUES (%s, %s, %s, %s)",
                                  (t_date.strftime("%Y-%m-%d"), wallet_from, wallet_to, t_amount))
                st.sidebar.success("تم نقل الرصيد بنجاح!")
                st.rerun()
            elif wallet_from == wallet_to:
                st.sidebar.error("⚠️ لا يمكن التحويل لنفس المحفظة!")

    elif operation == "🎯 تحديد ميزانية":
        budg_cat = st.sidebar.selectbox("اختر البند", [c for c in all_categories if c != "➕ إضافة بند جديد..."])
        budg_limit = st.sidebar.number_input("الحد الأقصى (ج.م)", min_value=0.0, format="%.2f")
        if st.sidebar.button("حفظ الميزانية ✅", use_container_width=True):
            with get_connection() as conn:
                conn.autocommit = True
                with conn.cursor() as c:
                    c.execute("INSERT INTO budgets (category, limit_amount) VALUES (%s, %s) ON CONFLICT (category) DO UPDATE SET limit_amount = EXCLUDED.limit_amount", (budg_cat, budg_limit))
            st.rerun()

    elif operation == "🤝 إضافة دين/سلفة":
        d_date = st.sidebar.date_input("التاريخ", datetime.today())
        d_type = st.sidebar.radio("نوع الدين", ["ليا (سلّفت حد)", "عليا (استلفت)"])
        d_person = st.sidebar.text_input("اسم الشخص")
        d_amount = st.sidebar.number_input("المبلغ", min_value=0.0, format="%.2f")
        d_desc = st.sidebar.text_input("التفاصيل")
        if st.sidebar.button("حفظ الدين ✅", use_container_width=True):
            if d_amount > 0 and d_person:
                with get_connection() as conn:
                    conn.autocommit = True
                    with conn.cursor() as c:
                        c.execute("INSERT INTO debts (date, person, amount, type, description) VALUES (%s, %s, %s, %s, %s)",
                                  (d_date.strftime("%Y-%m-%d"), d_person, d_amount, d_type, d_desc))
                st.rerun()

    elif operation == "🐷 هدف توفير":
        s_name = st.sidebar.text_input("اسم الهدف")
        s_target = st.sidebar.number_input("المبلغ المطلوب للهدف", min_value=0.0)
        s_saved = st.sidebar.number_input("معاك منه كام حالياً؟", min_value=0.0)
        if st.sidebar.button("إنشاء الهدف ✅", use_container_width=True):
            if s_target > 0 and s_name:
                with get_connection() as conn:
                    conn.autocommit = True
                    with conn.cursor() as c:
                        c.execute("INSERT INTO savings (goal_name, target, saved) VALUES (%s, %s, %s)", (s_name, s_target, s_saved))
                st.rerun()

    elif operation == "✏️ تعديل وحذف":
        edit_action = st.sidebar.radio("اختر العملية:", ["تعديل مصروف", "تعديل رصيد", "حذف مصروف", "حذف رصيد", "حذف تحويل"])

        if edit_action == "تعديل مصروف" and not df_exp.empty:
            exp_id = st.sidebar.selectbox("اختر المصروف للتعديل:", df_exp['id'].tolist(), format_func=lambda x: f"{df_exp[df_exp['id']==x]['amount'].iloc[0]} ج - {df_exp[df_exp['id']==x]['category'].iloc[0]}")
            selected_exp = df_exp[df_exp['id'] == exp_id].iloc[0]
            with st.sidebar.form("edit_exp_form"):
                n_date = st.date_input("التاريخ", pd.to_datetime(selected_exp['date']))
                n_cat = st.selectbox("القسم", all_categories[:-1], index=all_categories[:-1].index(selected_exp['category']) if selected_exp['category'] in all_categories[:-1] else 0)
                n_wallet = st.selectbox("المحفظة", wallets, index=wallets.index(selected_exp['wallet']) if selected_exp['wallet'] in wallets else 0)
                n_amount = st.number_input("المبلغ", min_value=0.0, value=float(selected_exp['amount']))
                n_desc = st.text_input("الوصف", value=str(selected_exp['description'] if pd.notna(selected_exp['description']) else ""))
                if st.form_submit_button("حفظ التعديلات 💾", use_container_width=True):
                    with get_connection() as conn:
                        conn.autocommit = True
                        with conn.cursor() as c:
                            c.execute("UPDATE expenses SET date=%s, category=%s, amount=%s, description=%s, wallet=%s WHERE id=%s", (n_date.strftime("%Y-%m-%d"), n_cat, n_amount, n_desc, n_wallet, exp_id))
                    st.rerun()

        elif edit_action == "تعديل رصيد" and not df_inc.empty:
            inc_id = st.sidebar.selectbox("اختر الرصيد للتعديل:", df_inc['id'].tolist(), format_func=lambda x: f"{df_inc[df_inc['id']==x]['amount'].iloc[0]} ج - {df_inc[df_inc['id']==x]['description'].iloc[0]}")
            selected_inc = df_inc[df_inc['id'] == inc_id].iloc[0]
            with st.sidebar.form("edit_inc_form"):
                n_date = st.date_input("التاريخ", pd.to_datetime(selected_inc['date']))
                n_wallet = st.selectbox("المحفظة", wallets, index=wallets.index(selected_inc['wallet']) if selected_inc['wallet'] in wallets else 0)
                n_amount = st.number_input("المبلغ", min_value=0.0, value=float(selected_inc['amount']))
                n_desc = st.text_input("الوصف", value=str(selected_inc['description'] if pd.notna(selected_inc['description']) else ""))
                if st.form_submit_button("حفظ التعديلات 💾", use_container_width=True):
                    with get_connection() as conn:
                        conn.autocommit = True
                        with conn.cursor() as c:
                            c.execute("UPDATE income SET date=%s, amount=%s, description=%s, wallet=%s WHERE id=%s", (n_date.strftime("%Y-%m-%d"), n_amount, n_desc, n_wallet, inc_id))
                    st.rerun()

        elif edit_action == "حذف مصروف" and not df_exp.empty:
            del_id = st.sidebar.selectbox("اختر المصروف للإلغاء:", df_exp['id'].tolist(), format_func=lambda x: f"{df_exp[df_exp['id']==x]['amount'].iloc[0]} ج - {df_exp[df_exp['id']==x]['category'].iloc[0]}")
            if st.sidebar.button("🗑️ حذف المصروف نهائياً", use_container_width=True):
                with get_connection() as conn:
                    conn.autocommit = True
                    with conn.cursor() as c: c.execute("DELETE FROM expenses WHERE id=%s", (del_id,))
                st.rerun()

        elif edit_action == "حذف رصيد" and not df_inc.empty:
            del_id = st.sidebar.selectbox("اختر الرصيد للإلغاء:", df_inc['id'].tolist(), format_func=lambda x: f"{df_inc[df_inc['id']==x]['amount'].iloc[0]} ج - {df_inc[df_inc['id']==x]['description'].iloc[0]}")
            if st.sidebar.button("🗑️ حذف الرصيد نهائياً", use_container_width=True):
                with get_connection() as conn:
                    conn.autocommit = True
                    with conn.cursor() as c: c.execute("DELETE FROM income WHERE id=%s", (del_id,))
                st.rerun()

        elif edit_action == "حذف تحويل" and not df_transfers.empty:
            del_id = st.sidebar.selectbox("اختر التحويل للإلغاء:", df_transfers['id'].tolist(), format_func=lambda x: f"{df_transfers[df_transfers['id']==x]['amount'].iloc[0]} ج (من {df_transfers[df_transfers['id']==x]['from_wallet'].iloc[0]} لـ {df_transfers[df_transfers['id']==x]['to_wallet'].iloc[0]})")
            if st.sidebar.button("🗑️ حذف التحويل", use_container_width=True):
                with get_connection() as conn:
                    conn.autocommit = True
                    with conn.cursor() as c: c.execute("DELETE FROM transfers WHERE id=%s", (del_id,))
                st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ إعدادات حساب المتوسط")
    excluded_categories = st.sidebar.multiselect("اختر البنود اللي مش عايزها تتحسب في المتوسط اليومي:", all_categories[:-1])

else:
    st.sidebar.info("👁️ تتصفح كضيف (قراءة فقط).")

# ==========================================
#        المحفظة العامة والفلترة
# ==========================================
def get_balance(wallet_name):
    inc = df_inc[df_inc['wallet'] == wallet_name]['amount'].sum() if not df_inc.empty and 'wallet' in df_inc.columns else 0
    exp = df_exp[df_exp['wallet'] == wallet_name]['amount'].sum() if not df_exp.empty and 'wallet' in df_exp.columns else 0
    trans_out = df_transfers[df_transfers['from_wallet'] == wallet_name]['amount'].sum() if not df_transfers.empty else 0
    trans_in = df_transfers[df_transfers['to_wallet'] == wallet_name]['amount'].sum() if not df_transfers.empty else 0
    return inc - exp + trans_in - trans_out

bal_cash = get_balance('نقدي')
bal_visa = get_balance('فيزا')
bal_voda = get_balance('فودافون كاش')
total_bal_all = bal_cash + bal_visa + bal_voda

def wcard(cls, label, icon, val):
    return (f'<div class="wcard {cls}"><div class="wc-top"><span>{icon} {label}</span><span class="chip"></span></div>'
            f'<div class="wc-amt">{val:,.2f}<small>ج.م</small></div></div>')

st.markdown(
    f'<div class="total"><span class="t-label">إجمالي رصيدك</span>'
    f'<span class="t-amt {"neg" if total_bal_all < 0 else ""}">{total_bal_all:,.2f}<small>ج.م</small></span></div>'
    f'<div class="wallet-row">'
    f'{wcard("w-cash", "كاش", "💵", bal_cash)}'
    f'{wcard("w-visa", "فيزا", "💳", bal_visa)}'
    f'{wcard("w-voda", "فودافون كاش", "📱", bal_voda)}'
    f'</div>',
    unsafe_allow_html=True
)

if not df_exp.empty and 'date' in df_exp.columns:
    df_exp['month_year'] = pd.to_datetime(df_exp['date']).dt.strftime('%Y-%m')
    months_list = ["كل الشهور"] + sorted(df_exp['month_year'].unique().tolist(), reverse=True)
else:
    months_list = ["كل الشهور"]

selected_month = st.selectbox("📅 فلترة البيانات حسب الشهر:", months_list)

df_exp_view = df_exp if selected_month == "كل الشهور" or df_exp.empty else df_exp[df_exp['month_year'] == selected_month]
total_exp_view = df_exp_view['amount'].sum() if not df_exp_view.empty and 'amount' in df_exp_view.columns else 0

if not df_exp_view.empty and 'category' in df_exp_view.columns:
    if "excluded_categories" in locals() and excluded_categories:
        df_daily_exp = df_exp_view[~df_exp_view['category'].isin(excluded_categories)]
    else:
        df_daily_exp = df_exp_view
    total_daily_exp = df_daily_exp['amount'].sum() if not df_daily_exp.empty else 0
    unique_days = df_daily_exp['date'].nunique() if not df_daily_exp.empty else 0
    avg_per_day = total_daily_exp / unique_days if unique_days > 0 else 0
else:
    avg_per_day = 0

# ==========================================
#                التابات
# ==========================================
if st.session_state["role"] == "admin":
    tabs = st.tabs(["📊 المصاريف والميزانية", "🤝 الديون والتوفير", "🤖 المستشار الذكي", "💵 الأرصدة والتحويلات", "🛡️ سجل الزيارات"])
    tab_exp, tab_plan, tab_ai, tab_inc, tab_sec = tabs
else:
    tabs = st.tabs(["📊 المصاريف", "💵 الأرصدة"])
    tab_exp, tab_inc = tabs

with tab_exp:
    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
    c_m1, c_m2 = st.columns(2)
    c_m1.metric(f"💸 إجمالي مصاريف ({selected_month})", f"{total_exp_view:,.2f} ج.م")
    c_m2.metric("📊 متوسط الصرف اليومي المخصص", f"{avg_per_day:,.2f} ج.م")

    if not df_exp_view.empty:
        cat_group = df_exp_view.groupby('category')['amount'].sum().reset_index().sort_values('amount', ascending=False)
        daily = (df_exp_view.assign(d=pd.to_datetime(df_exp_view['date']))
                 .groupby('d')['amount'].sum().reset_index().sort_values('d'))

        st.markdown("<div style='height:.75rem'></div>", unsafe_allow_html=True)
        col_a, col_b = st.columns([3, 2])

        with col_a:
            st.subheader("الصرف اليومي")
            area = alt.Chart(daily).mark_area(
                interpolate='monotone',
                line=alt.OverlayMarkDef(color=T['accent'], strokeWidth=2.5),
                point=alt.OverlayMarkDef(color=T['accent'], size=45),
                color=alt.Gradient(
                    gradient='linear',
                    stops=[alt.GradientStop(color=T['accent'] + "88", offset=0),
                           alt.GradientStop(color=T['accent'] + "00", offset=1)],
                    x1=1, x2=1, y1=0, y2=1)
            ).encode(
                x=alt.X('d:T', title=None, axis=alt.Axis(format='%m/%d', grid=False)),
                y=alt.Y('amount:Q', title=None, axis=alt.Axis(domain=False, ticks=False)),
                tooltip=[alt.Tooltip('d:T', title='اليوم', format='%Y-%m-%d'),
                         alt.Tooltip('amount:Q', title='المبلغ', format=',.2f')]
            )
            st.altair_chart(style_chart(area, 300), use_container_width=True)

        with col_b:
            st.subheader("توزيع المصاريف")
            donut = alt.Chart(cat_group).mark_arc(innerRadius=66, outerRadius=108, stroke=T['bg'], strokeWidth=2).encode(
                theta=alt.Theta('amount:Q'),
                color=alt.Color('category:N', scale=alt.Scale(range=CHART_COLORS),
                                legend=alt.Legend(title=None, orient="bottom")),
                tooltip=[alt.Tooltip('category:N', title='القسم'), alt.Tooltip('amount:Q', title='المبلغ', format=',.2f')]
            )
            st.altair_chart(style_chart(donut, 300), use_container_width=True)

        # ترتيب الأقسام
        st.subheader("الأقسام الأعلى صرفاً")
        top = float(cat_group['amount'].max()) or 1.0
        rank_rows = ""
        for i, r in enumerate(cat_group.itertuples()):
            color = CHART_COLORS[i % len(CHART_COLORS)]
            share = r.amount / total_exp_view * 100 if total_exp_view else 0
            rank_rows += (
                f'<div class="rank-row"><div class="rank-head"><span>{escape(str(r.category))}</span>'
                f'<span class="r-val">{r.amount:,.2f} ج.م · {share:.0f}%</span></div>'
                f'<div class="bar-track"><div class="bar-fill" style="width:{r.amount / top * 100:.0f}%;background:{color}"></div></div></div>'
            )
        st.markdown(f'<div class="rank">{rank_rows}</div>', unsafe_allow_html=True)

        # تقدّم الميزانيات
        if not df_budgets.empty and 'limit_amount' in df_budgets.columns:
            spent_map = cat_group.set_index('category')['amount'].to_dict()
            budget_rows = ""
            for _, b in df_budgets.iterrows():
                limit = float(b['limit_amount'] or 0)
                if limit <= 0:
                    continue
                spent = float(spent_map.get(b['category'], 0))
                pct = spent / limit * 100
                cls = "bad" if pct >= 100 else ("warn" if pct >= 80 else "ok")
                budget_rows += (
                    f'<div class="rank-row"><div class="rank-head"><span>{escape(str(b["category"]))}</span>'
                    f'<span class="r-val">{spent:,.0f} / {limit:,.0f} ج.م ({pct:.0f}%)</span></div>'
                    f'<div class="bar-track"><div class="bar-fill {cls}" style="width:{min(pct, 100):.0f}%"></div></div></div>'
                )
            if budget_rows:
                st.subheader("الميزانيات")
                st.markdown(f'<div class="rank">{budget_rows}</div>', unsafe_allow_html=True)

        st.subheader("سجل المصاريف")
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_exp_view.drop(columns=['month_year', 'id'], errors='ignore').to_excel(writer, sheet_name='المصاريف', index=False)
        st.download_button(label="📥 تحميل المصاريف (شيت إكسيل)", data=buffer.getvalue(), file_name=f"expenses_{selected_month}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
        render_table(df_exp_view)
    else:
        st.info("مفيش مصاريف في الفترة دي. أضف أول مصروف من القائمة الجانبية.")

if st.session_state["role"] == "admin":
    with tab_plan:
        st.subheader("الديون")
        render_table(df_debts)
        st.subheader("أهداف التوفير")
        render_table(df_savings)

    with tab_ai:
        st.subheader("🤖 المستشار الخوارزمي - اسألني عن مصاريفك!")
        cat_totals_dict = df_exp_view.groupby('category')['amount'].sum().to_dict() if not df_exp_view.empty else {}
        context_data = f"الرصيد الكلي: {total_bal_all} جنيه. مصاريف الشهر: {total_exp_view} جنيه. تفاصيل الأقسام: {cat_totals_dict}"

        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        prompt = st.chat_input("اكتب سؤالك هنا..")
        if prompt:
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            with st.chat_message("user"): st.write(prompt)
            with st.chat_message("assistant"):
                try:
                    import google.generativeai as genai
                    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                    model = genai.GenerativeModel('gemini-3.8-flash')
                    response = model.generate_content(f"أنت مستشار مالي مصري. بيانات المستخدم: {context_data}. سؤال: {prompt}")
                    st.write(response.text)
                    st.session_state.chat_history.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.error(f"⚠️ تفاصيل الخطأ التقني: {repr(e)}")

    with tab_sec:
        st.subheader("🛡️ سجل الزيارات والأمان")
        if not df_logs.empty:
            render_table(df_logs)
        else:
            st.info("لا توجد زيارات مسجلة حتى الآن.")

with tab_inc:
    st.subheader("سجل الأرصدة المضافة")
    if not df_inc.empty:
        render_table(df_inc)
    else:
        st.info("لم تضف أي رصيد بعد.")

    st.markdown("---")
    st.subheader("🔄 سجل التحويلات بين المحافظ")
    if not df_transfers.empty:
        render_table(df_transfers)
    else:
        st.info("لا توجد عمليات تحويل مسجلة حتى الآن.")
