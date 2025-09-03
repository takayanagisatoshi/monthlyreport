import streamlit as st
import os

st.title("📊 グリーンオーク茅場町 月次報告書（デモ）")

# ===== ファイルアップロード（ダミー用） =====
uploaded_csv = st.file_uploader("📂 点検チケットCSVをアップロード", type="csv")
uploaded_pdfs = st.file_uploader("📂 PDF報告書をアップロード（複数可）", type="pdf", accept_multiple_files=True)

# ===== 固定のサンプルHTMLファイル =====
demo_path = "monthlyreport/building_management_report_simple.html"

# ===== アップロードがあったら「生成した風」に見せる =====
if os.path.exists(demo_path):
    with open(demo_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    # ダウンロード風リンク
    st.markdown(
        f"[📂 月次レポートをダウンロード]({demo_path})",
        unsafe_allow_html=True
    )

    # 埋め込み表示
    st.components.v1.html(html_content, height=800, scrolling=True)
else:
    st.error("⚠️ サンプルHTMLが見つかりません。")
