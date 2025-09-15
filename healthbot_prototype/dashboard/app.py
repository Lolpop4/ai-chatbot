import streamlit as st
import sqlite3, pandas as pd, os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "healthbot.db")

st.set_page_config(page_title="HealthBot Dashboard", layout="wide")
st.title("🩺 HealthBot Admin Dashboard")

# Outbreak reports
st.header("🚨 Outbreak Reports")
conn = sqlite3.connect(DB_PATH)
reports = pd.read_sql("SELECT * FROM alerts_log ORDER BY created_at DESC", conn)
messages = pd.read_sql("SELECT * FROM messages ORDER BY created_at DESC", conn)
conn.close()

st.dataframe(reports)

# Messages log
st.header("💬 User Messages")
st.dataframe(messages)
