import streamlit as st
import pandas as pd
from databricks import sql
from databricks.sdk import WorkspaceClient
from openai import OpenAI
import io

# === KONFIGURACJA ===
DATABRICKS_HOST  = st.secrets["DATABRICKS_HOST"]
DATABRICKS_TOKEN = st.secrets["DATABRICKS_TOKEN"]
DATABRICKS_HTTP_PATH = st.secrets["DATABRICKS_HTTP_PATH"]
OPENAI_API_KEY   = st.secrets["OPENAI_API_KEY"]

CATALOG = "inspektor_budzet"
SCHEMA  = "rowkop"

st.set_page_config(page_title="Inspektor Budżet", layout="wide")

# === NAGŁÓWEK ===
col_logo, col_tytul = st.columns([1, 4])
with col_logo:
    st.image("StreamLit_App/logo.png", width=200)
with col_tytul:
    st.markdown("""
**Praca Zaliczeniowa z Przedmiotu**
*„Projektowanie produktu cyfrowego i architektury IT w start-up'ach"*

### pt. „Inspektor Budżet"

**Grupa Menedżerska Nr 6:**
Leon Nalepa, Robert Panek, Barbara Roszkowska, Piotr Sucharski, Wieńczysław Szoja, Joanna Wcisło
""")
st.divider()

# === FUNKCJE POMOCNICZE ===
# Kolejność odpowiada kolejności kroków w procesie:
# 1. Upload plików → 2. Połączenie z Databricks → 3. Pobranie raportu → 4. Analiza AI

def upload_to_databricks(file_bytes, filename, subfolder="bronze"):
    # Wysyła plik do Databricks Volumes (bronze)
    w = WorkspaceClient(
        host=DATABRICKS_HOST,
        token=DATABRICKS_TOKEN
    )
    path = f"/Volumes/{CATALOG}/{SCHEMA}/{subfolder}/{filename}"
    w.files.upload(path, io.BytesIO(file_bytes), overwrite=True)
    return path

def get_databricks_connection():
    # Otwiera połączenie SQL z Databricks
    return sql.connect(
        server_hostname=DATABRICKS_HOST.replace("https://", ""),
        http_path=DATABRICKS_HTTP_PATH,
        access_token=DATABRICKS_TOKEN
    )

def load_report():
    # Pobiera raport rozbieżności z tabeli gold
    with get_databricks_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(f"SELECT * FROM {CATALOG}.{SCHEMA}.gold_raport_rozbieznosci")
            return cursor.fetchall_arrow().to_pandas()

def analyze_with_llm(df):
    client = OpenAI(api_key=OPENAI_API_KEY)
    raport_text = df.to_string(index=False)
    prompt = f"""Jesteś ekspertem ds. kontroli budżetowej w gminie.
Przeanalizuj poniższy raport rozbieżności między danymi ERP gminy a fakturą dostawcy robót ziemnych.
Napisz krótkie podsumowanie po polsku (3-5 zdań): co się nie zgadza, na czyją niekorzyść i jaka jest łączna kwota rozbieżności.

Raport:
{raport_text}"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# === ZAKŁADKI ===
tab1, tab2 = st.tabs(["Weryfikacja faktury", "Analiza kontraktu"])

# --- ZAKŁADKA 1: WERYFIKACJA FAKTURY ---
with tab1:

    # Sekcja 1: Upload plików
    st.header("1. Wgraj pliki")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Dane zużycia (CSV)")
        csv_file = st.file_uploader("Wybierz plik CSV z ERP", type=["csv"])
        if csv_file and st.button("Wgraj CSV"):
            with st.spinner("Wysyłanie..."):
                path = upload_to_databricks(csv_file.read(), csv_file.name)
                st.success(f"Wgrano: {path}")

    with col2:
        st.subheader("Faktura (PDF)")
        pdf_file = st.file_uploader("Wybierz plik faktury PDF", type=["pdf"])
        if pdf_file and st.button("Wgraj PDF"):
            with st.spinner("Wysyłanie..."):
                path = upload_to_databricks(pdf_file.read(), pdf_file.name)
                st.success(f"Wgrano: {path}")

    st.divider()

    # Sekcja 2: Raport rozbieżności
    st.header("2. Raport rozbieżności")

    if st.button("Odśwież raport"):
        with st.spinner("Pobieranie danych..."):
            try:
                df = load_report()
                st.session_state["df_raport"] = df
            except Exception as e:
                st.error(f"Błąd połączenia z Databricks: {e}")

    if "df_raport" in st.session_state:
        df = st.session_state["df_raport"]

        def highlight_status(row):
            if row["status"] == "NIEZGODNOŚĆ":
                return ["background-color: #ffe0e0"] * len(row)
            return ["background-color: #e0ffe0"] * len(row)

        st.dataframe(df.style.apply(highlight_status, axis=1), use_container_width=True)

        laczna_roznica = df["roznica_kwota"].sum()
        st.metric(
            label="Łączna rozbieżność kwotowa (netto)",
            value=f"{laczna_roznica:,.2f} zł",
            delta=f"{laczna_roznica:,.2f} zł na niekorzyść gminy" if laczna_roznica > 0 else "Na korzyść gminy"
        )

        st.divider()

        # Sekcja 3: Analiza AI
        st.header("3. Analiza AI")
        if st.button("Generuj analizę"):
            with st.spinner("GPT analizuje raport..."):
                analiza = analyze_with_llm(st.session_state["df_raport"])
                st.session_state["analiza"] = analiza

        if "analiza" in st.session_state:
            st.write(st.session_state["analiza"])

# --- ZAKŁADKA 2: ANALIZA KONTRAKTU ---
with tab2:
    st.header("Analiza kontraktu")
    st.info("Wkrótce — upload kontraktu PDF i automatyczna analiza struktury pozycji.")


