# Skill: Lead Scoring for Real Estate

## Overview
This skill evaluates the quality of real estate leads based on their stated requirements and descriptions. It helps prioritize high-potential investors and filter out low-quality or irrelevant data.

## Input Data Structure
The skill expects a lead object with the following fields:
- `id`: Unique identifier for the lead.
- `ten_khach`: Customer name.
- `sdt`: Phone number.
- `nhu_cau_mo_ta`: Detailed description of the customer's needs and context.

## Scoring Logic
The scoring process starts with a base score of **0**.

### 1. VIP / High Potential Criteria (+50 Points)
Award +50 points if the `nhu_cau_mo_ta` matches any of the following:
- **High Budget**: Explicit mention of budget ≥ 20 billion VND or phrases like "tài chính mạnh" (strong finance), "không thành vấn đề" (budget is not an issue).
- **Premium Property Types**: Searching for "Biệt thự đơn lập" (detached villas), "Penthouse", "Shophouse mặt đường lớn" (main road shophouses), "Quỹ đất công nghiệp" (industrial land), or "Sàn văn phòng diện tích lớn" (large office space).
- **Prime Locations**: Requests for "Quận 1", "Ven sông" (riverside), "Vinhomes Ocean Park", "Phú Mỹ Hưng".
- **High-Value Personas**: Mentioned as "Chủ doanh nghiệp" (business owner), "Nhà đầu tư chuyên nghiệp" (professional investor), "Mua sỉ" (bulk buyer), "Mua số lượng lớn".
- **Urgency & Transparency**: Requests for "Pháp lý chuẩn 100%" (100% legal), "Sổ hồng riêng" (private pink book), or "Muốn gặp trực tiếp chủ đầu tư để đàm phán" (wants to meet developer directly).

### 2. Trash / Low Potential Criteria (-50 Points)
Deduct -50 points if the `nhu_cau_mo_ta` matches any of the following:
- **Unrealistic Expectations**: Price points significantly below market value (e.g., District 1 house for 1-2 billion VND, central house with pool for few hundred million).
- **No Intent/Wrong Data**: Mentions of "Nhầm số" (wrong number), "Không có nhu cầu" (no demand), "Dữ liệu cũ" (old data), "Nhầm ngành" (wrong industry).
- **Uncooperative**: "Hỏi giá cho vui" (asking for fun), "Chưa có ý định mua" (no intent to buy), "Thái độ không hợp tác" (uncooperative attitude).
- **Spam/Promotion**: Content related to other services like "Bảo hiểm" (insurance), "Vay vốn" (loans), or general service solicitations.
- **Contact Issues**: "Thuê bao" (out of service), "Gọi nhiều lần không bắt máy" (no answer), "Không phản hồi Zalo" (no Zalo response).

### 3. Neutral / Standard Criteria (0 - 10 Points)
Maintain or slightly increase score for standard requests:
- Standard apartments or townhouses (3-10 billion VND).
- Customers needing bank loans or inquiring about policies.
- Real interest but requiring further legal or location consultation.

## Output Format
The output must be a JSON object:
```json
{
  "id": "string",
  "score": integer,
  "category": "VIP" | "Potential" | "Trash",
  "reasoning": "Brief explanation of why this score was given based on keywords identified."
}
```

## Categorization Thresholds
- **Score >= 50**: VIP
- **0 <= Score < 50**: Potential
- **Score < 0**: Trash
