import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime
import io
import warnings
import urllib.request
import json

warnings.filterwarnings('ignore')

st.set_page_config(page_title="النظام المالي المتكامل", page_icon="💎", layout="wide")

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
        try: c.execute("ALTER TABLE expenses ADD COLUMN wallet TEXT DEFAULT 'نقدي'")
        except: pass
        try: c.execute("ALTER TABLE income ADD COLUMN wallet TEXT DEFAULT 'نقدي'")
        except: pass
        c.close()
        conn.close()
    except: pass

init_db()

if not st.session_state["authenticated"]:
    st.title("🔒 نظام الدخول الآمن")
    with st.form("login_form"):
        username = st.text_input("اسم المستخدم")
        password = st.text_input("كلمة المرور", type="password")
        if st.form_submit_button("دخول"):
            is_admin = (username == st.secrets.get("APP_USERNAME") and password == st.secrets.get("APP_PASSWORD"))
            is_guest = (username == st.secrets.get("GUEST_USERNAME") and password == st.secrets.get("GUEST_PASSWORD"))
            
            if is_admin or is_guest:
                st.session_state.update({"authenticated": True, "role": "admin" if is_admin else "guest"})
                st.rerun()
            else:
                st.error("❌ بيانات الدخول غير صحيحة!")
    st.stop()

# ==========================================
#         البرنامج الرئيسي 
# ==========================================
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
        
        db_categories = df_exp['category'].unique().tolist() if not df_exp.empty and 'category' in df_exp.columns else []
        all_categories = sorted(list(set(default_categories + db_categories))) + ["➕ إضافة بند جديد..."]
except Exception as e:
    st.error("خطأ في الاتصال بقاعدة البيانات.")
    st.stop()

st.title("💎 النظام المالي المتكامل")

# ==========================================
#        إدارة العمليات (القائمة الجانبية)
# ==========================================
st.sidebar.title("إدارة الأموال 💼")

if st.session_state["role"] == "admin":
    operation = st.sidebar.selectbox("ماذا تريد أن تفعل؟", 
        ["💸 إضافة مصروف", "💵 إضافة رصيد", "🎯 تحديد ميزانية", "🤝 إضافة دين/سلفة", "🐷 هدف توفير"])
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
                st.sidebar.success("تم!")
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
                st.rerun()

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
else:
    st.sidebar.info("👁️ تتصفح كضيف (قراءة فقط).")

# ==========================================
#        المحفظة العامة والفلترة
# ==========================================
def get_balance(wallet_name):
    inc = df_inc[df_inc['wallet'] == wallet_name]['amount'].sum() if not df_inc.empty and 'wallet' in df_inc.columns else 0
    exp = df_exp[df_exp['wallet'] == wallet_name]['amount'].sum() if not df_exp.empty and 'wallet' in df_exp.columns else 0
    return inc - exp

total_bal_all = get_balance('نقدي') + get_balance('فيزا') + get_balance('فودافون كاش')

c1, c2, c3, c4 = st.columns(4)
c1.metric("💰 الرصيد الكلي", f"{total_bal_all:.2f} ج.م")
c2.metric("💵 كاش", f"{get_balance('نقدي'):.2f} ج.م")
c3.metric("💳 فيزا", f"{get_balance('فيزا'):.2f} ج.م")
c4.metric("📱 فودافون كاش", f"{get_balance('فودافون كاش'):.2f} ج.م")
st.markdown("---")

if not df_exp.empty and 'date' in df_exp.columns:
    df_exp['month_year'] = pd.to_datetime(df_exp['date']).dt.strftime('%Y-%m')
    months_list = ["كل الشهور"] + sorted(df_exp['month_year'].unique().tolist(), reverse=True)
else:
    months_list = ["كل الشهور"]

selected_month = st.selectbox("📅 فلترة البيانات حسب الشهر:", months_list)

df_exp_view = df_exp if selected_month == "كل الشهور" or df_exp.empty else df_exp[df_exp['month_year'] == selected_month]
total_exp_view = df_exp_view['amount'].sum() if not df_exp_view.empty and 'amount' in df_exp_view.columns else 0

# ==========================================
#                التابات
# ==========================================
if st.session_state["role"] == "admin":
    tabs = st.tabs(["📊 المصاريف والميزانية", "🤝 الديون والتوفير", "🤖 المستشار الذكي (Gemini)", "💵 الأرصدة"])
    tab_exp, tab_plan, tab_ai, tab_inc = tabs
else:
    tabs = st.tabs(["📊 المصاريف", "💵 الأرصدة"])
    tab_exp, tab_inc = tabs

