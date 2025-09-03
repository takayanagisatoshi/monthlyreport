import streamlit as st
import pandas as pd
import json
from datetime import datetime
import base64
import io
import os

# 外部パッケージの動的インポート
try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# ページ設定
st.set_page_config(
    page_title="月次業務報告レポート生成",
    page_icon="📊",
    layout="wide"
)

def check_dependencies():
    """依存関係をチェックし、インストール指示を表示"""
    missing_packages = []
    
    if not PDF_AVAILABLE:
        missing_packages.append("PyPDF2")
    
    if not ANTHROPIC_AVAILABLE:
        missing_packages.append("anthropic")
    
    if missing_packages:
        st.warning("以下のパッケージが不足しています:")
        for package in missing_packages:
            st.code(f"pip install {package}")
        
        st.info("パッケージをインストールしてからアプリを再起動してください。")
        return False
    
    return True

def extract_text_from_pdf_safe(pdf_file):
    """安全なPDFテキスト抽出（PyPDF2が利用可能な場合のみ）"""
    if not PDF_AVAILABLE:
        st.error("PyPDF2パッケージが必要です。`pip install PyPDF2` でインストールしてください。")
        return None
    
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        
        for page_num, page in enumerate(pdf_reader.pages):
            page_text = page.extract_text()
            text += f"--- ページ {page_num + 1} ---\n{page_text}\n\n"
        
        return text
    
    except Exception as e:
        st.error(f"PDF読み取りエラー: {e}")
        return None

def manual_pdf_input():
    """PDFが読めない場合の手動入力オプション"""
    st.subheader("📝 手動でPDF内容を入力")
    
    st.info("""
    PDFから自動でテキストを抽出できない場合は、
    以下のテキストエリアに点検報告書の内容を手動で入力してください。
    """)
    
    manual_text = st.text_area(
        "点検報告書の内容",
        height=300,
        placeholder="点検項目、結果、指摘事項等を入力してください..."
    )
    
    filename = st.text_input("ファイル名", value="手動入力.txt")
    
    if manual_text.strip():
        return [{"text": manual_text, "filename": filename}]
    
    return []

def analyze_text_with_anthropic_safe(text, filename, api_key):
    """安全なAnthropic API呼び出し"""
    if not ANTHROPIC_AVAILABLE:
        st.error("anthropicパッケージが必要です。`pip install anthropic` でインストールしてください。")
        return None
    
    try:
        client = anthropic.Anthropic(api_key=api_key)
        
        analysis_prompt = f"""
以下は建物管理の点検報告書「{filename}」の内容です：

{text}

この内容を建物管理の専門家として分析し、以下のJSON形式で回答してください：

{{
  "inspection_summary": {{
    "inspection_date": "点検日",
    "contractor": "業者名",
    "inspection_type": "点検種別"
  }},
  "issues_found": [
    {{
      "issue_description": "指摘事項",
      "severity": "緊急/重要/軽微",
      "location": "場所",
      "recommended_action": "推奨対応"
    }}
  ],
  "urgent_items": [
    {{
      "item": "緊急対応項目",
      "immediate_action": "必要な対応"
    }}
  ]
}}

日本語で回答してください。
"""
        
        # 利用可能なモデルを順番に試す
        models_to_try = [
            "claude-3-5-sonnet-20241022",  # 最新Sonnet
            "claude-3-5-sonnet-20240620",  # Claude 3.5 Sonnet
            "claude-3-sonnet-20240229",    # Claude 3 Sonnet
            "claude-3-haiku-20240307"      # より軽量なモデル
        ]
        
        response = None
        used_model = None
        
        for model in models_to_try:
            try:
                response = client.messages.create(
                    model=model,
                    max_tokens=3000,
                    messages=[{"role": "user", "content": analysis_prompt}]
                )
                used_model = model
                break
            except Exception as model_error:
                if "not_found" in str(model_error) or "404" in str(model_error):
                    continue  # 次のモデルを試す
                else:
                    raise model_error  # その他のエラーは再発生
        
        if response is None:
            raise Exception("利用可能なClaude モデルが見つかりません。API KEYの権限を確認してください。")
        
        st.info(f"使用モデル: {used_model}")
        
        response_text = response.content[0].text
        
        # JSON抽出
        if '```json' in response_text:
            json_start = response_text.find('```json') + 7
            json_end = response_text.find('```', json_start)
            if json_end != -1:
                response_text = response_text[json_start:json_end]
        
        return json.loads(response_text.strip())
    
    except Exception as e:
        st.error(f"AI分析エラー: {e}")
        return None

def simple_keyword_analysis(text, filename):
    """キーワードベースの簡易分析（フォールバック）"""
    urgent_keywords = ["異常", "破損", "不良", "漏水", "故障", "緊急", "危険"]
    attention_keywords = ["要注意", "劣化", "摩耗", "汚れ", "錆び", "異音"]
    
    issues = []
    urgent_items = []
    
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 緊急事項チェック
        for keyword in urgent_keywords:
            if keyword in line:
                urgent_items.append({
                    "item": line,
                    "immediate_action": "要確認・対応"
                })
                break
        
        # 一般的な指摘事項
        for keyword in attention_keywords:
            if keyword in line:
                severity = "重要" if any(uk in line for uk in urgent_keywords) else "軽微"
                issues.append({
                    "issue_description": line,
                    "severity": severity,
                    "location": "要確認",
                    "recommended_action": "点検・確認"
                })
                break
    
    return {
        "inspection_summary": {
            "inspection_date": "要確認",
            "contractor": "要確認",
            "inspection_type": filename
        },
        "issues_found": issues,
        "urgent_items": urgent_items
    }

