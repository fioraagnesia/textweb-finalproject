import streamlit as st
import pandas as pd
import pickle as pkl
import matplotlib.pyplot as plt
import joblib
from cleaning.cleaning import clean_text_only
import seaborn as sns
import plotly.express as px



# 1. Page Configuration
st.set_page_config(page_title="Pendeteksi Berita Palsu", layout="wide")

# 2. Sidebar Menu
st.sidebar.title("Menu")
menu = st.sidebar.radio("Telusuri:", ["Pendeteksi Berita Palsu", "Overview Data"])

# --- PAGE 1: CLASSIFIER ---
if menu == "Pendeteksi Berita Palsu":
    st.title("🛡️ Pendeteksi Berita Palsu")
    st.write("Silahkan ketik atau tempel narasi berita yang ingin Anda analisis di bawah ini.")
    st.markdown("<span style='font-weight:bold;color:red'>Hasil analisa baik hanya bila input berbahasa Indonesia.</span>", unsafe_allow_html=True)
    
    # Load your model (use @st.cache_resource to prevent reloading every time)
    @st.cache_resource
    def load_model():
        with open('models/model_lg (1).pkl', 'rb') as file:
            model = pkl.load(file)
        with open('models/tfidf_vectorizer (2).pkl', 'rb') as file:
            vectorizer = pkl.load(file)
        return model, vectorizer

    news_input = st.text_area("Konten Berita:", height=200)
    
    if st.button("Analisa Berita"):
        if news_input.strip():
            news_input = clean_text_only(news_input)
            print("Cleaned Input:", news_input)  

            model, vectorizer = load_model()
            data = vectorizer.transform([news_input])
            prediction = model.predict(data)[0]
            
            print("Prediction:", prediction) 
            if prediction == 1 or prediction == '1':
                st.error("🚩 Berita ini berpotensi HOAX.")
            else:
                st.success("✅ Berita ini terlihat SAH.")
        else:
            st.warning("Please enter some text first.")


# --- PAGE 2: VISUALIZATIONS ---
elif menu == "Overview Data":
    st.title("📊 Overview Dataset")
    st.write("Visualisasi data yang digunakan untuk melatih model klasifikasi berita.")

    # Fungsi untuk memuat data (menggunakan cache agar cepat)
    @st.cache_data
    def load_viz_data():
        # Membaca data
        df = pd.read_excel("cleaned_news.xlsx", engine="openpyxl")
        
        # Normalisasi Tanggal
        # errors='coerce' akan mengubah format yang tidak dikenali menjadi NaT (Not a Time)
        if 'date' in df.columns:
            df['date_normalized'] = pd.to_datetime(df['date'], errors='coerce')
        
        return df

    try:
        df_viz = load_viz_data()

        # 1. Row Metrik (Cards)
        col1, col2, col3 = st.columns(3)
        
        total_data = len(df_viz)
        hoax_count = len(df_viz[df_viz['label'] == 1])
        fact_count = len(df_viz[df_viz['label'] == 0])

        with col1:
            st.metric("Total Seluruh Data", f"{total_data:,}")
        with col2:
            st.metric("Jumlah Berita Hoaks", f"{hoax_count:,}", delta_color="inverse")
        with col3:
            st.metric("Jumlah Berita Fakta", f"{fact_count:,}")

        st.markdown("---")

        # 2. Grafik Distribusi Kategori
        st.subheader("📌 Distribusi Kategori Berita")
        if 'category' in df_viz.columns:
            category_counts = df_viz['category'].value_counts().reset_index()
            category_counts.columns = ['Kategori', 'Jumlah']
            category_counts = category_counts.sort_values(by='Jumlah', ascending=False)  # Ensure sort
            
            fig = px.bar(category_counts, x='Kategori', y='Jumlah')
            fig.update_xaxes(categoryorder='total descending')  # Explicitly sort x-axis by descending values
            st.plotly_chart(fig)
        else:
            st.info("Kolom 'category' tidak ditemukan dalam file cleaned_news.xlsx")

        # 3. Grafik Distribusi Tanggal
        st.subheader("📅 Berita Berdasarkan Tanggal")
        if 'date_normalized' in df_viz.columns:
            # Menghapus data yang gagal dikonversi (NaT)
            date_df = df_viz.dropna(subset=['date_normalized'])
            
            # Kelompokkan berdasarkan tanggal (Harian)
            date_trend = date_df.groupby(date_df['date_normalized'].dt.date).size()
            
            # Tampilkan Line Chart
            st.bar_chart(date_trend)
            st.caption("Grafik menunjukkan frekuensi berita yang terkumpul dalam dataset seiring waktu.")
        else:
            st.warning("Kolom 'date' tidak ditemukan atau tidak dapat diproses.")

    except FileNotFoundError:
        st.error("File 'cleaned_news.xlsx' tidak ditemukan. Pastikan Anda sudah menjalankan proses cleaning terlebih dahulu.")
    except Exception as e:
        st.error(f"Terjadi kesalahan saat memuat data: {e}")