with tab_exp:
    st.subheader(f"💸 إجمالي مصاريف ({selected_month}): {total_exp_view:.2f} ج.م")
    if not df_exp_view.empty:
        cat_group = df_exp_view.groupby('category')['amount'].sum().reset_index()
        st.bar_chart(cat_group.set_index('category'))
        st.dataframe(df_exp_view.drop(columns=['id', 'month_year'], errors='ignore'), use_container_width=True)

if st.session_state["role"] == "admin":
    with tab_plan:
        st.subheader("إدارة الديون والأهداف")
        st.dataframe(df_debts.drop(columns=['id'], errors='ignore'), use_container_width=True)
        st.dataframe(df_savings.drop(columns=['id'], errors='ignore'), use_container_width=True)

    with tab_ai:
        st.subheader("🤖 أنا المستشار الخوارزمي - اسألني عن مصاريفك!")
        
        cat_totals_dict = df_exp_view.groupby('category')['amount'].sum().to_dict() if not df_exp_view.empty else {}
        context_data = f"الرصيد: {total_bal_all} جنيه. المصاريف: {total_exp_view} جنيه. تفاصيل: {cat_totals_dict}"

        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []
            
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
                
        prompt = st.chat_input("اكتب سؤالك هنا.. (مثال: تنصحني أعمل إيه عشان أوفر 500 جنيه؟)")
        
        if prompt:
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.write(prompt)
                
            with st.chat_message("assistant"):
                try:
                    import google.generativeai as genai
                    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                    
                    # 🚀 السحر هنا: بحث تلقائي عن الموديل المتاح لحسابك
                    target_model = None
                    for m in genai.list_models():
                        if 'generateContent' in m.supported_generation_methods:
                            target_model = m.name
                            if 'flash' in m.name.lower(): # نفضل الفلاش عشان أسرع
                                break
                    
                    if target_model:
                        model = genai.GenerativeModel(target_model)
                        full_prompt = f"أنت مستشار مالي مصري. بيانات المستخدم: {context_data}. سؤال المستخدم: {prompt}"
                        response = model.generate_content(full_prompt)
                        reply = response.text
                        st.write(reply)
                        st.session_state.chat_history.append({"role": "assistant", "content": reply})
                    else:
                        st.error("لم أتمكن من العثور على أي نسخة ذكاء اصطناعي متاحة لمفتاحك.")
                        
                except Exception as e:
                    st.error(f"⚠️ تفاصيل الخطأ التقني: {repr(e)}")

with tab_inc:
    st.subheader("سجل الأرصدة المضافة")
    if not df_inc.empty:
        st.dataframe(df_inc.drop(columns=['id'], errors='ignore'), use_container_width=True)import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime
import io
import warnings
import urllib.request
import json

warnings.filterwarnings('ignore')

st.set_page_config(page_title="النظام المالي المتكامل", page_icon="💎", layout="wide")

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
        try: c.execute("ALTER TABLE expenses ADD COLUMN wallet TEXT DEFAULT 'نقدي'")
        except: pass
        try: c.execute("ALTER TABLE income ADD COLUMN wallet TEXT DEFAULT 'نقدي'")
        except: pass
        c.close()
        conn.close()
    except: pass

init_db()

if not st.session_state["authenticated"]:
    st.title("🔒 نظام الدخول الآمن")
    with st.form("login_form"):
        username = st.text_input("اسم المستخدم")
        password = st.text_input("كلمة المرور", type="password")
        if st.form_submit_button("دخول"):
            is_admin = (username == st.secrets.get("APP_USERNAME") and password == st.secrets.get("APP_PASSWORD"))
            is_guest = (username == st.secrets.get("GUEST_USERNAME") and password == st.secrets.get("GUEST_PASSWORD"))
            
            if is_admin or is_guest:
                st.session_state.update({"authenticated": True, "role": "admin" if is_admin else "guest"})
                st.rerun()
            else:
                st.error("❌ بيانات الدخول غير صحيحة!")
    st.stop()

# ==========================================
#         البرنامج الرئيسي 
# ==========================================
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
        
        db_categories = df_exp['category'].unique().tolist() if not df_exp.empty and 'category' in df_exp.columns else []
        all_categories = sorted(list(set(default_categories + db_categories))) + ["➕ إضافة بند جديد..."]
except Exception as e:
    st.error("خطأ في الاتصال بقاعدة البيانات.")
    st.stop()

st.title("💎 النظام المالي المتكامل")

# ==========================================
#        إدارة العمليات (القائمة الجانبية)
# ==========================================
st.sidebar.title("إدارة الأموال 💼")

if st.session_state["role"] == "admin":
    operation = st.sidebar.selectbox("ماذا تريد أن تفعل؟", 
        ["💸 إضافة مصروف", "💵 إضافة رصيد", "🎯 تحديد ميزانية", "🤝 إضافة دين/سلفة", "🐷 هدف توفير"])
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
                st.sidebar.success("تم!")
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
                st.rerun()

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
else:
    st.sidebar.info("👁️ تتصفح كضيف (قراءة فقط).")

