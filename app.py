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
#             نظام الأمان
# ==========================================
if "authenticated" not in st.session_state:
    st.session_state.update({"authenticated": False, "role": None})

def logout():
    st.session_state.update({"authenticated": False, "role": None})

def get_connection():
    return psycopg2.connect(st.secrets["DATABASE_URL"])

# تأمين إنشاء الجداول (لو جدول فشل ميوقفش الباقي)
try:
    with get_connection() as setup_conn:
        setup_conn.autocommit = True
        with setup_conn.cursor() as c:
            try: c.execute('''CREATE TABLE IF NOT EXISTS access_logs (id SERIAL PRIMARY KEY, timestamp TEXT, username TEXT, ip_address TEXT, device_info TEXT, location TEXT)''')
            except: pass
            
            try: c.execute('''CREATE TABLE IF NOT EXISTS expenses (id SERIAL PRIMARY KEY, date TEXT, category TEXT, amount REAL, description TEXT, wallet TEXT DEFAULT 'نقدي')''')
            except: pass
            try: c.execute("ALTER TABLE expenses ADD COLUMN wallet TEXT DEFAULT 'نقدي'")
            except: pass
            
            try: c.execute('''CREATE TABLE IF NOT EXISTS income (id SERIAL PRIMARY KEY, date TEXT, amount REAL, description TEXT, wallet TEXT DEFAULT 'نقدي')''')
            except: pass
            try: c.execute("ALTER TABLE income ADD COLUMN wallet TEXT DEFAULT 'نقدي'")
            except: pass
            
            try: c.execute('''CREATE TABLE IF NOT EXISTS budgets (category TEXT UNIQUE, limit_amount REAL)''')
            except: pass
            
            try: c.execute('''CREATE TABLE IF NOT EXISTS debts (id SERIAL PRIMARY KEY, date TEXT, person TEXT, amount REAL, type TEXT, description TEXT)''')
            except: pass
            
            try: c.execute('''CREATE TABLE IF NOT EXISTS savings (id SERIAL PRIMARY KEY, goal_name TEXT, target REAL, saved REAL)''')
            except: pass
except:
    pass

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

# دالة آمنة لجلب البيانات (عشان لو جدول مش موجود البرنامج ميقفلش)
def safe_read_sql(query, conn):
    try:
        return pd.read_sql(query, conn)
    except:
        return pd.DataFrame()

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
    st.error(f"خطأ رئيسي في الاتصال بقاعدة البيانات: {e}")
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
        st.sidebar.write("حدد حد أقصى للصرف في بند معين بالشهر:")
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
        s_name = st.sidebar.text_input("اسم الهدف (مثال: كورس CCNA)")
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
#        المحفظة العامة (لا تتأثر بالفلتر)
# ==========================================
def get_balance(wallet_name):
    inc = df_inc[df_inc['wallet'] == wallet_name]['amount'].sum() if not df_inc.empty and 'wallet' in df_inc.columns else 0
    exp = df_exp[df_exp['wallet'] == wallet_name]['amount'].sum() if not df_exp.empty and 'wallet' in df_exp.columns else 0
    return inc - exp

c1, c2, c3, c4 = st.columns(4)
c1.metric("💰 الرصيد الكلي", f"{get_balance('نقدي') + get_balance('فيزا') + get_balance('فودافون كاش'):.2f} ج.م")
c2.metric("💵 كاش", f"{get_balance('نقدي'):.2f} ج.م")
c3.metric("💳 فيزا", f"{get_balance('فيزا'):.2f} ج.م")
c4.metric("📱 فودافون كاش", f"{get_balance('فودافون كاش'):.2f} ج.م")
st.markdown("---")

# ==========================================
#        فلتر الشهور (يؤثر على الإحصائيات)
# ==========================================
if not df_exp.empty and 'date' in df_exp.columns:
    df_exp['month_year'] = pd.to_datetime(df_exp['date']).dt.strftime('%Y-%m')
    months_list = ["كل الشهور"] + sorted(df_exp['month_year'].unique().tolist(), reverse=True)
else:
    months_list = ["كل الشهور"]

selected_month = st.selectbox("📅 فلترة البيانات حسب الشهر:", months_list)

