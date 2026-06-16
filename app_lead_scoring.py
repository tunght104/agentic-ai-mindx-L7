import streamlit as st
import pandas as pd
import google.generativeai as genai
import requests
import io
import json
import os
from dotenv import load_dotenv

# Tự động đồng bộ credentials.json sang .streamlit/secrets.toml nếu chạy ở local
if os.path.exists("credentials.json") and not os.path.exists(".streamlit/secrets.toml"):
    try:
        os.makedirs(".streamlit", exist_ok=True)
        with open("credentials.json", "r", encoding="utf-8") as f:
            creds = json.load(f)
        toml_content = "[connections.gsheets]\n"
        for k, v in creds.items():
            if k == "private_key":
                toml_content += f'private_key = """{v}"""\n'
            elif isinstance(v, str):
                escaped_v = v.replace('"', '\\"')
                toml_content += f'{k} = "{escaped_v}"\n'
            else:
                toml_content += f'{k} = {json.dumps(v)}\n'
        with open(".streamlit/secrets.toml", "w", encoding="utf-8") as f:
            f.write(toml_content)
    except Exception as e:
        pass

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
def load_data_from_url(sheet_url):
    """Downloads data from Google Sheet URL using Streamlit's official GSheetsConnection."""
    from streamlit_gsheets import GSheetsConnection
    conn = st.connection("gsheets", type=GSheetsConnection)
    return conn.read(spreadsheet=sheet_url, ttl=0)

def write_data_to_url(sheet_url, df_scored):
    """Writes the scored data back to the Google Sheet URL."""
    from streamlit_gsheets import GSheetsConnection
    conn = st.connection("gsheets", type=GSheetsConnection)
    conn.update(spreadsheet=sheet_url, data=df_scored)

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

def keyword_scoring(description):
    """Rule-based scoring based on keywords (Fast Mode)."""
    score = 0
    reasons = []
    description = str(description).lower()
    
    # VIP Keywords
    vip_keywords = {
        "20 tỷ": "Ngân sách lớn (>= 20 tỷ)",
        "tài chính mạnh": "Tài chính mạnh",
        "không thành vấn đề": "Ngân sách linh hoạt",
        "biệt thự": "Loại hình cao cấp (Biệt thự)",
        "penthouse": "Loại hình cao cấp (Penthouse)",
        "shophouse": "Loại hình cao cấp (Shophouse)",
        "đất công nghiệp": "Quỹ đất lớn",
        "văn phòng": "Diện tích văn phòng lớn",
        "quận 1": "Vị trí đắc địa (Quận 1)",
        "ven sông": "Vị trí đắc địa (Ven sông)",
        "vinhomes": "Vị trí đắc địa (Vinhomes)",
        "phú mỹ hưng": "Vị trí đắc địa (Phú Mỹ Hưng)",
        "chủ doanh nghiệp": "Đối tượng khách hàng VIP",
        "nhà đầu tư": "Nhà đầu tư chuyên nghiệp",
        "mua sỉ": "Mua sỉ/số lượng lớn",
        "pháp lý chuẩn": "Yêu cầu pháp lý minh bạch",
        "sổ hồng": "Có sổ hồng riêng",
        "đàm phán": "Thiện chí gặp trực tiếp"
    }
    
    # Trash Keywords
    trash_keywords = {
        "nhầm số": "Nhầm số/Dữ liệu cũ",
        "không có nhu cầu": "Không có nhu cầu thực",
        "dữ liệu cũ": "Dữ liệu cũ",
        "hỏi giá cho vui": "Không thiện chí",
        "chưa có ý định mua": "Chưa có ý định mua",
        "bảo hiểm": "Spam/Quảng cáo bảo hiểm",
        "vay vốn": "Spam/Quảng cáo vay vốn",
        "thuê bao": "Không liên lạc được",
        "không bắt máy": "Không liên lạc được",
        "không phản hồi": "Không phản hồi Zalo/SĐT"
    }

    found_vip = [v for k, v in vip_keywords.items() if k in description]
    found_trash = [v for k, v in trash_keywords.items() if k in description]

    if found_vip:
        score += 50
        reasons.extend(found_vip)
    if found_trash:
        score -= 50
        reasons.extend(found_trash)
    
    category = "VIP" if score >= 50 else "Trash" if score <= -50 else "Potential"
    reasoning = ", ".join(reasons) if reasons else "Nhu cầu cơ bản / Cần tư vấn thêm"
    
    return {"score": score, "category": category, "reasoning": reasoning}

# Sidebar - Settings
st.sidebar.title("⚙️ Cấu hình")
api_key = st.sidebar.text_input("Gemini API Key", type="password", value=os.getenv("GEMINI_API_KEY", ""))
if not api_key:
    st.sidebar.info("💡 Điền Gemini API Key ở trên để sử dụng mô hình AI. Nếu không điền, bạn vẫn có thể sử dụng chế độ chấm điểm bằng Từ khóa (Rule-based).")