def process_csv_data(csv_file):
    """CSV処理（pandas使用）"""
    try:
        df = pd.read_csv(csv_file)
        
        total_operations = len(df)
        completed_operations = len(df[df['ステータス'] == '実施済'])
        
        operations_with_issues = df[df['対象ファイル'].str.contains('指摘有', na=False)]
        operations_no_issues = df[df['対象ファイル'].str.contains('指摘無', na=False)]
        
        companies = df['担当会社'].dropna().unique()
        
        stats = {
            "total_operations": total_operations,
            "completed_operations": completed_operations,
            "completion_rate": round(completed_operations / total_operations * 100, 1) if total_operations > 0 else 0,
            "companies_count": len(companies),
            "operations_with_issues": len(operations_with_issues),
            "operations_no_issues": len(operations_no_issues),
            "issue_rate": round(len(operations_with_issues) / total_operations * 100, 1) if total_operations > 0 else 0,
        }
        
        return {
            "stats": stats,
            "operations": df,
            "operations_with_issues": operations_with_issues,
            "operations_no_issues": operations_no_issues,
            "companies": companies
        }
    
    except Exception as e:
        st.error(f"CSV処理エラー: {e}")
        return None

def generate_simple_html_report(data, report_month, property_name, client_name, analysis_results=None):
    """シンプルなHTMLレポート生成"""
    
    html_content = f"""
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{report_month} {property_name} 月次業務報告レポート</title>
    <style>
        body {{
            font-family: 'Yu Gothic', sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f8f9fa;
        }}
        .header {{
            background-color: #495057;
            color: white;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 5px;
        }}
        .summary-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        .card {{
            background: white;
            padding: 15px;
            border-radius: 5px;
            text-align: center;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        .section {{
            background: white;
            margin-bottom: 20px;
            border-radius: 5px;
            overflow: hidden;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        .section-header {{
            background-color: #6c757d;
            color: white;
            padding: 10px 15px;
            font-weight: bold;
        }}
        .content {{
            padding: 15px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            border: 1px solid #dee2e6;
            padding: 8px;
            text-align: left;
        }}
        th {{
            background-color: #f8f9fa;
        }}
        .urgent {{
            background-color: #f8d7da;
        }}
        .important {{
            background-color: #fff3cd;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{report_month} {property_name} 月次業務報告レポート</h1>
        <div>発注者: {client_name} | 作成日: {datetime.now().strftime("%Y年%m月%d日")}</div>
    </div>

    <div class="summary-cards">
        <div class="card">
            <h3>総業務数</h3>
            <div style="font-size: 24px; font-weight: bold;">{data['stats']['total_operations']}件</div>
        </div>
        <div class="card">
            <h3>完了率</h3>
            <div style="font-size: 24px; font-weight: bold;">{data['stats']['completion_rate']}%</div>
        </div>
        <div class="card">
            <h3>指摘事項</h3>
            <div style="font-size: 24px; font-weight: bold;">{data['stats']['operations_with_issues']}件</div>
        </div>
        <div class="card">
            <h3>担当業者</h3>
            <div style="font-size: 24px; font-weight: bold;">{data['stats']['companies_count']}社</div>
        </div>
    </div>

    <div class="section">
        <div class="section-header">業務実施状況</div>
        <div class="content">
            <table>
                <thead>
                    <tr>
                        <th>業務名</th>
                        <th>実施日</th>
                        <th>担当会社</th>
                        <th>ステータス</th>
                        <th>備考</th>
                    </tr>
                </thead>
                <tbody>
"""
    
    # 業務データを追加
    for _, row in data['operations'].iterrows():
        html_content += f"""
                    <tr>
                        <td>{row.get('業務名', '')}</td>
                        <td>{row.get('日付', '')}</td>
                        <td>{row.get('担当会社', '')}</td>
                        <td>{row.get('ステータス', '')}</td>
                        <td>{row.get('メモ', '')}</td>
                    </tr>
"""
    
    html_content += """
                </tbody>
            </table>
        </div>
    </div>
"""
    
    # AI分析結果を追加
    if analysis_results:
        html_content += """
    <div class="section">
        <div class="section-header">AI分析による指摘事項</div>
        <div class="content">
"""
        
        for result in analysis_results:
            if 'issues_found' in result and result['issues_found']:
                html_content += f"<h4>{result.get('filename', '不明ファイル')}</h4><table><thead><tr><th>指摘事項</th><th>重要度</th><th>推奨対応</th></tr></thead><tbody>"
                
                for issue in result['issues_found']:
                    severity = issue.get('severity', '')
                    css_class = 'urgent' if severity == '緊急' else ('important' if severity == '重要' else '')
                    html_content += f"""
                    <tr class="{css_class}">
                        <td>{issue.get('issue_description', '')}</td>
                        <td>{severity}</td>
                        <td>{issue.get('recommended_action', '')}</td>
                    </tr>
"""
                
                html_content += "</tbody></table>"
        
        html_content += "</div></div>"
    
    html_content += """
</body>
</html>
"""
    
    return html_content