# ==========================================
#        المحفظة العامة والفلترة
# ==========================================
def get_balance(wallet_name):
    inc = df_inc[df_inc['wallet'] == wallet_name]['amount'].sum() if not df_inc.empty and 'wallet' in df_inc.columns else 0
    exp = df_exp[df_exp['wallet'] == wallet_name]['amount'].sum() if not df_exp.empty and 'wallet' in df_exp.columns else 0
    return inc - exp

total_bal_all = get_balance('نقدي') + get_balance('فيزا') + get_balance('فودافون كاش')

c1, c2, c3, c4 = st.columns(4)
c1.metric("💰 الرصيد الكلي", f"{total_bal_all:.2f} ج.م")
c2.metric("💵 كاش", f"{get_balance('نقدي'):.2f} ج.م")
c3.metric("💳 فيزا", f"{get_balance('فيزا'):.2f} ج.م")
c4.metric("📱 فودافون كاش", f"{get_balance('فودافون كاش'):.2f} ج.م")
st.markdown("---")

if not df_exp.empty and 'date' in df_exp.columns:
    df_exp['month_year'] = pd.to_datetime(df_exp['date']).dt.strftime('%Y-%m')
    months_list = ["كل الشهور"] + sorted(df_exp['month_year'].unique().tolist(), reverse=True)
else:
    months_list = ["كل الشهور"]

selected_month = st.selectbox("📅 فلترة البيانات حسب الشهر:", months_list)

df_exp_view = df_exp if selected_month == "كل الشهور" or df_exp.empty else df_exp[df_exp['month_year'] == selected_month]
total_exp_view = df_exp_view['amount'].sum() if not df_exp_view.empty and 'amount' in df_exp_view.columns else 0

# ==========================================
#                التابات
# ==========================================
if st.session_state["role"] == "admin":
    tabs = st.tabs(["📊 المصاريف والميزانية", "🤝 الديون والتوفير", "🤖 المستشار الذكي (Gemini)", "💵 الأرصدة"])
    tab_exp, tab_plan, tab_ai, tab_inc = tabs
else:
    tabs = st.tabs(["📊 المصاريف", "💵 الأرصدة"])
    tab_exp, tab_inc = tabs

with tab_exp:
    st.subheader(f"💸 إجمالي مصاريف ({selected_month}): {total_exp_view:.2f} ج.م")
    if not df_exp_view.empty:
        cat_group = df_exp_view.groupby('category')['amount'].sum().reset_index()
        st.bar_chart(cat_group.set_index('category'))
        st.dataframe(df_exp_view.drop(columns=['id', 'month_year'], errors='ignore'), use_container_width=True)

if st.session_state["role"] == "admin":
    with tab_plan:
        st.subheader("إدارة الديون والأهداف")
        st.dataframe(df_debts.drop(columns=['id'], errors='ignore'), use_container_width=True)
        st.dataframe(df_savings.drop(columns=['id'], errors='ignore'), use_container_width=True)

    with tab_ai:
        st.subheader("🤖 أنا المستشار الخوارزمي (عقلي من Gemini) - اسألني عن مصاريفك!")
        
        cat_totals_dict = df_exp_view.groupby('category')['amount'].sum().to_dict() if not df_exp_view.empty else {}
        context_data = f"الرصيد: {total_bal_all} جنيه. المصاريف: {total_exp_view} جنيه. تفاصيل: {cat_totals_dict}"

        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []
            
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
                
        prompt = st.chat_input("اكتب سؤالك هنا.. (مثال: تنصحني أعمل إيه عشان أوفر 500 جنيه؟)")
        
        if prompt:
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.write(prompt)
                
            with st.chat_message("assistant"):
                try:
                    import google.generativeai as genai
                    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                    # قمنا بتغيير اسم الموديل لـ gemini-pro لضمان عمله على كل المفاتيح
                    model = genai.GenerativeModel('gemini-pro')
                    full_prompt = f"أنت مستشار مالي مصري. بيانات المستخدم: {context_data}. سؤال المستخدم: {prompt}"
                    response = model.generate_content(full_prompt)
                    reply = response.text
                    st.write(reply)
                    st.session_state.chat_history.append({"role": "assistant", "content": reply})
                except Exception as e:
                    st.error(f"⚠️ تفاصيل الخطأ التقني (انسخ هذا الكلام): {repr(e)}")

with tab_inc:
    st.subheader("سجل الأرصدة المضافة")
    if not df_inc.empty:
        st.dataframe(df_inc.drop(columns=['id'], errors='ignore'), use_container_width=True)