# Main UI
st.title("🏡 Real Estate Lead Scoring AI")
st.markdown("Hệ thống tự động đánh giá và phân loại khách hàng tiềm năng bằng trí tuệ nhân tạo.")

# Step 1: Load and Preview Data
st.subheader("1. Dữ liệu khách hàng")

# Cho phép chọn nguồn dữ liệu (Google Sheet hoặc tải tệp trực tiếp)
data_source = st.radio("Chọn nguồn nhập dữ liệu khách hàng:", ["Google Sheet Link", "Tải lên tệp CSV/Excel từ máy tính"], horizontal=True)

if data_source == "Google Sheet Link":
    sheet_url = st.text_input("Nhập Google Sheet URL:", 
                             value="https://docs.google.com/spreadsheets/d/1PtYHhTapnRp8bOVYCxkAaEb37G_7iva99xnmoO-lvG0/edit?usp=sharing")
    if st.button("📥 Tải dữ liệu từ Google Sheet"):
        try:
            df = load_data_from_url(sheet_url)
            st.session_state['df_leads'] = df
            if 'scored_df' in st.session_state:
                del st.session_state['scored_df']
            st.success(f"Đã tải {len(df)} khách hàng thành công từ Google Sheet!")
        except Exception as e:
            st.error(f"Lỗi khi tải dữ liệu từ Google Sheet: {e}")
else:
    uploaded_file = st.file_uploader("Tải lên tệp danh sách khách hàng (chấp nhận .csv, .xlsx):", type=["csv", "xlsx"])
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            st.session_state['df_leads'] = df
            if 'scored_df' in st.session_state:
                del st.session_state['scored_df']
            st.success(f"Đã tải {len(df)} khách hàng thành công từ tệp của bạn!")
        except Exception as e:
            st.error(f"Lỗi khi tải dữ liệu từ tệp tin: {e}")

if 'df_leads' in st.session_state:
    st.dataframe(st.session_state['df_leads'], use_container_width=True)

    # Step 2: Scoring
    st.divider()
    st.subheader("2. Chấm điểm")
    
    col1, col2 = st.columns(2)
    with col1:
        use_ai = st.toggle("Sử dụng AI (Cần Gemini Key)", value=True)
    with col2:
        start_button = st.button("🚀 Bắt đầu chấm điểm")
    
    if start_button:
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        total = len(st.session_state['df_leads'])

        if use_ai:
            if not api_key:
                st.error("❌ Vui lòng nhập Gemini API Key để sử dụng chế độ AI.")
                st.stop()
            genai.configure(api_key=api_key)
            skill_content = load_scoring_skill()
            model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                system_instruction=f"You are a professional Lead Scoring Assistant for Real Estate. Use the following criteria:\n\n{skill_content}"
            )
        
        for i, (index, row) in enumerate(st.session_state['df_leads'].iterrows()):
            status_text.text(f"Đang xử lý: {row['ten_khach']} ({i+1}/{total})")
            
            if use_ai:
                score_result = score_lead(model, row)
            else:
                score_result = keyword_scoring(row['nhu_cau_mo_ta'])
            
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
        st.success("✅ Đã hoàn thành chấm điểm!")

    if 'scored_df' in st.session_state:
        st.subheader("📊 Kết quả phân loại")
        
        # Add color coding to Category
        def color_category(val):
            color = '#ff4b4b' if val == 'Trash' else '#28a745' if val == 'VIP' else '#ffa500'
            return f'color: {color}; font-weight: bold'
        
        st.dataframe(st.session_state['scored_df'].style.map(color_category, subset=['Category']), use_container_width=True)
        
        # Step 3: Export
        st.divider()
        st.subheader("3. Xuất dữ liệu")
        
        # Create Excel in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            st.session_state['scored_df'].to_excel(writer, index=False, sheet_name='Scored Leads')
        
        excel_data = output.getvalue()
        
        if data_source == "Google Sheet Link":
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    label="📥 Tải về file Excel kết quả",
                    data=excel_data,
                    file_name="leads_scored_results.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            with col2:
                if st.button("🔄 Đồng bộ kết quả trực tiếp về Google Sheet"):
                    with st.spinner("Đang đồng bộ dữ liệu về Google Sheet..."):
                        try:
                            write_data_to_url(sheet_url, st.session_state['scored_df'])
                            st.success("✅ Đã đồng bộ kết quả lên Google Sheet thành công!")
                        except Exception as e:
                            st.error(f"❌ Lỗi khi đồng bộ: {e}")
        else:
            st.download_button(
                label="📥 Tải về file Excel kết quả",
                data=excel_data,
                file_name="leads_scored_results.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
else:
    st.info("Nhấn nút 'Tải dữ liệu' để bắt đầu.")
