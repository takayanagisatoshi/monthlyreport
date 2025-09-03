import streamlit as st
import pandas as pd
import plotly.express as px
import pdfplumber
from anthropic import Anthropic
import tempfile

# ====== UIでAPIキー入力 ======
st.sidebar.header("🔑 API設定")
api_key = st.sidebar.text_input("Anthropic API Key", type="password")

if "api_key" not in st.session_state:
    st.session_state["api_key"] = None

if api_key:
    st.session_state["api_key"] = api_key

# ====== Claude呼び出し関数 ======
def summarize_with_claude(text, title="報告要約"):
    if not st.session_state["api_key"]:
        return "⚠️ APIキーが入力されていません。"
    
    client = Anthropic(api_key=st.session_state["api_key"])
    prompt = f"""
以下は建物点検の報告書テキストです。
重要な指摘事項と要約コメントを箇条書きで整理してください。

# テキスト
{text[:6000]}
"""
    try:
        resp = client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )
        return resp.content[0].text
    except Exception as e:
        return f"APIエラー: {e}"

# ====== データ読込 ======
tickets = pd.read_csv("operation_tickets.csv")

pdf_files = [
    "7月度グリーンオーク茅場町ビル保守点検報告書.pdf",
    "GO茅場町_作業報告書_設備巡回点検_20250718_指摘有.pdf"
]

def extract_pdf_text(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text

pdf_texts = {f: extract_pdf_text(f) for f in pdf_files}

# ====== Streamlit画面 ======
st.title("グリーンオーク茅場町ビル 月次報告書")

# 指標
col1, col2 = st.columns(2)
with col1:
    st.metric("総作業件数", len(tickets))
    st.metric("指摘件数", (tickets["status"].str.contains("指摘")).sum())
    st.metric("指摘率", f"{(tickets['status'].str.contains('指摘').mean()*100):.1f}%")

with col2:
    fig = px.pie(
        tickets,
        names=tickets["status"].apply(lambda x: "指摘有" if "指摘" in str(x) else "指摘無"),
        title="指摘有無の割合"
    )
    st.plotly_chart(fig, use_container_width=True)

# チケット一覧
st.subheader("点検チケット一覧")
st.dataframe(tickets[["date", "task_name", "担当者", "status"]])

# Claude要約
st.subheader("報告書要約（Claude生成）")
for fname, text in pdf_texts.items():
    st.markdown(f"### {fname}")
    summary = summarize_with_claude(text)
    st.write(summary)

# ====== HTML出力 ======
html_content = f"""
<html>
<head><meta charset="utf-8"></head>
<body>
<h1>グリーンオーク茅場町ビル 月次報告書</h1>
<p>総作業件数: {len(tickets)}</p>
<p>指摘件数: {(tickets["status"].str.contains("指摘")).sum()}</p>
<p>指摘率: {(tickets['status'].str.contains('指摘').mean()*100):.1f}%</p>
<h2>報告書要約</h2>
"""
for fname, text in pdf_texts.items():
    html_content += f"<h3>{fname}</h3><p>{summarize_with_claude(text)}</p>"

html_content += "</body></html>"

with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as f:
    f.write(html_content.encode("utf-8"))
    tmpfile = f.name

with open(tmpfile, "rb") as f:
    st.download_button("📥 HTMLダウンロード", f, file_name="monthly_report.html")
