import streamlit as st
import pandas as pd
import google.generativeai as genai
import requests
import io
import json
import os
from dotenv import load_dotenv

# Page configuration
st.set_page_config(page_title="Real Estate Lead Scoring AI", page_icon="🏡", layout="wide")

# Load CSS for better aesthetics
st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        background-color: #007bff;
        color: white;
    }
    .stDownloadButton>button {
        width: 100%;
        background-color: #28a745;
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)

# Helper Functions
def get_csv_url(url):
    """Converts a standard Google Sheet URL to a CSV export URL."""
    if "/edit" in url:
        return url.split("/edit")[0] + "/export?format=csv"
    return url

def load_scoring_skill():
    """Loads the scoring criteria from the markdown file."""
    try:
        with open("lead_scoring_skill.md", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "Scoring criteria file not found. Please ensure lead_scoring_skill.md exists."

def score_lead(model, lead_data):
    """Sends a single lead to Gemini for scoring."""
    lead_json = lead_data.to_json()
    prompt = f"Evaluate this lead and return a JSON object as specified in the instructions:\n{lead_json}"
    
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text)
    except Exception as e:
        return {"id": lead_data.get("id"), "score": 0, "category": "Error", "reasoning": str(e)}

# Sidebar - Settings
st.sidebar.title("⚙️ Cấu hình")
api_key = st.sidebar.text_input("Gemini API Key", type="password", value=os.getenv("GEMINI_API_KEY", ""))
sheet_url = st.sidebar.text_input("Google Sheet URL", value="https://docs.google.com/spreadsheets/d/1PtYHhTapnRp8bOVYCxkAaEb37G_7iva99xnmoO-lvG0/edit?usp=sharing")

# Main UI
st.title("🏡 Real Estate Lead Scoring AI")
st.markdown("Hệ thống tự động đánh giá và phân loại khách hàng tiềm năng bằng trí tuệ nhân tạo.")

if not api_key:
    st.warning("⚠️ Vui lòng nhập Gemini API Key ở thanh bên để bắt đầu.")
    st.stop()

# Step 1: Load and Preview Data
st.subheader("1. Dữ liệu khách hàng")
if st.button("📥 Tải dữ liệu từ Google Sheet"):
    try:
        csv_url = get_csv_url(sheet_url)
        response = requests.get(csv_url)
        response.raise_for_status()
        df = pd.read_csv(io.StringIO(response.text))
        st.session_state['df_leads'] = df
        st.success(f"Đã tải {len(df)} khách hàng thành công!")
    except Exception as e:
        st.error(f"Lỗi khi tải dữ liệu: {e}")

if 'df_leads' in st.session_state:
    st.dataframe(st.session_state['df_leads'], use_container_width=True)

    # Step 2: Scoring
    st.divider()
    st.subheader("2. Chấm điểm AI")
    
    if st.button("🚀 Bắt đầu chấm điểm bằng AI"):
        # Setup Gemini
        genai.configure(api_key=api_key)
        skill_content = load_scoring_skill()
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=f"You are a professional Lead Scoring Assistant for Real Estate. Use the following criteria:\n\n{skill_content}"
        )
        
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        total = len(st.session_state['df_leads'])
        for i, (index, row) in enumerate(st.session_state['df_leads'].iterrows()):
            status_text.text(f"Đang xử lý: {row['ten_khach']} ({i+1}/{total})")
            score_result = score_lead(model, row)
            
            # Combine original data with results
            combined = row.to_dict()
            combined.update({
                "Score": score_result.get("score"),
                "Category": score_result.get("category"),
                "Reasoning": score_result.get("reasoning")
            })
            results.append(combined)
            progress_bar.progress((i + 1) / total)
            
        st.session_state['scored_df'] = pd.DataFrame(results)
        st.success("✅ Đã hoàn thành chấm điểm tất cả khách hàng!")

    if 'scored_df' in st.session_state:
        st.subheader("📊 Kết quả phân loại")
        
        # Add color coding to Category
        def color_category(val):
            color = '#ff4b4b' if val == 'Trash' else '#28a745' if val == 'VIP' else '#ffa500'
            return f'color: {color}; font-weight: bold'
        
        st.dataframe(st.session_state['scored_df'].style.applymap(color_category, subset=['Category']), use_container_width=True)
        
        # Step 3: Export
        st.divider()
        st.subheader("3. Xuất dữ liệu")
        
        # Create Excel in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            st.session_state['scored_df'].to_excel(writer, index=False, sheet_name='Scored Leads')
        
        excel_data = output.getvalue()
        
        st.download_button(
            label="📥 Tải về file Excel kết quả",
            data=excel_data,
            file_name="leads_scored_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
else:
    st.info("Nhấn nút 'Tải dữ liệu' để bắt đầu.")
