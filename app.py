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
        pass # العمود موجود بالفعل

    # إنشاء جدول الرصيد (الإيداعات) الجديد
    c.execute('''CREATE TABLE IF NOT EXISTS income
                 (id SERIAL PRIMARY KEY, date TEXT, amount REAL, description TEXT)''')

except Exception as e:
    st.error(f"خطأ في الاتصال بقاعدة البيانات: {e}")

st.set_page_config(page_title="متتبع المصاريف", page_icon="💰", layout="centered")
st.title("💰 متتبع المصاريف الشخصية")

# --- واجهة الإدخال في القائمة الجانبية ---
st.sidebar.title("إدارة الأموال 💼")
tab_expense, tab_income = st.sidebar.tabs(["إضافة مصروف 💸", "إضافة رصيد 💵"])

# تاب إضافة المصروف
with tab_expense:
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
with tab_income:
    inc_date = st.date_input("التاريخ", datetime.today(), key="inc_date")
    inc_amount = st.number_input("المبلغ المراد إضافته", min_value=0.0, format="%.2f", key="inc_amt")
    inc_desc = st.text_input("مصدر الرصيد (اختياري) مثلا: الفلوس الحالية، راتب", key="inc_desc")
    
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

# حساب الإجماليات
total_expenses = df_exp['amount'].sum() if not df_exp.empty else 0
total_income = df_inc['amount'].sum() if not df_inc.empty else 0
current_balance = total_income - total_expenses

# عرض البطاقات العلوية (3 أعمدة)
col1, col2, col3 = st.columns(3)

# لو الرصيد أقل من صفر هيظهر باللون الأحمر للتنبيه
balance_delta = None
if current_balance < 0:
    balance_delta = "- رصيد بالسالب"

col1.metric("الرصيد المتاح 💵", f"{current_balance:.2f} ج.م", delta=balance_delta, delta_color="inverse")
col2.metric("إجمالي المصاريف 💸", f"{total_expenses:.2f} ج.م")

unique_days = df_exp['date'].nunique() if not df_exp.empty else 0
avg_per_day = total_expenses / unique_days if unique_days > 0 else 0
col3.metric("متوسط الصرف 📊", f"{avg_per_day:.2f} ج.م/يوم")

st.markdown("---")

if not df_exp.empty:
    # الرسوم البيانية
    st.subheader("📊 المصاريف حسب كل بند")
    category_group = df_exp.groupby('category')['amount'].sum().reset_index()
    st.bar_chart(category_group.set_index('category'))
    
    st.markdown("---")
    
    # قسم التعديل والحذف
    st.subheader("⚙️ تعديل أو حذف مصروف")
    df_exp['display_text'] = df_exp['date'].astype(str) + " | " + df_exp['category'] + " | " + df_exp['amount'].astype(str) + " ج.م"
    options_dict = dict(zip(df_exp['id'], df_exp['display_text']))
    
    selected_id = st.selectbox("اختر المصروف الذي تريد تعديله أو حذفه:", 
                               options=list(options_dict.keys()), 
                               format_func=lambda x: options_dict[x])
    
    if selected_id:
        row_data = df_exp[df_exp['id'] == selected_id].iloc[0]
        col_edit, col_delete = st.columns(2)
        
        with col_edit:
            with st.expander("✏️ تعديل المصروف"):
                with st.form("edit_form"):
                    new_date = st.date_input("التاريخ الجديد", pd.to_datetime(row_data['date']).date())
                    cat_index = categories.index(row_data['category']) if row_data['category'] in categories else 0
                    new_category = st.selectbox("القسم الجديد", categories, index=cat_index)
                    new_amount = st.number_input("المبلغ الجديد", min_value=0.0, value=float(row_data['amount']), format="%.2f")
                    current_desc = row_data['description'] if pd.notna(row_data['description']) else ""
                    new_desc = st.text_input("الوصف الجديد", value=str(current_desc))
                    
                    if st.form_submit_button("حفظ التعديلات"):
                        c.execute("UPDATE expenses SET date=%s, category=%s, amount=%s, description=%s WHERE id=%s",
                                  (new_date.strftime("%Y-%m-%d"), new_category, new_amount, new_desc, selected_id))
                        st.success("تم التعديل! جاري التحديث...")
                        st.rerun()
        
        with col_delete:
            with st.expander("🗑️ حذف المصروف"):
                st.warning("تحذير: لا يمكن التراجع عن هذا الإجراء!")
                if st.button("نعم، تأكيد الحذف"):
                    c.execute("DELETE FROM expenses WHERE id=%s", (selected_id,))
                    st.success("تم الحذف! جاري التحديث...")
                    st.rerun()

    st.markdown("---")
    st.subheader("📝 السجل الكامل للمصاريف")
    display_df = df_exp.drop(columns=['id', 'display_text'])
    st.dataframe(display_df.rename(columns={
        'date': 'التاريخ', 
        'category': 'البند', 
        'amount': 'المبلغ', 
        'description': 'الوصف'
    }), use_container_width=True)

    st.markdown("---")
    st.subheader("📥 تصدير البيانات")
    buffer = io.BytesIO()
    df_excel = display_df.rename(columns={'date': 'التاريخ', 'category': 'البند', 'amount': 'المبلغ', 'description': 'الوصف'})
    
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_excel.to_excel(writer, index=False, sheet_name='سجل المصاريف')
    
    st.download_button(
        label="تحميل البيانات كملف Excel 📊",
        data=buffer.getvalue(),
        file_name=f"expenses_{datetime.today().strftime('%Y-%m-%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("لم يتم إضافة أي مصاريف حتى الآن.")
