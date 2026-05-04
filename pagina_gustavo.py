import streamlit as st
import pandas as pd
import random

st.set_page_config(page_title="Gestor de Frota", layout="wide")

st.title("🚜 Gestor de Frota — Ranking de Risco")

regiao = st.selectbox(
    "Filtrar por região:",
    ["Todas", "Norte", "Sul", "Leste", "Oeste"]
)

dados = []

for i in range(10):
    dados.append({
        "Equipamento": f"EQP-{i+1}",
        "Região": random.choice(["Norte", "Sul", "Leste", "Oeste"]),
        "Score de Risco": random.randint(0, 100)
    })

df = pd.DataFrame(dados)

if regiao != "Todas":
    df = df[df["Região"] == regiao]

df = df.sort_values(by="Score de Risco", ascending=False)

st.subheader("📊 Equipamentos com Maior Risco")
st.dataframe(df, use_container_width=True)