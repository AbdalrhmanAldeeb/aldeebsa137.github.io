import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime
import io
import warnings

warnings.filterwarnings('ignore')

st.set_page_config(page_title="متتبع المصاريف", page_icon="💰", layout="wide")

# ==========================================
#             نظام تسجيل الدخول
# ==========================================
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

def logout():
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🔒 تسجيل الدخول")
    st.markdown("يرجى إدخال بيانات الاعتماد للوصول إلى متتبع المصاريف.")
    
    with st.form("login_form"):
        username = st.text_input("اسم المستخدم")
        password = st.text_input("كلمة المرور", type="password")
        submit = st.form_submit_button("دخول")
        
        if submit:
            if username == st.secrets["APP_USERNAME"] and password == st.secrets["APP_PASSWORD"]:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("❌ اسم المستخدم أو كلمة المرور غير صحيحة!")
    st.stop()

# ==========================================
#         البرنامج الرئيسي (بعد الدخول)
# ==========================================
st.sidebar.button("تسجيل الخروج 🚪", on_click=logout, use_container_width=True)
st.sidebar.markdown("---")

def get_connection():
    return psycopg2.connect(st.secrets["DATABASE_URL"])

# تجهيز قائمة المحافظ
wallets = ["نقدي", "فيزا", "فودافون كاش"]

try:
    conn = get_connection()
    conn.autocommit = True
    c = conn.cursor()

    # تحديث جداول قاعدة البيانات لإضافة عمود "المحفظة"
    c.execute('''CREATE TABLE IF NOT EXISTS expenses
                 (date TEXT, category TEXT, amount REAL, description TEXT)''')
    try: c.execute("ALTER TABLE expenses ADD COLUMN id SERIAL PRIMARY KEY")
    except Exception: pass 
    try: c.execute("ALTER TABLE expenses ADD COLUMN wallet TEXT DEFAULT 'نقدي'")
    except Exception: pass 

    c.execute('''CREATE TABLE IF NOT EXISTS income
                 (id SERIAL PRIMARY KEY, date TEXT, amount REAL, description TEXT)''')
    try: c.execute("ALTER TABLE income ADD COLUMN wallet TEXT DEFAULT 'نقدي'")
    except Exception: pass 

except Exception as e:
    st.error(f"خطأ في الاتصال بقاعدة البيانات: {e}")
    st.stop()

st.title("💰 متتبع المصاريف الشخصية")

st.sidebar.title("إدارة الأموال 💼")
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

try:
    with get_connection() as read_conn:
        df_exp = pd.read_sql("SELECT * FROM expenses ORDER BY date DESC, id DESC", read_conn)
        df_inc = pd.read_sql("SELECT * FROM income ORDER BY date DESC, id DESC", read_conn)
        
        # معالجة البيانات القديمة التي ليس لها محفظة
        if not df_exp.empty and 'wallet' not in df_exp.columns: df_exp['wallet'] = 'نقدي'
        elif not df_exp.empty: df_exp['wallet'] = df_exp['wallet'].fillna('نقدي')
        
        if not df_inc.empty and 'wallet' not in df_inc.columns: df_inc['wallet'] = 'نقدي'
        elif not df_inc.empty: df_inc['wallet'] = df_inc['wallet'].fillna('نقدي')

except Exception as e:
    st.error(f"خطأ أثناء جلب البيانات: {e}")
    df_exp = pd.DataFrame()
    df_inc = pd.DataFrame()

# ==========================================
#            حساب الأرصدة لكل محفظة
# ==========================================
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

# عرض الأرصدة الأربعة في صف واحد
c1, c2, c3, c4 = st.columns(4)
c1.metric("💰 الإجمالي الكلي", f"{total_balance:.2f} ج.م", delta="- رصيد كلي سالب" if total_balance < 0 else None, delta_color="inverse")
c2.metric("💵 رصيد نقدي", f"{cash_balance:.2f} ج.م")
c3.metric("💳 رصيد فيزا", f"{visa_balance:.2f} ج.م")
c4.metric("📱 فودافون كاش", f"{vf_balance:.2f} ج.م")

st.markdown("---")
# عرض ملخص المصاريف
c_exp1, c_exp2 = st.columns(2)
c_exp1.metric("💸 إجمالي المصاريف", f"{total_expenses:.2f} ج.م")
c_exp2.metric("📊 متوسط الصرف العام", f"{avg_per_day_all:.2f} ج.م/يوم")
st.markdown("---")

tab_main_exp, tab_main_inc = st.tabs(["💸 سجل المصاريف", "💵 سجل الأرصدة المضافة"])

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
            'category': 'البند',
            'إجمالي_المبلغ': 'إجمالي الصرف',
            'عدد_المرات': 'الحركات',
            'أيام_الصرف': 'أيام الصرف',
            'متوسط_اليوم_للبند': 'متوسط البند/يوم'
        }), use_container_width=True)
        
        st.markdown("---")
        st.subheader("⚙️ تعديل أو حذف مصروف")
        df_exp['display_text'] = df_exp['date'].astype(str) + " | " + df_exp['category'] + " | " + df_exp['amount'].astype(str) + " ج.م | " + df_exp['wallet']
        exp_options = dict(zip(df_exp['id'], df_exp['display_text']))
        
        selected_exp_id = st.selectbox("اختر المصروف لتعديله أو حذفه:", 
                                   options=list(exp_options.keys()), 
                                   format_func=lambda x: exp_options[x], key="edit_exp")
        
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
        display_exp_df = df_exp.drop(columns=['id', 'display_text'])
        st.dataframe(display_exp_df.rename(columns={
            'date': 'التاريخ', 
            'category': 'البند', 
            'amount': 'المبلغ', 
            'description': 'الوصف',
            'wallet': 'طريقة الدفع'
        }), use_container_width=True)

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            display_exp_df.rename(columns={'date': 'التاريخ', 'category': 'البند', 'amount': 'المبلغ', 'description': 'الوصف', 'wallet': 'طريقة الدفع'}).to_excel(writer, index=False, sheet_name='المصاريف')
        st.download_button("تحميل البيانات كملف Excel 📊", buffer.getvalue(), f"expenses_{datetime.today().strftime('%Y-%m-%d')}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("لم يتم إضافة أي مصاريف حتى الآن.")

with tab_main_inc:
    if not df_inc.empty:
        st.subheader("⚙️ تعديل أو حذف رصيد مضاف")
        df_inc['desc_str'] = df_inc['description'].fillna('بدون وصف').astype(str)
        df_inc['display_text'] = df_inc['date'].astype(str) + " | " + df_inc['wallet'] + " | " + df_inc['amount'].astype(str) + " ج.م | " + df_inc['desc_str']
        
        inc_options = dict(zip(df_inc['id'], df_inc['display_text']))
        
        selected_inc_id = st.selectbox("اختر الرصيد لتعديله أو حذفه:", 
                                   options=list(inc_options.keys()), 
                                   format_func=lambda x: inc_options[x], key="edit_inc")
        
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
            
            with col_i2:
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
        display_inc_df = df_inc.drop(columns=['id', 'display_text', 'desc_str'])
        st.dataframe(display_inc_df.rename(columns={
            'date': 'التاريخ', 
            'wallet': 'أضيف إلى',
            'amount': 'المبلغ', 
            'description': 'مصدر الرصيد / الوصف'
        }), use_container_width=True)
    else:
        st.info("لم يتم إضافة أي أرصدة حتى الآن.")
