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
        # جدول التحويلات الجديد
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
    st.title("🔒 نظام الدخول الآمن")
    with st.form("login_form"):
        username = st.text_input("اسم المستخدم")
        password = st.text_input("كلمة المرور", type="password")
        if st.form_submit_button("دخول"):
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
        df_logs = safe_read_sql("SELECT * FROM access_logs ORDER BY id DESC LIMIT 50", read_conn)
        df_transfers = safe_read_sql("SELECT * FROM transfers ORDER BY date DESC, id DESC", read_conn) # قراءة التحويلات
        
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

    # الميزة الجديدة: التحويل بين المحافظ
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
                
        # إلغاء تحويل
        elif edit_action == "حذف تحويل" and not df_transfers.empty:
            del_id = st.sidebar.selectbox("اختر التحويل للإلغاء:", df_transfers['id'].tolist(), format_func=lambda x: f"{df_transfers[df_transfers['id']==x]['amount'].iloc[0]} ج (من {df_transfers[df_transfers['id']==x]['from_wallet'].iloc[0]} لـ {df_transfers[df_transfers['id']==x]['to_wallet'].iloc[0]})")
            if st.sidebar.button("🗑️ حذف التحويل", use_container_width=True):
                with get_connection() as conn:
                    conn.autocommit = True
                    with conn.cursor() as c: c.execute("DELETE FROM transfers WHERE id=%s", (del_id,))
                st.rerun()

    # --- التحكم في حساب المتوسط ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ إعدادات حساب المتوسط")
    excluded_categories = st.sidebar.multiselect("اختر البنود اللي مش عايزها تتحسب في المتوسط اليومي:", all_categories[:-1])

else:
    st.sidebar.info("👁️ تتصفح كضيف (قراءة فقط).")

# ==========================================
#        المحفظة العامة والفلترة (تم التحديث للتحويلات)
# ==========================================
def get_balance(wallet_name):
    # حساب الرصيد المضاف
    inc = df_inc[df_inc['wallet'] == wallet_name]['amount'].sum() if not df_inc.empty and 'wallet' in df_inc.columns else 0
    # حساب المصاريف المخصومة
    exp = df_exp[df_exp['wallet'] == wallet_name]['amount'].sum() if not df_exp.empty and 'wallet' in df_exp.columns else 0
    
    # حساب التحويلات (طرح اللي طالع من المحفظة، وجمع اللي داخل ليها)
    trans_out = df_transfers[df_transfers['from_wallet'] == wallet_name]['amount'].sum() if not df_transfers.empty else 0
    trans_in = df_transfers[df_transfers['to_wallet'] == wallet_name]['amount'].sum() if not df_transfers.empty else 0
    
    return inc - exp + trans_in - trans_out

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

# حساب المتوسط بناءً على اختيارك
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
    c_m1, c_m2 = st.columns(2)
    c_m1.metric(f"💸 إجمالي مصاريف ({selected_month})", f"{total_exp_view:.2f} ج.م")
    c_m2.metric("📊 متوسط الصرف اليومي المخصص", f"{avg_per_day:.2f} ج.م")
    
    if not df_exp_view.empty:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_exp_view.drop(columns=['month_year', 'id'], errors='ignore').to_excel(writer, sheet_name='المصاريف', index=False)
        st.download_button(label="📥 تحميل المصاريف (شيت إكسيل)", data=buffer.getvalue(), file_name=f"expenses_{selected_month}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.markdown("---")
        
        cat_group = df_exp_view.groupby('category')['amount'].sum().reset_index()
        st.bar_chart(cat_group.set_index('category'))
        st.dataframe(df_exp_view.drop(columns=['id', 'month_year'], errors='ignore'), use_container_width=True)

if st.session_state["role"] == "admin":
    with tab_plan:
        st.subheader("إدارة الديون والأهداف")
        st.dataframe(df_debts.drop(columns=['id'], errors='ignore'), use_container_width=True)
        st.dataframe(df_savings.drop(columns=['id'], errors='ignore'), use_container_width=True)

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
            st.dataframe(df_logs.drop(columns=['id'], errors='ignore'), use_container_width=True)
        else:
            st.info("لا توجد زيارات مسجلة حتى الآن.")

with tab_inc:
    st.subheader("سجل الأرصدة المضافة")
    if not df_inc.empty:
        st.dataframe(df_inc.drop(columns=['id', 'month_year'], errors='ignore'), use_container_width=True)
    
    # عرض سجل التحويلات الجديد
    st.markdown("---")
    st.subheader("🔄 سجل التحويلات بين المحافظ")
    if not df_transfers.empty:
        st.dataframe(df_transfers.drop(columns=['id'], errors='ignore'), use_container_width=True)
    else:
        st.info("لا توجد عمليات تحويل مسجلة حتى الآن.")
