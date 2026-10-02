import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime
import io
import warnings

warnings.filterwarnings('ignore')

@st.cache_resource
def init_connection():
    return psycopg2.connect(st.secrets["DATABASE_URL"])

try:
    conn = init_connection()
    conn.autocommit = True
    c = conn.cursor()

    # إنشاء جدول المصاريف
    c.execute('''CREATE TABLE IF NOT EXISTS expenses
                 (date TEXT, category TEXT, amount REAL, description TEXT)''')
    try:
        c.execute("ALTER TABLE expenses ADD COLUMN id SERIAL PRIMARY KEY")
    except Exception:
        pass 

    # إنشاء جدول الرصيد (الإيداعات)
    c.execute('''CREATE TABLE IF NOT EXISTS income
                 (id SERIAL PRIMARY KEY, date TEXT, amount REAL, description TEXT)''')

except Exception as e:
    st.error(f"خطأ في الاتصال بقاعدة البيانات: {e}")

st.set_page_config(page_title="متتبع المصاريف", page_icon="💰", layout="centered")
st.title("💰 متتبع المصاريف الشخصية")

# --- واجهة الإدخال في القائمة الجانبية ---
st.sidebar.title("إدارة الأموال 💼")
tab_sidebar_exp, tab_sidebar_inc = st.sidebar.tabs(["إضافة مصروف 💸", "إضافة رصيد 💵"])

# تاب إضافة المصروف
with tab_sidebar_exp:
    categories = ["طعام ومشروبات", "مواصلات", "فواتير واشتراكات", "استثمارات", "كورسات وتعليم", "ترفيه", "أخرى"]
    date_input = st.date_input("التاريخ", datetime.today(), key="exp_date")
    category_input = st.selectbox("القسم (البند)", categories, key="exp_cat")
    amount_input = st.number_input("المبلغ", min_value=0.0, format="%.2f", key="exp_amt")
    desc_input = st.text_input("الوصف (اختياري)", key="exp_desc")

    if st.button("إضافة المصروف"):
        if amount_input > 0:
            c.execute("INSERT INTO expenses (date, category, amount, description) VALUES (%s, %s, %s, %s)", 
                      (date_input.strftime("%Y-%m-%d"), category_input, amount_input, desc_input))
            st.success("تمت الإضافة بنجاح! 💸")
            st.rerun()
        else:
            st.error("يرجى إدخال مبلغ أكبر من الصفر.")

# تاب إضافة الرصيد
with tab_sidebar_inc:
    inc_date = st.date_input("التاريخ", datetime.today(), key="inc_date")
    inc_amount = st.number_input("المبلغ المراد إضافته", min_value=0.0, format="%.2f", key="inc_amt")
    inc_desc = st.text_input("مصدر الرصيد (اختياري)", key="inc_desc")
    
    if st.button("إضافة للرصيد"):
        if inc_amount > 0:
            c.execute("INSERT INTO income (date, amount, description) VALUES (%s, %s, %s)", 
                      (inc_date.strftime("%Y-%m-%d"), inc_amount, inc_desc))
            st.success("تمت إضافة الرصيد بنجاح! 💵")
            st.rerun()
        else:
            st.error("يرجى إدخال مبلغ أكبر من الصفر.")

# --- حساب وعرض البيانات ---
df_exp = pd.read_sql("SELECT * FROM expenses ORDER BY date DESC, id DESC", conn)
df_inc = pd.read_sql("SELECT * FROM income ORDER BY date DESC, id DESC", conn)

total_expenses = df_exp['amount'].sum() if not df_exp.empty else 0
total_income = df_inc['amount'].sum() if not df_inc.empty else 0
current_balance = total_income - total_expenses

col1, col2, col3 = st.columns(3)
balance_delta = "- رصيد بالسالب" if current_balance < 0 else None
col1.metric("الرصيد المتاح 💵", f"{current_balance:.2f} ج.م", delta=balance_delta, delta_color="inverse")
col2.metric("إجمالي المصاريف 💸", f"{total_expenses:.2f} ج.م")

unique_days = df_exp['date'].nunique() if not df_exp.empty else 0
avg_per_day = total_expenses / unique_days if unique_days > 0 else 0
col3.metric("متوسط الصرف 📊", f"{avg_per_day:.2f} ج.م/يوم")

st.markdown("---")

tab_main_exp, tab_main_inc = st.tabs(["💸 سجل المصاريف", "💵 سجل الأرصدة المضافة"])

