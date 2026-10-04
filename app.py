import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime
import io
import warnings
import urllib.request
import json

warnings.filterwarnings('ignore')

st.set_page_config(page_title="متتبع المصاريف", page_icon="💰", layout="wide")

# ==========================================
#             نظام تسجيل الدخول والأمان
# ==========================================
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
    st.session_state["role"] = None

def logout():
    st.session_state["authenticated"] = False
    st.session_state["role"] = None

def get_connection():
    return psycopg2.connect(st.secrets["DATABASE_URL"])

# إنشاء جدول المراقبة (سجل الزيارات) لو مش موجود
try:
    with get_connection() as setup_conn:
        setup_conn.autocommit = True
        with setup_conn.cursor() as setup_c:
            setup_c.execute('''CREATE TABLE IF NOT EXISTS access_logs
                             (id SERIAL PRIMARY KEY, timestamp TEXT, username TEXT, ip_address TEXT, device_info TEXT, location TEXT)''')
except:
    pass

if not st.session_state["authenticated"]:
    st.title("🔒 نظام الدخول الآمن")
    st.markdown("يرجى إدخال بيانات الاعتماد.")
    
    with st.form("login_form"):
        username = st.text_input("اسم المستخدم")
        password = st.text_input("كلمة المرور", type="password")
        submit = st.form_submit_button("دخول")
        
        if submit:
            is_admin = (username == st.secrets.get("APP_USERNAME") and password == st.secrets.get("APP_PASSWORD"))
            is_guest = (username == st.secrets.get("GUEST_USERNAME") and password == st.secrets.get("GUEST_PASSWORD"))
            
            if is_admin or is_guest:
                st.session_state["authenticated"] = True
                st.session_state["role"] = "admin" if is_admin else "guest"
                
                # --- نظام التتبع وتسجيل بيانات الزائر ---
                try:
                    headers = st.context.headers
                    ip = headers.get("X-Forwarded-For", "غير معروف").split(",")[0].strip()
                    user_agent = headers.get("User-Agent", "جهاز غير معروف")
                    location = "غير معروف"
                    
                    if ip != "غير معروف":
                        try:
                            # جلب الموقع الجغرافي للـ IP
                            url = f"http://ip-api.com/json/{ip}"
                            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                            with urllib.request.urlopen(req, timeout=3) as response:
                                data = json.loads(response.read().decode())
                                if data.get("status") == "success":
                                    location = f"{data.get('country', '')} - {data.get('city', '')}"
                        except:
                            pass
                            
                    # حفظ بيانات الزيارة في قاعدة البيانات
                    with get_connection() as log_conn:
                        log_conn.autocommit = True
                        with log_conn.cursor() as log_c:
                            log_c.execute("INSERT INTO access_logs (timestamp, username, ip_address, device_info, location) VALUES (%s, %s, %s, %s, %s)",
                                          (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), username, ip, user_agent, location))
                except Exception as e:
                    pass # تجاهل الأخطاء لعدم إزعاج المستخدم

                st.rerun()
            else:
                st.error("❌ بيانات الدخول غير صحيحة!")
    st.stop()

# ==========================================
#         البرنامج الرئيسي (بعد الدخول)
# ==========================================
st.sidebar.button("تسجيل الخروج 🚪", on_click=logout, use_container_width=True)
st.sidebar.markdown("---")

wallets = ["نقدي", "فيزا", "فودافون كاش"]

