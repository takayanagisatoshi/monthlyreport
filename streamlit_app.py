import streamlit as st
import pandas as pd
import pdfplumber
from anthropic import Anthropic
import tempfile, base64

# ===== サイドバーで APIキー入力 =====
st.sidebar.header("🔑 API設定")
api_key = st.sidebar.text_input("Anthropic API Key", type="password")
if api_key:
    st.session_state["api_key"] = api_key

# ===== Claude呼び出し関数 =====
def analyze_pdf_with_summary(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
    if not text.strip():
        return "不明", "テキスト抽出できず"

    client = Anthropic(api_key=st.session_state["api_key"])
    prompt = f"""
以下は設備点検報告書のテキストです。

1. 指摘事項がある場合は「指摘あり」／問題がなければ「指摘なし」
2. 指摘がある場合はその内容を2〜3行で要約

次の形式で出力してください：
有無: ○○
概要: ○○
---
{text[:6000]}
"""
    resp = client.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    output = resp.content[0].text.strip()

    has_issue, summary = "不明", ""
    for line in output.splitlines():
        if line.startswith("有無:"):
            has_issue = line.replace("有無:", "").strip()
        if line.startswith("概要:"):
            summary = line.replace("概要:", "").strip()
    return has_issue, summary

# ===== PDFリンク生成関数 =====
def make_download_link(uploaded_file):
    data = uploaded_file.read()
    b64 = base64.b64encode(data).decode()
    href = f'<a href="data:application/pdf;base64,{b64}" download="{uploaded_file.name}">📥 {uploaded_file.name}</a>'
    return href

# ===== アップロード =====
st.title("📊 グリーンオーク茅場町 月次報告書")

uploaded_csv = st.file_uploader("📂 点検チケットCSVをアップロード", type="csv")
uploaded_pdfs = st.file_uploader("📂 PDF報告書をアップロード（複数可）", type="pdf", accept_multiple_files=True)

if uploaded_csv is not None:
    tickets = pd.read_csv(uploaded_csv)

    pdf_results = {}
    if uploaded_pdfs:
        for pdf in uploaded_pdfs:
            # 一時ファイルに保存して解析
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(pdf.getvalue())
                pdf_path = tmp.name
            has_issue, summary = analyze_pdf_with_summary(pdf_path)

            # リンク生成
            link = make_download_link(pdf)

            pdf_results[pdf.name] = {"有無": has_issue, "概要": summary, "リンク": link}

    # CSVに「指摘有無」「指摘内容」「ダウンロード」列を追加
    tickets["指摘有無"] = tickets["対象ファイル"].map(lambda x: pdf_results.get(x, {}).get("有無", "不明"))
    tickets["指摘内容"] = tickets["対象ファイル"].map(lambda x: pdf_results.get(x, {}).get("概要", ""))
    tickets["ダウンロード"] = tickets["対象ファイル"].map(lambda x: pdf_results.get(x, {}).get("リンク", ""))

    # ===== サマリー =====
    st.metric("総作業件数", len(tickets))
    st.metric("指摘事項あり", (tickets["指摘有無"] == "指摘あり").sum())
    st.metric("指摘事項なし", (tickets["指摘有無"] == "指摘なし").sum())
    st.metric("担当業者数", tickets["担当会社"].nunique())

    # 一覧テーブル（リンクを有効化）
    st.write("### 点検チケット一覧")
    st.write(tickets.to_html(escape=False, index=False), unsafe_allow_html=True)

    # ===== HTMLダウンロード =====
    html_content = tickets.to_html(escape=False, index=False)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as f:
        f.write(html_content.encode("utf-8"))
        tmpfile = f.name
    with open(tmpfile, "rb") as f:
        st.download_button("📥 HTMLダウンロード", f, file_name="monthly_report.html")
