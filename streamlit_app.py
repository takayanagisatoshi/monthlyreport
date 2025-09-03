import streamlit as st
import pandas as pd
import pdfplumber
from anthropic import Anthropic
import tempfile

# ===== サイドバーで APIキー入力 =====
st.sidebar.header("🔑 API設定")
api_key = st.sidebar.text_input("Anthropic API Key", type="password")
if api_key:
    st.session_state["api_key"] = api_key

# ===== Claude呼び出し関数 =====
def analyze_pdf_with_details(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
    if not text.strip():
        return "不明", "テキスト抽出できず", "不明"

    client = Anthropic(api_key=st.session_state["api_key"])
    prompt = f"""
以下は設備点検報告書のテキストです。
次の3つを必ず抽出してください：

1. 指摘有無 → 「指摘あり」または「指摘なし」
2. 指摘内容 → 2〜3行で要約（指摘なしの場合は「特になし」）
3. 是正状況 → 「完了」「対応中」「予定」「不明」など

出力フォーマットは必ず以下にしてください：
有無: ○○
概要: ○○
是正状況: ○○
---
{text[:6000]}
"""
    resp = client.messages.create(
        model="claude-3-sonnet-20240229",  # ← sonnetを利用
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    output = resp.content[0].text.strip()

    has_issue, summary, status = "不明", "", "不明"
    for line in output.splitlines():
        if line.startswith("有無:"):
            has_issue = line.replace("有無:", "").strip()
        if line.startswith("概要:"):
            summary = line.replace("概要:", "").strip()
        if line.startswith("是正状況:"):
            status = line.replace("是正状況:", "").strip()
    return has_issue, summary, status

# ===== CSS =====
st.markdown("""
<style>
.card {
  background-color: #f8f9fa;
  border-radius: 12px;
  padding: 20px;
  text-align: center;
  box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
  font-size: 18px;
  margin: 5px;
}
.card b { font-size: 24px; }
table.dataframe {
  border-collapse: collapse;
  width: 100%;
}
table.dataframe th {
  background: #495057;
  color: white;
  padding: 6px;
}
table.dataframe td {
  padding: 6px;
  border: 1px solid #ddd;
}
</style>
""", unsafe_allow_html=True)

# ===== ファイルアップロード =====
st.title("📊 グリーンオーク茅場町 月次報告書")

uploaded_csv = st.file_uploader("📂 点検チケットCSVをアップロード", type="csv")
uploaded_pdfs = st.file_uploader("📂 PDF報告書をアップロード（複数可）", type="pdf", accept_multiple_files=True)

if uploaded_csv is not None:
    tickets = pd.read_csv(uploaded_csv)

    # PDF解析
    pdf_results = {}
    if uploaded_pdfs:
        for pdf in uploaded_pdfs:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(pdf.read())
                pdf_path = tmp.name
            has_issue, summary, status = analyze_pdf_with_details(pdf_path)
            pdf_results[pdf.name] = {"有無": has_issue, "概要": summary, "是正状況": status}

    # CSVに追加
    tickets["指摘有無"] = tickets["対象ファイル"].map(lambda x: pdf_results.get(x, {}).get("有無", "不明"))
    tickets["指摘内容"] = tickets["対象ファイル"].map(lambda x: pdf_results.get(x, {}).get("概要", ""))
    tickets["是正状況"] = tickets["対象ファイル"].map(lambda x: pdf_results.get(x, {}).get("是正状況", "不明"))

    # ===== サマリーカード =====
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"<div class='card'>総業務数<br><b>{len(tickets)}件</b></div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='card'>指摘事項あり<br><b>{(tickets['指摘有無']=='指摘あり').sum()}件</b></div>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"<div class='card'>指摘事項なし<br><b>{(tickets['指摘有無']=='指摘なし').sum()}件</b></div>", unsafe_allow_html=True)
    with col4:
        st.markdown(f"<div class='card'>担当業者数<br><b>{tickets['担当会社'].nunique()}社</b></div>", unsafe_allow_html=True)

    # ===== 点検表（色付け） =====
    def highlight(row):
        if row["指摘有無"] == "指摘あり":
            return ["background-color: #f8d7da"] * len(row)
        elif "対応中" in str(row.get("是正状況", "")):
            return ["background-color: #fff3cd"] * len(row)
        return [""] * len(row)

    styled_df = tickets[["日付", "担当会社", "対象ファイル", "指摘有無", "指摘内容", "是正状況"]].style.apply(highlight, axis=1)
    st.write(styled_df.to_html(escape=False), unsafe_allow_html=True)

    # ===== HTMLダウンロード =====
    html_content = f"""
    <html>
    <head><meta charset="utf-8"></head>
    <body>
    <h1>グリーンオーク茅場町 月次報告書</h1>
    {styled_df.to_html(escape=False)}
    </body>
    </html>
    """

    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as f:
        f.write(html_content.encode("utf-8"))
        tmpfile = f.name

    with open(tmpfile, "rb") as f:
        st.download_button("📥 HTMLダウンロード", f, file_name="monthly_report.html")