df_exp_view = df_exp if selected_month == "كل الشهور" or df_exp.empty else df_exp[df_exp['month_year'] == selected_month]
df_inc_view = df_inc.copy()
if not df_inc.empty and selected_month != "كل الشهور" and 'date' in df_inc.columns:
    df_inc_view['month_year'] = pd.to_datetime(df_inc['date']).dt.strftime('%Y-%m')
    df_inc_view = df_inc_view[df_inc_view['month_year'] == selected_month]

total_exp_view = df_exp_view['amount'].sum() if not df_exp_view.empty and 'amount' in df_exp_view.columns else 0
unique_days = df_exp_view['date'].nunique() if not df_exp_view.empty and 'date' in df_exp_view.columns else 0
avg_per_day = total_exp_view / unique_days if unique_days > 0 else 0

# ==========================================
#                التابات
# ==========================================
if st.session_state["role"] == "admin":
    tabs = st.tabs(["📊 المصاريف والميزانية", "🤝 الديون والتوفير", "🤖 المستشار المالي", "💵 الأرصدة", "🛡️ الأمان"])
    tab_exp, tab_plan, tab_ai, tab_inc, tab_sec = tabs
else:
    tabs = st.tabs(["📊 المصاريف والميزانية", "🤝 الديون والتوفير", "💵 الأرصدة"])
    tab_exp, tab_plan, tab_inc = tabs

# ----------------- تاب المصاريف -----------------
with tab_exp:
    c_m1, c_m2 = st.columns(2)
    c_m1.metric(f"💸 مصاريف ({selected_month})", f"{total_exp_view:.2f} ج.م")
    c_m2.metric("📊 متوسط الصرف اليومي", f"{avg_per_day:.2f} ج.م")
    
    if not df_exp_view.empty:
        cat_group = df_exp_view.groupby('category')['amount'].sum().reset_index()
        
        # نظام التحذير والميزانية
        if not df_budgets.empty and 'category' in df_budgets.columns:
            st.subheader("🎯 موقفك من الميزانية المحددة")
            for _, b_row in df_budgets.iterrows():
                b_cat = b_row['category']
                b_limit = b_row['limit_amount']
                spent = cat_group[cat_group['category'] == b_cat]['amount'].sum() if b_cat in cat_group['category'].values else 0
                progress = min(spent / b_limit, 1.0) if b_limit > 0 else 0
                
                st.write(f"**{b_cat}**: صرفت {spent:.2f} من أصل {b_limit:.2f}")
                st.progress(progress)
                if progress == 1.0: st.error(f"⚠️ لقد تجاوزت ميزانية {b_cat}!")
        
        st.markdown("---")
        st.subheader("تحليل البنود")
        st.bar_chart(cat_group.set_index('category'))
        st.dataframe(df_exp_view.drop(columns=['id', 'month_year'], errors='ignore'), use_container_width=True)