try:
    conn = get_connection()
    conn.autocommit = True
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS expenses
                 (date TEXT, category TEXT, amount REAL, description TEXT)''')
    try: c.execute("ALTER TABLE expenses ADD COLUMN id SERIAL PRIMARY KEY")
    except: pass 
    try: c.execute("ALTER TABLE expenses ADD COLUMN wallet TEXT DEFAULT 'نقدي'")
    except: pass 

    c.execute('''CREATE TABLE IF NOT EXISTS income
                 (id SERIAL PRIMARY KEY, date TEXT, amount REAL, description TEXT)''')
    try: c.execute("ALTER TABLE income ADD COLUMN wallet TEXT DEFAULT 'نقدي'")
    except: pass 

except Exception as e:
    st.error(f"خطأ في الاتصال بقاعدة البيانات: {e}")
    st.stop()

st.title("💰 متتبع المصاريف الشخصية")

# ==========================================
#        القائمة الجانبية (للأدمن فقط)
# ==========================================
st.sidebar.title("إدارة الأموال 💼")

if st.session_state["role"] == "admin":
    tab_sidebar_exp, tab_sidebar_inc = st.sidebar.tabs(["إضافة مصروف 💸", "إضافة رصيد 💵"])

    with tab_sidebar_exp:
        categories = ["طعام ومشروبات", "مواصلات", "فواتير واشتراكات", "استثمارات", "كورسات وتعليم", "ترفيه", "أخرى"]
        date_input = st.date_input("التاريخ", datetime.today(), key="exp_date")
        category_input = st.selectbox("القسم (البند)", categories, key="exp_cat")
        wallet_out = st.selectbox("طريقة الدفع (خصم من)", wallets, key="exp_wal")
        amount_input = st.number_input("المبلغ", min_value=0.0, format="%.2f", key="exp_amt")
        desc_input = st.text_input("الوصف (اختياري)", key="exp_desc")

        if st.button("إضافة المصروف"):
            if amount_input > 0:
                with get_connection() as write_conn:
                    write_conn.autocommit = True
                    with write_conn.cursor() as write_c:
                        write_c.execute("INSERT INTO expenses (date, category, amount, description, wallet) VALUES (%s, %s, %s, %s, %s)", 
                                  (date_input.strftime("%Y-%m-%d"), category_input, amount_input, desc_input, wallet_out))
                st.success("تمت الإضافة بنجاح! 💸")
                st.rerun()
            else:
                st.error("يرجى إدخال مبلغ أكبر من الصفر.")

    with tab_sidebar_inc:
        inc_date = st.date_input("التاريخ", datetime.today(), key="inc_date")
        wallet_in = st.selectbox("إضافة الرصيد إلى", wallets, key="inc_wal")
        inc_amount = st.number_input("المبلغ المراد إضافته", min_value=0.0, format="%.2f", key="inc_amt")
        inc_desc = st.text_input("مصدر الرصيد (اختياري)", key="inc_desc")
        
        if st.button("إضافة للرصيد"):
            if inc_amount > 0:
                with get_connection() as write_conn:
                    write_conn.autocommit = True
                    with write_conn.cursor() as write_c:
                        write_c.execute("INSERT INTO income (date, amount, description, wallet) VALUES (%s, %s, %s, %s)", 
                                  (inc_date.strftime("%Y-%m-%d"), inc_amount, inc_desc, wallet_in))
                st.success("تمت إضافة الرصيد بنجاح! 💵")
                st.rerun()
            else:
                st.error("يرجى إدخال مبلغ أكبر من الصفر.")
else:
    st.sidebar.info("👁️ أنت الآن تتصفح كضيف.")
    st.sidebar.write("صلاحيتك هي **(للقراءة فقط)**، لا يمكنك إضافة أو تعديل أو حذف البيانات.")

# ==========================================
#              حساب الأرصدة 
# ==========================================
try:
    with get_connection() as read_conn:
        df_exp = pd.read_sql("SELECT * FROM expenses ORDER BY date DESC, id DESC", read_conn)
        df_inc = pd.read_sql("SELECT * FROM income ORDER BY date DESC, id DESC", read_conn)
        
        if not df_exp.empty and 'wallet' not in df_exp.columns: df_exp['wallet'] = 'نقدي'
        elif not df_exp.empty: df_exp['wallet'] = df_exp['wallet'].fillna('نقدي')
        
        if not df_inc.empty and 'wallet' not in df_inc.columns: df_inc['wallet'] = 'نقدي'
        elif not df_inc.empty: df_inc['wallet'] = df_inc['wallet'].fillna('نقدي')

except Exception as e:
    df_exp = pd.DataFrame()
    df_inc = pd.DataFrame()

def get_balance(wallet_name):
    inc = df_inc[df_inc['wallet'] == wallet_name]['amount'].sum() if not df_inc.empty else 0
    exp = df_exp[df_exp['wallet'] == wallet_name]['amount'].sum() if not df_exp.empty else 0
    return inc - exp

cash_balance = get_balance("نقدي")
visa_balance = get_balance("فيزا")
vf_balance = get_balance("فودافون كاش")
total_balance = cash_balance + visa_balance + vf_balance

total_expenses = df_exp['amount'].sum() if not df_exp.empty else 0
unique_days_all = df_exp['date'].nunique() if not df_exp.empty else 0
avg_per_day_all = total_expenses / unique_days_all if unique_days_all > 0 else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("💰 الإجمالي الكلي", f"{total_balance:.2f} ج.م", delta="- رصيد كلي سالب" if total_balance < 0 else None, delta_color="inverse")
c2.metric("💵 رصيد نقدي", f"{cash_balance:.2f} ج.م")
c3.metric("💳 رصيد فيزا", f"{visa_balance:.2f} ج.م")
c4.metric("📱 فودافون كاش", f"{vf_balance:.2f} ج.م")

st.markdown("---")
c_exp1, c_exp2 = st.columns(2)
c_exp1.metric("💸 إجمالي المصاريف", f"{total_expenses:.2f} ج.م")
c_exp2.metric("📊 متوسط الصرف العام", f"{avg_per_day_all:.2f} ج.م/يوم")
st.markdown("---")

# ==========================================
#          عرض التابات بناءً على الصلاحية
# ==========================================
if st.session_state["role"] == "admin":
    tabs = st.tabs(["💸 سجل المصاريف", "💵 سجل الأرصدة المضافة", "🕵️‍♂️ سجل الزيارات (الأمان)"])
    tab_main_exp, tab_main_inc, tab_main_logs = tabs
else:
    tabs = st.tabs(["💸 سجل المصاريف", "💵 سجل الأرصدة المضافة"])
    tab_main_exp, tab_main_inc = tabs

# ==========================================
#             تاب سجل المصاريف
# ==========================================
with tab_main_exp:
    if not df_exp.empty:
        st.subheader("📊 تفاصيل المصاريف حسب كل بند")
        
        cat_stats = df_exp.groupby('category').agg(
            إجمالي_المبلغ=('amount', 'sum'),
            عدد_المرات=('amount', 'count'),
            أيام_الصرف=('date', 'nunique')
        ).reset_index()
        
        cat_stats['متوسط_اليوم_للبند'] = (cat_stats['إجمالي_المبلغ'] / cat_stats['أيام_الصرف']).round(2)
        cat_stats['إجمالي_المبلغ'] = cat_stats['إجمالي_المبلغ'].round(2)
        
        st.bar_chart(cat_stats.set_index('category')['إجمالي_المبلغ'])
        
        st.write("**ملخص البنود:**")
        st.dataframe(cat_stats.rename(columns={
            'category': 'البند', 'إجمالي_المبلغ': 'إجمالي الصرف', 'عدد_المرات': 'الحركات',
            'أيام_الصرف': 'أيام الصرف', 'متوسط_اليوم_للبند': 'متوسط البند/يوم'
        }), use_container_width=True)
        
        st.markdown("---")
        
        # إظهار التعديل والحذف للأدمن فقط
        if st.session_state["role"] == "admin":
            st.subheader("⚙️ تعديل أو حذف مصروف")
            categories = ["طعام ومشروبات", "مواصلات", "فواتير واشتراكات", "استثمارات", "كورسات وتعليم", "ترفيه", "أخرى"]
            df_exp['display_text'] = df_exp['date'].astype(str) + " | " + df_exp['category'] + " | " + df_exp['amount'].astype(str) + " ج.م | " + df_exp['wallet']
            exp_options = dict(zip(df_exp['id'], df_exp['display_text']))
            
            selected_exp_id = st.selectbox("اختر المصروف لتعديله أو حذفه:", options=list(exp_options.keys()), format_func=lambda x: exp_options[x], key="edit_exp")
            
            if selected_exp_id:
                row_data = df_exp[df_exp['id'] == selected_exp_id].iloc[0]
                col_e1, col_e2 = st.columns(2)
                
                with col_e1:
                    with st.expander("✏️ تعديل"):
                        with st.form("edit_exp_form"):
                            new_date = st.date_input("التاريخ", pd.to_datetime(row_data['date']).date())
                            cat_index = categories.index(row_data['category']) if row_data['category'] in categories else 0
                            new_category = st.selectbox("القسم", categories, index=cat_index)
                            wal_index = wallets.index(row_data['wallet']) if row_data['wallet'] in wallets else 0
                            new_wallet = st.selectbox("دُفع من", wallets, index=wal_index)
                            new_amount = st.number_input("المبلغ", min_value=0.0, value=float(row_data['amount']), format="%.2f")
                            current_desc = row_data['description'] if pd.notna(row_data['description']) else ""
                            new_desc = st.text_input("الوصف", value=str(current_desc))
                            
                            if st.form_submit_button("حفظ التعديل"):
                                with get_connection() as update_conn:
                                    update_conn.autocommit = True
                                    with update_conn.cursor() as update_c:
                                        update_c.execute("UPDATE expenses SET date=%s, category=%s, amount=%s, description=%s, wallet=%s WHERE id=%s",
                                                  (new_date.strftime("%Y-%m-%d"), new_category, new_amount, new_desc, new_wallet, selected_exp_id))
                                st.success("تم التعديل!")
                                st.rerun()
                
                with col_e2:
                    with st.expander("🗑️ حذف"):
                        st.warning("تحذير: لا يمكن التراجع!")
                        if st.button("نعم، تأكيد الحذف", key="del_exp_btn"):
                            with get_connection() as del_conn:
                                del_conn.autocommit = True
                                with del_conn.cursor() as del_c:
                                    del_c.execute("DELETE FROM expenses WHERE id=%s", (selected_exp_id,))
                            st.success("تم الحذف!")
                            st.rerun()
            st.markdown("---")

        st.subheader("📝 السجل الكامل للمصاريف")
        display_exp_df = df_exp.drop(columns=['id', 'display_text'], errors='ignore')
        st.dataframe(display_exp_df.rename(columns={
            'date': 'التاريخ', 'category': 'البند', 'amount': 'المبلغ', 
            'description': 'الوصف', 'wallet': 'طريقة الدفع'
        }), use_container_width=True)

    else:
        st.info("لم يتم إضافة أي مصاريف حتى الآن.")

# ==========================================
#             تاب سجل الأرصدة
# ==========================================
with tab_main_inc:
    if not df_inc.empty:
        if st.session_state["role"] == "admin":
            st.subheader("⚙️ تعديل أو حذف رصيد مضاف")
            df_inc['desc_str'] = df_inc['description'].fillna('بدون وصف').astype(str)
            df_inc['display_text'] = df_inc['date'].astype(str) + " | " + df_inc['wallet'] + " | " + df_inc['amount'].astype(str) + " ج.م | " + df_inc['desc_str']
            inc_options = dict(zip(df_inc['id'], df_inc['display_text']))
            
            selected_inc_id = st.selectbox("اختر الرصيد لتعديله أو حذفه:", options=list(inc_options.keys()), format_func=lambda x: inc_options[x], key="edit_inc")
            
            if selected_inc_id:
                row_data = df_inc[df_inc['id'] == selected_inc_id].iloc[0]
                col_i1, col_i2 = st.columns(2)
                
                with col_i1:
                    with st.expander("✏️ تعديل"):
                        with st.form("edit_inc_form"):
                            new_date = st.date_input("التاريخ", pd.to_datetime(row_data['date']).date())
                            wal_index_inc = wallets.index(row_data['wallet']) if row_data['wallet'] in wallets else 0
                            new_wallet = st.selectbox("المحفظة", wallets, index=wal_index_inc)
                            new_amount = st.number_input("المبلغ", min_value=0.0, value=float(row_data['amount']), format="%.2f")
                            current_desc = row_data['description'] if pd.notna(row_data['description']) else ""
                            new_desc = st.text_input("الوصف (المصدر)", value=str(current_desc))
                            
                            if st.form_submit_button("حفظ التعديل"):
                                with get_connection() as update_inc_conn:
                                    update_inc_conn.autocommit = True
                                    with update_inc_conn.cursor() as update_inc_c:
                                        update_inc_c.execute("UPDATE income SET date=%s, amount=%s, description=%s, wallet=%s WHERE id=%s",
                                                  (new_date.strftime("%Y-%m-%d"), new_amount, new_desc, new_wallet, selected_inc_id))
                                st.success("تم التعديل!")
                                st.rerun()
                
                with col_e2:
                    with st.expander("🗑️ حذف"):
                        st.warning("تحذير: لا يمكن التراجع!")
                        if st.button("نعم، تأكيد الحذف", key="del_inc_btn"):
                            with get_connection() as del_inc_conn:
                                del_inc_conn.autocommit = True
                                with del_inc_conn.cursor() as del_inc_c:
                                    del_inc_c.execute("DELETE FROM income WHERE id=%s", (selected_inc_id,))
                            st.success("تم الحذف!")
                            st.rerun()
            st.markdown("---")

        st.subheader("📝 السجل الكامل للأرصدة المضافة")
        display_inc_df = df_inc.drop(columns=['id', 'display_text', 'desc_str'], errors='ignore')
        st.dataframe(display_inc_df.rename(columns={
            'date': 'التاريخ', 'wallet': 'أضيف إلى', 'amount': 'المبلغ', 'description': 'مصدر الرصيد / الوصف'
        }), use_container_width=True)
    else:
        st.info("لم يتم إضافة أي أرصدة حتى الآن.")

# ==========================================
#          تاب الأمان (للأدمن فقط)
# ==========================================
if st.session_state["role"] == "admin":
    with tab_main_logs:
        st.subheader("🕵️‍♂️ سجل زيارات النظام")
        st.write("هنا يتم تسجيل كل عملية دخول للنظام، سواء كانت بصلاحيات أدمن أو ضيف.")
        try:
            with get_connection() as log_read_conn:
                df_logs = pd.read_sql("SELECT * FROM access_logs ORDER BY id DESC LIMIT 50", log_read_conn)
                
            if not df_logs.empty:
                st.dataframe(df_logs.rename(columns={
                    'timestamp': 'وقت وتاريخ الدخول',
                    'username': 'اسم المستخدم',
                    'ip_address': 'عنوان IP',
                    'device_info': 'بيانات الجهاز والمتصفح',
                    'location': 'الموقع الجغرافي'
                }).drop(columns=['id']), use_container_width=True)
            else:
                st.info("لا توجد زيارات مسجلة حتى الآن.")
        except Exception as e:
            st.error("حدث خطأ في تحميل السجل.")
