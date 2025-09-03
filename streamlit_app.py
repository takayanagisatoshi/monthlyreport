import streamlit as st
from pathlib import Path

st.title("📊 グリーンオーク茅場町 月次報告書（デモ）")

# 1) アップローダー（ダミーでOK）
uploaded_csv = st.file_uploader("📂 点検チケットCSVをアップロード", type="csv")
uploaded_pdfs = st.file_uploader("📂 PDF報告書をアップロード（複数可）", type="pdf", accept_multiple_files=True)

# 2) アプリディレクトリからHTMLを探す
APP_DIR = Path(__file__).parent          # このファイルが置かれている場所
demo_path = APP_DIR / "building_management_report_simple.html"   # 直下に置いた場合

# 3) 見つからない時のデバッグ表示（今だけ役立ちます）
# ※邪魔なら消してOK
with st.expander("🔎 デバッグ：ファイル探索ログ（問題解決したら閉じてOK）", expanded=False):
    st.write("APP_DIR:", str(APP_DIR))
    st.write("存在ファイル:", [p.name for p in APP_DIR.iterdir()])

# 4) 「アップロードが発生したら作成した風に見せる」＋ HTML埋め込み＆ダウンロード
if uploaded_csv or uploaded_pdfs:
    st.success("✅ レポートを作成しました！")

    if demo_path.exists():
        html_content = demo_path.read_text(encoding="utf-8")

        # 4-1) 画面内に埋め込み表示
        st.components.v1.html(html_content, height=800, scrolling=True)

        # 4-2) ダウンロードボタンで配布（Markdownリンクではなく、こちらが確実）
        st.download_button(
            "📥 月次レポートをダウンロード",
            data=html_content,
            file_name="building_management_report_simple.html",
            mime="text/html",
        )
    else:
        st.error("⚠️ サンプルHTMLが見つかりません。リポジトリ直下に 'building_management_report_simple.html' を置いてください。")