# ==========================================
#             تاب سجل المصاريف
# ==========================================
with tab_main_exp:
    if not df_exp.empty:
        st.subheader("📊 تفاصيل المصاريف حسب كل بند")
        
        # --- التعديل الجديد: حساب متوسط الصرف اليومي لكل بند ---
        cat_stats = df_exp.groupby('category').agg(
            إجمالي_المبلغ=('amount', 'sum'),
            عدد_المرات=('amount', 'count')
        ).reset_index()
        
        # حساب متوسط اليوم بقسمة الإجمالي على عدد الأيام الكلية
        cat_stats['متوسط_اليوم'] = (cat_stats['إجمالي_المبلغ'] / unique_days).round(2) if unique_days > 0 else 0
        cat_stats['إجمالي_المبلغ'] = cat_stats['إجمالي_المبلغ'].round(2)
        
        st.bar_chart(cat_stats.set_index('category')['إجمالي_المبلغ'])
        
        st.write("**ملخص البنود (الإجمالي والمتوسط اليومي):**")
        st.dataframe(cat_stats.rename(columns={
            'category': 'البند',
            'إجمالي_المبلغ': 'إجمالي الصرف (ج.م)',
            'عدد_المرات': 'عدد مرات الصرف',
            'متوسط_اليوم': 'متوسط الصرف في اليوم (ج.م)'
        }), use_container_width=True)
        # ---------------------------------------------
        
        st.markdown("---")
        st.subheader("⚙️ تعديل أو حذف مصروف")
        df_exp['display_text'] = df_exp['date'].astype(str) + " | " + df_exp['category'] + " | " + df_exp['amount'].astype(str) + " ج.م"
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
                        new_amount = st.number_input("المبلغ", min_value=0.0, value=float(row_data['amount']), format="%.2f")
                        current_desc = row_data['description'] if pd.notna(row_data['description']) else ""
                        new_desc = st.text_input("الوصف", value=str(current_desc))
                        
                        if st.form_submit_button("حفظ التعديل"):
                            c.execute("UPDATE expenses SET date=%s, category=%s, amount=%s, description=%s WHERE id=%s",
                                      (new_date.strftime("%Y-%m-%d"), new_category, new_amount, new_desc, selected_exp_id))
                            st.success("تم التعديل!")
                            st.rerun()
            
            with col_e2:
                with st.expander("🗑️ حذف"):
                    st.warning("تحذير: لا يمكن التراجع!")
                    if st.button("نعم، تأكيد الحذف", key="del_exp_btn"):
                        c.execute("DELETE FROM expenses WHERE id=%s", (selected_exp_id,))
                        st.success("تم الحذف!")
                        st.rerun()

        st.markdown("---")
        st.subheader("📝 السجل الكامل للمصاريف")
        display_exp_df = df_exp.drop(columns=['id', 'display_text'])
        st.dataframe(display_exp_df.rename(columns={
            'date': 'التاريخ', 
            'category': 'البند', 
            'amount': 'المبلغ', 
            'description': 'الوصف'
        }), use_container_width=True)

        st.markdown("---")
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            display_exp_df.rename(columns={'date': 'التاريخ', 'category': 'البند', 'amount': 'المبلغ', 'description': 'الوصف'}).to_excel(writer, index=False, sheet_name='المصاريف')
        
        st.download_button(
            label="تحميل البيانات كملف Excel 📊",
            data=buffer.getvalue(),
            file_name=f"expenses_{datetime.today().strftime('%Y-%m-%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("لم يتم إضافة أي مصاريف حتى الآن.")

# ==========================================
#             تاب سجل الأرصدة
# ==========================================
with tab_main_inc:
    if not df_inc.empty:
        st.subheader("⚙️ تعديل أو حذف رصيد مضاف")
        df_inc['desc_str'] = df_inc['description'].fillna('بدون وصف').astype(str)
        df_inc['display_text'] = df_inc['date'].astype(str) + " | " + df_inc['amount'].astype(str) + " ج.م | " + df_inc['desc_str']
        
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
                        new_amount = st.number_input("المبلغ", min_value=0.0, value=float(row_data['amount']), format="%.2f")
                        current_desc = row_data['description'] if pd.notna(row_data['description']) else ""
                        new_desc = st.text_input("الوصف (المصدر)", value=str(current_desc))
                        
                        if st.form_submit_button("حفظ التعديل"):
                            c.execute("UPDATE income SET date=%s, amount=%s, description=%s WHERE id=%s",
                                      (new_date.strftime("%Y-%m-%d"), new_amount, new_desc, selected_inc_id))
                            st.success("تم التعديل!")
                            st.rerun()
            
            with col_i2:
                with st.expander("🗑️ حذف"):
                    st.warning("تحذير: لا يمكن التراجع!")
                    if st.button("نعم، تأكيد الحذف", key="del_inc_btn"):
                        c.execute("DELETE FROM income WHERE id=%s", (selected_inc_id,))
                        st.success("تم الحذف!")
                        st.rerun()

        st.markdown("---")
        st.subheader("📝 السجل الكامل للأرصدة المضافة")
        display_inc_df = df_inc.drop(columns=['id', 'display_text', 'desc_str'])
        st.dataframe(display_inc_df.rename(columns={
            'date': 'التاريخ', 
            'amount': 'المبلغ', 
            'description': 'مصدر الرصيد / الوصف'
        }), use_container_width=True)
    else:
        st.info("لم يتم إضافة أي أرصدة حتى الآن.")