# ----------------- تاب التخطيط (ديون وتوفير) -----------------
with tab_plan:
    col_d, col_s = st.columns(2)
    with col_d:
        st.subheader("🤝 سجل السُلف والديون")
        if not df_debts.empty and 'type' in df_debts.columns:
            ليا = df_debts[df_debts['type'] == 'ليا (سلّفت حد)']['amount'].sum()
            عليا = df_debts[df_debts['type'] == 'عليا (استلفت)']['amount'].sum()
            st.info(f"🟢 ليك بره: {ليا:.2f} ج.م  |  🔴 عليك: {عليا:.2f} ج.م")
            st.dataframe(df_debts.drop(columns=['id'], errors='ignore'), use_container_width=True)
            
            if st.session_state["role"] == "admin" and 'id' in df_debts.columns:
                d_del = st.selectbox("حذف دين (بعد سداده):", df_debts['id'].tolist(), format_func=lambda x: f"{df_debts[df_debts['id']==x]['person'].iloc[0]} - {df_debts[df_debts['id']==x]['amount'].iloc[0]} ج.م")
                if st.button("تأكيد السداد/الحذف 🗑️", key="del_debt"):
                    with get_connection() as cnn:
                        cnn.autocommit=True
                        with cnn.cursor() as c: c.execute("DELETE FROM debts WHERE id=%s", (d_del,))
                    st.rerun()
        else:
            st.write("مفيش ديون مسجلة.")
            
    with col_s:
        st.subheader("🐷 أهداف التوفير")
        if not df_savings.empty and 'target' in df_savings.columns:
            for _, s_row in df_savings.iterrows():
                prog = min(s_row['saved'] / s_row['target'], 1.0) if s_row['target'] > 0 else 0
                st.write(f"🎯 **{s_row['goal_name']}**: تم توفير {s_row['saved']} من {s_row['target']}")
                st.progress(prog)
            
            if st.session_state["role"] == "admin" and 'id' in df_savings.columns:
                st.markdown("---")
                s_upd_id = st.selectbox("تحديث رصيد هدف:", df_savings['id'].tolist(), format_func=lambda x: df_savings[df_savings['id']==x]['goal_name'].iloc[0])
                s_add = st.number_input("إضافة مبلغ للهدف", min_value=0.0)
                if st.button("إضافة للحصالة 💰"):
                    with get_connection() as cnn:
                        cnn.autocommit=True
                        with cnn.cursor() as c: c.execute("UPDATE savings SET saved = saved + %s WHERE id = %s", (s_add, s_upd_id))
                    st.rerun()
        else:
            st.write("مفيش أهداف توفير حالياً.")

# ----------------- تاب المستشار الذكي -----------------
if st.session_state["role"] == "admin":
    with tab_ai:
        st.subheader("🤖 المستشار المالي الذكي (Khawarizmi AI)")
        st.write(f"تحليل لبيانات شهر: **{selected_month}**")
        
        if df_exp_view.empty:
            st.warning("مفيش مصاريف كافية في الشهر ده عشان أحللها يا هندسة. ضيف بيانات وارجعلي!")
        else:
            cat_totals = df_exp_view.groupby('category')['amount'].sum().sort_values(ascending=False)
            top_cat = cat_totals.index[0]
            top_amt = cat_totals.iloc[0]
            pct = (top_amt / total_exp_view) * 100 if total_exp_view > 0 else 0
            
            st.info(f"💡 **أكبر ثقب أسود لفلوسك:** بند '{top_cat}' أخد لوحده {top_amt:.2f} ج.م (بيمثل {pct:.1f}% من مصاريفك!).")
            
            current_day = datetime.today().day
            if selected_month == datetime.today().strftime('%Y-%m') and current_day > 5:
                expected = avg_per_day * 30
                st.warning(f"📈 **التوقع الشهري:** بمعدل صرفك الحالي ({avg_per_day:.2f} ج/يوم)، متوقع تقفل الشهر ده بمصاريف حوالي **{expected:.2f} ج.م**. لو الرقم ده أكبر من دخلك، فرمل نفسك من دلوقتي!")
            
            if not df_budgets.empty:
                st.success("🎯 ممتاز إنك حاطط حدود للميزانية (Budgets). دي أفضل طريقة تحكم بيها مصاريفك كمدير مالي شاطر.")
                
            st.write("---")
            st.markdown("✨ *نصيحة اليوم:* التوفير مش معناه إنك تحرم نفسك، معناه إنك تصرف بذكاء في الحاجات اللي بتسعدك بجد، وتقطع المصاريف العشوائية اللي ملهاش لازمة.")

# ----------------- تاب الأرصدة -----------------
with tab_inc:
    st.subheader("سجل الأرصدة المضافة")
    if not df_inc.empty:
        st.dataframe(df_inc_view.drop(columns=['id', 'month_year'], errors='ignore'), use_container_width=True)

# ----------------- تاب الأمان -----------------
if st.session_state["role"] == "admin":
    with tab_sec:
        st.subheader("🛡️ سجل زيارات النظام")
        try:
            with get_connection() as cnn:
                df_logs = pd.read_sql("SELECT * FROM access_logs ORDER BY id DESC LIMIT 50", cnn)
            if not df_logs.empty: st.dataframe(df_logs.drop(columns=['id'], errors='ignore'), use_container_width=True)
            else: st.info("لا توجد زيارات مسجلة.")
        except: pass
