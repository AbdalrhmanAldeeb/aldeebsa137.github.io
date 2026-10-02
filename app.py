import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime
import io
import warnings

# تجاهل تحذيرات التوافقية بين Pandas وقواعد البيانات
warnings.filterwarnings('ignore')

# 1. إعداد قاعدة البيانات السحابية (PostgreSQL)
# نستخدم st.cache_resource لضمان عدم فتح اتصال جديد مع كل تحديث للصفحة
@st.cache_resource
def init_connection():
    return psycopg2.connect(st.secrets["DATABASE_URL"])

try:
    conn = init_connection()
    conn.autocommit = True  # لحفظ البيانات تلقائياً
    c = conn.cursor()

    # إنشاء الجدول إذا لم يكن موجوداً
    c.execute('''CREATE TABLE IF NOT EXISTS expenses
                 (date TEXT, category TEXT, amount REAL, description TEXT)''')
except Exception as e:
    st.error(f"خطأ في الاتصال بقاعدة البيانات: {e}")

# إعدادات الصفحة
st.set_page_config(page_title="متتبع المصاريف", page_icon="💰", layout="centered")
st.title("💰 متتبع المصاريف الشخصية")

# 2. واجهة إدخال المصاريف (في القائمة الجانبية)
st.sidebar.header("إضافة مصروف جديد")
categories = ["طعام ومشروبات", "مواصلات", "فواتير واشتراكات", "استثمارات", "كورسات وتعليم", "ترفيه", "أخرى"]

date_input = st.sidebar.date_input("التاريخ", datetime.today())
category_input = st.sidebar.selectbox("القسم (البند)", categories)
amount_input = st.sidebar.number_input("المبلغ", min_value=0.0, format="%.2f")
desc_input = st.sidebar.text_input("الوصف (اختياري)")

if st.sidebar.button("إضافة المصروف"):
    if amount_input > 0:
        # لاحظ استخدام %s بدلاً من ? في PostgreSQL
        c.execute("INSERT INTO expenses (date, category, amount, description) VALUES (%s, %s, %s, %s)", 
                  (date_input.strftime("%Y-%m-%d"), category_input, amount_input, desc_input))
        st.sidebar.success("تمت الإضافة بنجاح! 💸")
    else:
        st.sidebar.error("يرجى إدخال مبلغ أكبر من الصفر.")

# 3. عرض البيانات والتحليلات
# قراءة البيانات باستخدام اتصال قاعدة البيانات
df = pd.read_sql("SELECT * FROM expenses", conn)

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
    st.dataframe(category_group.rename(columns={'category': 'البند', 'amount': 'الإجمالي (ج.م)'}), use_container_width=True)

    st.markdown("---")
    st.subheader("📝 السجل الكامل للمصاريف")
    st.dataframe(df.rename(columns={
        'date': 'التاريخ', 
        'category': 'البند', 
        'amount': 'المبلغ', 
        'description': 'الوصف'
    }), use_container_width=True)

    # 4. إضافة زر تصدير البيانات إلى إكسيل
    st.markdown("---")
    st.subheader("📥 تصدير البيانات")

    buffer = io.BytesIO()
    df_excel = df.rename(columns={
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
    st.info("لم يتم إضافة أي مصاريف حتى الآن. ابدأ بإضافة مصروف من القائمة الجانبية.")