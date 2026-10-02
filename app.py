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

    # إنشاء الجدول الأساسي
    c.execute('''CREATE TABLE IF NOT EXISTS expenses
                 (date TEXT, category TEXT, amount REAL, description TEXT)''')
    
    # إضافة عمود معرف فريد (ID) للمصاريف القديمة والجديدة
    try:
        c.execute("ALTER TABLE expenses ADD COLUMN id SERIAL PRIMARY KEY")
    except Exception:
        pass # العمود موجود بالفعل

except Exception as e:
    st.error(f"خطأ في الاتصال بقاعدة البيانات: {e}")

st.set_page_config(page_title="متتبع المصاريف", page_icon="💰", layout="centered")
st.title("💰 متتبع المصاريف الشخصية")

# --- واجهة إدخال المصاريف ---
st.sidebar.header("إضافة مصروف جديد")
categories = ["طعام ومشروبات", "مواصلات", "فواتير واشتراكات", "استثمارات", "كورسات وتعليم", "ترفيه", "أخرى"]

date_input = st.sidebar.date_input("التاريخ", datetime.today())
category_input = st.sidebar.selectbox("القسم (البند)", categories)
amount_input = st.sidebar.number_input("المبلغ", min_value=0.0, format="%.2f")
desc_input = st.sidebar.text_input("الوصف (اختياري)")

if st.sidebar.button("إضافة المصروف"):
    if amount_input > 0:
        c.execute("INSERT INTO expenses (date, category, amount, description) VALUES (%s, %s, %s, %s)", 
                  (date_input.strftime("%Y-%m-%d"), category_input, amount_input, desc_input))
        st.sidebar.success("تمت الإضافة بنجاح! 💸")
        st.rerun() # تحديث الصفحة فوراً
    else:
        st.sidebar.error("يرجى إدخال مبلغ أكبر من الصفر.")

# --- عرض البيانات ---
# سحب البيانات وترتيبها من الأحدث للأقدم
df = pd.read_sql("SELECT * FROM expenses ORDER BY date DESC, id DESC", conn)

if not df.empty:
    df['amount'] = pd.to_numeric(df['amount'])
    df['date'] = pd.to_datetime(df['date'])

    total_expenses = df['amount'].sum()
    unique_days = df['date'].nunique()
    avg_per_day = total_expenses / unique_days if unique_days > 0 else 0

    col1, col2 = st.columns(2)
    col1.metric("إجمالي المصاريف", f"{total_expenses:.2f} ج.م")
    col2.metric("متوسط الصرف اليومي", f"{avg_per_day:.2f} ج.م / يوم")

    st.markdown("---")
    st.subheader("📊 المصاريف حسب كل بند")
    category_group = df.groupby('category')['amount'].sum().reset_index()
    st.bar_chart(category_group.set_index('category'))
    
    st.markdown("---")
    
    # --- قسم التعديل والحذف الجديد ---
    st.subheader("⚙️ تعديل أو حذف مصروف")
    
    # تجهيز قائمة المصاريف لتسهيل الاختيار
    df['display_text'] = df['date'].dt.strftime('%Y-%m-%d') + " | " + df['category'] + " | " + df['amount'].astype(str) + " ج.م"
    options_dict = dict(zip(df['id'], df['display_text']))
    
    selected_id = st.selectbox("اختر المصروف الذي تريد تعديله أو حذفه:", 
                               options=list(options_dict.keys()), 
                               format_func=lambda x: options_dict[x])
    
    if selected_id:
        row_data = df[df['id'] == selected_id].iloc[0]
        
        col_edit, col_delete = st.columns(2)
        
        # زر التعديل
        with col_edit:
            with st.expander("✏️ تعديل المصروف"):
                with st.form("edit_form"):
                    new_date = st.date_input("التاريخ الجديد", row_data['date'].date())
                    # اختيار القسم الحالي كقيمة افتراضية
                    cat_index = categories.index(row_data['category']) if row_data['category'] in categories else 0
                    new_category = st.selectbox("القسم الجديد", categories, index=cat_index)
                    new_amount = st.number_input("المبلغ الجديد", min_value=0.0, value=float(row_data['amount']), format="%.2f")
                    
                    # التعامل مع الوصف الفارغ
                    current_desc = row_data['description'] if pd.notna(row_data['description']) else ""
                    new_desc = st.text_input("الوصف الجديد", value=str(current_desc))
                    
                    if st.form_submit_button("حفظ التعديلات"):
                        c.execute("UPDATE expenses SET date=%s, category=%s, amount=%s, description=%s WHERE id=%s",
                                  (new_date.strftime("%Y-%m-%d"), new_category, new_amount, new_desc, selected_id))
                        st.success("تم التعديل! جاري التحديث...")
                        st.rerun()
        
        # زر الحذف
        with col_delete:
            with st.expander("🗑️ حذف المصروف"):
                st.warning("تحذير: لا يمكن التراجع عن هذا الإجراء!")
                if st.button("نعم، تأكيد الحذف"):
                    c.execute("DELETE FROM expenses WHERE id=%s", (selected_id,))
                    st.success("تم الحذف! جاري التحديث...")
                    st.rerun()

    st.markdown("---")
    st.subheader("📝 السجل الكامل للمصاريف")
    
    # إخفاء أعمدة الـ ID والنص التعريفي من العرض النهائي
    display_df = df.drop(columns=['id', 'display_text'])
    st.dataframe(display_df.rename(columns={
        'date': 'التاريخ', 
        'category': 'البند', 
        'amount': 'المبلغ', 
        'description': 'الوصف'
    }), use_container_width=True)

    # تصدير البيانات إلى إكسيل
    st.markdown("---")
    st.subheader("📥 تصدير البيانات")

    buffer = io.BytesIO()
    df_excel = display_df.rename(columns={
        'date': 'التاريخ', 
        'category': 'البند', 
        'amount': 'المبلغ', 
        'description': 'الوصف'
    })
    
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