# メインアプリケーション
def main():
    st.title("月次業務報告レポート自動生成システム")
    
    # 依存関係チェック
    if not check_dependencies():
        st.stop()
    
    # サイドバー設定
    with st.sidebar:
        st.header("設定")
        api_key = st.text_input("Anthropic API KEY", type="password")
        report_month = st.text_input("対象月", value="2025年7月度")
        property_name = st.text_input("物件名", value="グリーンオーク茅場町")
        client_name = st.text_input("発注者", value="双日ライフワン株式会社")
    
    # ファイルアップロード
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("業務データ (CSV)")
        csv_file = st.file_uploader("CSVファイル", type=['csv'])
    
    with col2:
        st.subheader("点検報告書")
        
        # PDF分析オプション
        analysis_option = st.radio(
            "分析方法を選択:",
            ["PDFアップロード", "手動入力", "スキップ"]
        )
        
        text_data = []
        
        if analysis_option == "PDFアップロード" and PDF_AVAILABLE:
            pdf_files = st.file_uploader(
                "PDFファイル（最大10件）", 
                type=['pdf'], 
                accept_multiple_files=True,
                help="一度に処理できるPDFファイルは最大10件までです"
            )
            
            if pdf_files:
                # ファイル数制限チェック
                if len(pdf_files) > 10:
                    st.error(f"ファイル数が上限を超えています。選択されたファイル: {len(pdf_files)}件 / 上限: 10件")
                    st.info("10件以下になるようにファイルを選択し直してください。")
                    pdf_files = pdf_files[:10]  # 最初の10件のみ使用
                    st.warning("最初の10件のみ処理します。")
                
                st.info(f"選択されたファイル: {len(pdf_files)}件")
                
                # ファイル一覧表示
                with st.expander("選択ファイル一覧"):
                    for i, pdf_file in enumerate(pdf_files, 1):
                        file_size = len(pdf_file.getvalue()) / (1024 * 1024)  # MB
                        st.write(f"{i}. {pdf_file.name} ({file_size:.1f}MB)")
                
                # テキスト抽出処理
                for pdf_file in pdf_files:
                    text = extract_text_from_pdf_safe(pdf_file)
                    if text:
                        text_data.append({"text": text, "filename": pdf_file.name})
        
        elif analysis_option == "手動入力":
            text_data = manual_pdf_input()
    
    # データ処理
    if csv_file:
        processed_data = process_csv_data(csv_file)
        
        if processed_data:
            # 統計表示
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("総業務数", f"{processed_data['stats']['total_operations']}件")
            with col2:
                st.metric("完了率", f"{processed_data['stats']['completion_rate']}%")
            with col3:
                st.metric("指摘事項", f"{processed_data['stats']['operations_with_issues']}件")
            with col4:
                st.metric("担当業者", f"{processed_data['stats']['companies_count']}社")
            
            # テキスト分析
            analysis_results = []
            if text_data and api_key:
                st.subheader("AI分析実行中...")
                for item in text_data:
                    with st.spinner(f"分析中: {item['filename']}"):
                        result = analyze_text_with_anthropic_safe(item['text'], item['filename'], api_key)
                        if result:
                            result['filename'] = item['filename']
                            analysis_results.append(result)
            elif text_data:
                st.info("API KEYが設定されていません。簡易分析を実行します。")
                for item in text_data:
                    result = simple_keyword_analysis(item['text'], item['filename'])
                    result['filename'] = item['filename']
                    analysis_results.append(result)
            
            # 分析結果表示
            if analysis_results:
                st.subheader("分析結果")
                for result in analysis_results:
                    with st.expander(f"📄 {result['filename']}"):
                        if 'issues_found' in result and result['issues_found']:
                            issues_df = pd.DataFrame(result['issues_found'])
                            st.dataframe(issues_df)
                        
                        if 'urgent_items' in result and result['urgent_items']:
                            st.subheader("緊急対応事項")
                            for urgent in result['urgent_items']:
                                st.error(f"🚨 {urgent['item']}")
            
            # レポート生成
            st.markdown("---")
            if st.button("📄 レポート生成", type="primary"):
                html_report = generate_original_style_html_report(
                    processed_data, report_month, property_name, client_name, analysis_results
                )
                
                filename = f"{report_month}_{property_name}_月次レポート.html"
                b64 = base64.b64encode(html_report.encode('utf-8')).decode()
                href = f'<a href="data:text/html;base64,{b64}" download="{filename}">📄 レポートダウンロード</a>'
                st.markdown(href, unsafe_allow_html=True)
                
                st.subheader("📋 元のデザインで生成されたレポート")
                st.components.v1.html(html_report, height=800, scrolling=True)

if __name__ == "__main__":
    main()
