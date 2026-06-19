import streamlit as st
import pandas as pd
import json
import os
import re
import time
import requests
from PIL import Image
import io
import concurrent.futures
from google import genai
from google.genai import types

# --- CẤU HÌNH TRANG & BẢO MẬT ---
st.set_page_config(layout="wide", page_title="Amazon IT Script Gen (v2Pro)")

def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if not st.session_state["password_correct"]:
        st.title("🔒 Cổng Đăng Nhập Hệ Thống - Thị Trường Ý 🇮🇹")
        pwd = st.text_input("Nhập mật khẩu truy cập:", type="password")
        if st.button("Đăng nhập"):
            if pwd == st.secrets["APP_PASSWORD"]: 
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Mật khẩu không chính xác!")
        st.stop()
    return True

check_password()

# --- CẤU HÌNH API ---
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
MODEL_ID = "gemini-3-flash-preview"
PRO_MODEL_ID = "gemini-pro-latest"

# --- BIẾN NỘI BỘ & PROMPTS (Dành cho thị trường Ý) ---
PERSONA_DICT = {
    "L'Appassionato Verace (Chiến thần nhiệt huyết)": "Năng lượng cực cao, nói chuyện bằng cả tay lẫn miệng (phong cách Ý đặc trưng). Cực kỳ đam mê công nghệ/đồ gia dụng, khen chê rõ ràng, non nể nang. Hay dùng từ lóng mạnh, biểu cảm sống động. Rất quan tâm đến thiết kế (Design) và hiệu năng.",
    "Il Cacciatore di Affari (Thánh săn sale)": "Thực tế, chi li. Trọng tâm là 'Rapporto qualità-prezzo' (Tỷ lệ P/P). Ghét lãng phí tiền bạc vào những tính năng vô bổ. Giọng điệu nhanh nhạy, thân thiện như một người bạn mách nước.",
    "L'Esteta (Chuyên gia Thẩm mỹ)": "Giọng điệu điềm tĩnh, sang trọng. Người Ý rất coi trọng thiết kế. Nhân vật này sẽ chê thẳng tay những sản phẩm 'xấu xúc phạm người nhìn' dù thông số tốt, ưu tiên sự hòa hợp với không gian sống.",
    "L'Esaminatore Pignolo (Chuyên gia Bắt bẻ)": "Kỹ tính, soi mói từng lỗi nhỏ (chất lượng nhựa, tiếng ồn, viền màn hình). Tạo độ tin cậy cực cao vì một khi nhân vật này đã khen thì sản phẩm đó chắc chắn là hàng tuyển."
}

MEME_VAULT = [
    # Khen ngợi / Chốt sale
    "Mamma mia, che bomba! (Trời ơi, đỉnh chóp!)",
    "Poca spesa, tanta resa. (P/P vô địch, ngon bổ rẻ.)",
    "Un vero affare, non fatevelo scappare. (Kèo thơm thực sự, đừng bỏ lỡ.)",
    "Esteticamente è un capolavoro. (Giao diện chuẩn hoa hậu.)",
    "Costa un occhio della testa, ma li vale tutti. (Hơi đau ví nhưng đáng từng xu.)",
    "Cambia la vita, letteralmente. (Nó thay đổi cuộc sống luôn, thề.)",
    "Rapporto qualità-prezzo spaziale. (P/P ở cái tầm vũ trụ.)",
    "A questo prezzo è regalato! (Giá này thì khác gì vừa bán vừa cho!)",
    "Se non lo comprate, peggio per voi. (Không mua thì ráng chịu thiệt thôi.)",
    
    # Chê bai / Tạo Trust
    "Una cinesata pazzesca, lasciate perdere. (Hàng rác rưởi, bỏ đi anh em.)",
    "Esteticamente è un pugno nell'occhio. (Thiết kế đúng kiểu đấm vào mắt người xem.)",
    "Sulla carta sembra perfetto, ma... (Trên giấy tờ thì ngon đấy, ma...)",
    "Non ci piove, ha i suoi difetti. (Không phải bàn cãi, nó có nhược điểm rõ ràng.)",
    "I materiali? Insomma... (Chất liệu hả? Ờ thì... hên xui...)",
    "Onestamente, mi aspettavo di più. (Nói thật, tôi đã kỳ vọng nhiều hơn.)",
    "Un po' troppo rumoroso per i miei gusti. (Hơi ồn ào quá so với gu của tôi.)",
    "Il software fa i capricci. (Phần mềm cứ chập cheng kiểu gì ấy.)"
]

P1_TEMPLATE = """AMAZON ITALY SEO & KEYWORD ANALYST
Bối cảnh: Tôi sẽ gửi tệp dữ liệu từ khóa (.CSV). Bạn hãy lọc bộ từ khóa "Hái ra tiền" (Money Keywords) tối ưu nhất cho kịch bản Video Review Affiliate Amazon Ý (Amazon.it).
Thông tin dự án:
- Sản phẩm: {seed_keywords}
- Ngôn ngữ: Ưu tiên Tiếng Ý (Italian).
- Hiện tại là năm 2026, tên kênh review youtube: Shopping Intelligente

YÊU CẦU LỌC TỪ KHÓA:
1. Gộp, lọc trùng, chuyển Volume về số nguyên. CHỈ GIỮ LẠI TỪ KHÓA TIẾNG Ý. Tuyệt đối không để lọt ngôn ngữ khác.
2. Giữ trọn vẹn các từ khóa dài (Long-tail keywords), đặc biệt là tên model chi tiết vì đây là người mua có ý định chốt đơn cao.
3. Bộ lọc Ý định "Chốt Sale & Bắt Trend" kiểu Ý:
- ƯU TIÊN TỐI ĐA từ khóa mua hàng: "miglior", "recensione", "confronto", "qualità prezzo", "economico", "come scegliere".
- CHUYỂN HÓA NỖI ĐAU: GIỮ LẠI từ khóa vấn đề: "problema", "non funziona", "durata batteria", "rumoroso".
- CHỈ LOẠI BỎ: Từ khóa tìm đồ cũ (usato, subito.it) hoặc sàn đối thủ (ebay, eprice).
4. Bộ lọc Thương hiệu: Giữ lại từ khóa kết hợp [Brand] + [Product].

Dữ liệu đầu vào:
{csv_data}

YÊU CẦU ĐẦU RA (TRẢ VỀ JSON):
{
    "detected_brands": ["brand1", "brand2"],
    "keywords": [ {"keyword": "parola chiave in italiano", "volume": 1000} ]
}"""

P2_TEMPLATE = """Phân tích chéo dữ liệu Amazon Ý (Amazon.it) và từ khóa để chọn Top 15 sản phẩm tốt nhất.
Tiêu chí:
1. Đa dạng phổ giá.
2. Ưu tiên có Rating > 4.0 và số lượng review cao.
3. THƯƠNG HIỆU: LOẠI BỎ các sản phẩm có tên thương hiệu rác, ký tự vô nghĩa (tránh hàng cinesata). CHỈ CHỌN thương hiệu uy tín hoặc đọc được tên.
4. Tối ưu SEO: Khớp với từ khóa tiếng Ý có Volume cao.

Dữ liệu Amazon: {amazon_data}
Từ khóa: {keywords_json}

YÊU CẦU ĐẦU RA (JSON):
{
    "top_15": [
        {
            "asin": "...", 
            "name": "...", 
            "url": "https://www.amazon.it/dp/...", 
            "price": "...", 
            "rating": "...", 
            "reason": "Lý do chọn bằng tiếng Việt",
            "relevant_keywords": ["parola chiave 1", "parola chiave 2"]
        }
    ]
}"""

P3_TEMPLATE = """Đóng vai Giám khảo chuyên môn. Đọc chi tiết features, giá và review của 15 sản phẩm Amazon Ý để chọn ra ĐÚNG 5 SẢN PHẨM XUẤT SẮC NHẤT.

TIÊU CHÍ LỰA CHỌN BẮT BUỘC:
1. Phân bổ vai trò: 1 [Migliore in Assoluto] (Best Overall), 1 [Scelta Premium] (Premium), 1 [Miglior Qualità-Prezzo] (Value for Money), và 2 [Alternative/Economico] (Alternative).
2. Hệ thống chấm điểm ngầm: Người Ý cực kỳ khắt khe về 'Qualità costruttiva' (Độ hoàn thiện) và 'Estetica' (Thiết kế). Dựa vào mục Review Summary, LOẠI BỎ ngay các sản phẩm bị chê tơi tả về việc dễ hỏng hoặc quá xấu. CHỈ CHỌN sản phẩm có tỷ lệ Khen/Chê > 80%.
3. ĐA DẠNG THƯƠNG HIỆU: Không để 1 thương hiệu chiếm quá 2 vị trí.

Dữ liệu sản phẩm: {scraped_data}
(Viết một đoạn reasoning ngắn bằng tiếng Việt giải thích lý do loại trừ/chọn trước khi xuất JSON).
TRẢ VỀ JSON:
{
    "top_5_alternative_1": "Mã_ASIN_5",
    "top_4_alternative_2": "Mã_ASIN_4",
    "top_3_value_for_money": "Mã_ASIN_3",
    "top_2_premium": "Mã_ASIN_2",
    "top_1_best_overall": "Mã_ASIN_1",
    "reasoning": "Giải thích..."
}"""

P4_TEMPLATE = """# YouTube Script Generation Prompt - ITALIAN MARKET

Generate a highly engaging YouTube script (6-8 minutes) for a TOP X product ranking video on Amazon Italy.

## CRITICAL RULES
- **ABSOLUTELY NO JAPANESE OR VIETNAMESE WORDS IN THE SCRIPT OUTPUT.** The output MUST be 100% in Italian (except for the section tags like <intro>, title:, description: which remain as is).
- **Target Audience:** Italian consumers.

## INPUT
- **Product Category**: {seed_keywords}
- **Product Count**: 5 products
- **Language**: Italian (Conversational, dynamic, passionate. Use "Ragazzi" or "Amici". Mix casual expressions).
- **Persona**: {selected_persona} (Traits: {persona_traits})
{meme_instruction}
- **Keywords**: {refined_keywords}
- **Tag Candidates**: {tag_candidates_str}
- **Product Data**: {final_5_data}
- **Context**: Year 2026. Channel Name: "Shopping Intelligente"

## TTS EMOTION TAGS
Insert emotion tags in brackets to control the tone:
- `[laugh]` (ironic laugh / finding something funny)
- `[sigh]` (disappointment over a bad feature)
- `[gasp]` (shock at a great price or amazing spec)
- `[emphasis]` (stressing a word)
- `[excited]` (pumping up the energy)
*Rule: Use 1-2 tags max per product section.*

---

## VIDEO STRUCTURE
**Aim for 1800-2200 words total.**

### 1. HOOK & INTRO (100-150 words)
- Use PAS formula. Start with a relatable frustration.
- "Niente filtri, niente sponsorizzazioni fasulle. Solo la verità."

### 2. BUYING GUIDE (150-200 words)
- 2-3 essential tips tailored to Italian expectations.
- **Affiliate Disclosure:** "Prima di iniziare, vi ricordo che tutti i link per controllare i prezzi aggiornati sono in descrizione. Sono link affiliati..."

### 3. PRODUCT REVIEWS (Top 5 to Top 1 - ~250-300 words each)
- **Spec-Story Fusion:** Translate cold specs into real daily life in Italy.
- **The "Ma..." (Limitation + Solution):** Find ONE flaw and give a workaround based on the Product Data (Merits/Demerits).
- **Seamless Transitions.**
- **Pricing & CTA:** DO NOT say exact prices. Use dynamic CTAs:
  + "I prezzi su Amazon ballano sempre, cliccate il link giù in descrizione!"
  + "Controllate il link in basso per sconti attivi!"

### 4. CONCLUSION (100-150 words)
- Quick recap and Call to action.

---

## OUTPUT FORMAT

title:
[MUST contain the main SEO keyword in Italian. Format: [Keyword] - [Hook] - 2026]

description:
Disclaimer: Questa descrizione contiene link di affiliazione. Acquistando tramite questi link, sostieni il canale senza costi aggiuntivi per te. Grazie!

[2-3 introductory sentences in Italian containing primary keywords]

#5. [Brand + Product Name]
- Perché lo consigliamo: [1-2 sentences summarizing in Italian]
👉 Link Amazon: {LINK_5}

#4. [Brand + Product Name]
- Perché lo consigliamo: [1-2 sentences summarizing in Italian]
👉 Link Amazon: {LINK_4}

#3. [Brand + Product Name]
- Perché lo consigliamo: [1-2 sentences summarizing in Italian]
👉 Link Amazon: {LINK_3}

#2. [Brand + Product Name]
- Perché lo consigliamo: [1-2 sentences summarizing in Italian]
👉 Link Amazon: {LINK_2}

#1. [Brand + Product Name]
- Perché lo consigliamo: [1-2 sentences summarizing in Italian]
👉 Link Amazon: {LINK_1}

[Outro & Call to action in Italian]
Hashtags: [3-5 hashtags in Italian]

tags: 
[Comma-separated Italian keywords. Max 460 chars]

script:
[DO NOT FORGET EMOTION TAGS]

<intro>
[Italian content]

<buying_guide>
[Italian content]

<top5>
[Italian content]

<top4>
[Italian content]

<top3>
[Italian content]

<top2>
[Italian content]

<top1>
[Italian content]

<outro>
[Italian content]
"""

# --- HÀM HỖ TRỢ CHUNG ---
def clean_and_parse_json(ai_text):
    text = ai_text.strip()
    text = re.sub(r'^```(json)?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*
```$', '', text)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find('{')
        if start != -1:
            stack = 0
            for i in range(start, len(text)):
                if text[i] == '{': stack += 1
                elif text[i] == '}':
                    stack -= 1
                    if stack == 0:
                        try: return json.loads(text[start:i+1])
                        except: break
        raise ValueError(f"Lỗi bóc tách JSON.")

def call_gemini_with_retry(contents, response_mime_type=None, max_retries=3, target_model=MODEL_ID):
    delay = 3
    for attempt in range(max_retries):
        try:
            if response_mime_type:
                return client.models.generate_content(
                    model=target_model, contents=contents, 
                    config=types.GenerateContentConfig(response_mime_type=response_mime_type)
                )
            return client.models.generate_content(model=target_model, contents=contents)
        except Exception as e:
            if "503" in str(e) or "429" in str(e) or "quota" in str(e).lower():
                if attempt < max_retries - 1:
                    time.sleep(delay)
                    delay *= 2
                else: raise e
            else: raise e

# --- HÀM XỬ LÝ DỮ LIỆU ---
def parse_amazon_md_search(md_texts):
    """Đọc file MD của trang kết quả tìm kiếm (Amazon.it)"""
    products = []
    seen_asins = set()
    for text in md_texts:
        blocks = text.split('## Product')
        for block in blocks[1:]:
            title_match = re.search(r'\*\*Title\*\*: (.*)', block)
            asin_match = re.search(r'\*\*ASIN\*\*: (.*)', block)
            if title_match and asin_match:
                title = title_match.group(1).strip()
                # TỐI ƯU Ý: Lọc bỏ chữ "Annuncio sponsorizzato – " ở các sp quảng cáo
                title = re.sub(r'^Annuncio sponsorizzato\s*[–-]\s*', '', title)
                
                asin = asin_match.group(1).strip()
                if asin not in seen_asins:
                    products.append({
                        "asin": asin, "name": title,
                        "url": f"https://www.amazon.it/dp/{asin}" 
                    })
                    seen_asins.add(asin)
    return products

def clean_md_content(text):
    """Lọc rác siêu chuẩn cho Amazon Italy Markdown"""
    # Xóa khối Chính sách bảo hành & Trả hàng
    text = re.sub(r'### Garanzia legale, diritto di recesso e politica dei resi.*?Resi e rimborsi per articoli Marketplace\.', '', text, flags=re.DOTALL)
    # Xóa khối Feedback báo cáo giá thấp hơn
    text = re.sub(r'### Feedback\nVuoi \*\*segnalarci un prezzo più basso\?\).*?Effettua l\'accesso per rilasciare un feedback\.', '', text, flags=re.DOTALL|re.IGNORECASE)
    text = re.sub(r'## Dove hai trovato questo prodotto a un prezzo più basso\?.*?Effettua l\'accesso per rilasciare un feedback\.', '', text, flags=re.DOTALL|re.IGNORECASE)
    # Xóa metadata rác cuối file
    text = re.sub(r'## Scraped Information.*', '', text, flags=re.DOTALL)
    # Xóa khoảng trắng thừa
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text.strip()

def parse_detailed_md_files(md_contents_list):
    scraped_data = []
    for md_text in md_contents_list:
        try:
            cleaned_text = clean_md_content(md_text)
            
            asin_match = re.search(r'\*\*ASIN\*\*: (.*?)\n', cleaned_text)
            title_match = re.search(r'# (.*?)\n', cleaned_text)
            price_match = re.search(r'\*\*Price\*\*: (.*?)\n', cleaned_text)
            rating_match = re.search(r'\*\*Rating\*\*: (.*?)\n', cleaned_text)
            
            asin = asin_match.group(1).strip() if asin_match else "UNKNOWN"
            title = title_match.group(1).strip() if title_match else "UNKNOWN"
            
            valuable_parts = []
            # TỐI ƯU Ý: Đổi logic bắt các Tag chứa Review chất lượng cao của form mới
            target_sections = [
                "## Basic Information", 
                "## Key Features", 
                "## Specifications", 
                "## Customer Review Summary", 
                "## Review Aspects"
            ]
            for section in target_sections:
                pattern = rf"{section}(.*?)(?=\n## |\Z)"
                match = re.search(pattern, cleaned_text, re.DOTALL)
                if match:
                    valuable_parts.append(f"{section}\n{match.group(1).strip()}")
            
            final_description = "\n\n".join(valuable_parts)
            
            images = []
            img_section = re.search(r'## Description Image Links\n(.*?)(?=\n## |\Z)', cleaned_text, re.DOTALL)
            if img_section:
                images = re.findall(r'- (https://m\.media-amazon\.com[^\s]+)', img_section.group(1))
            
            scraped_data.append({
                "asin": asin,
                "name": title,
                "url": f"https://www.amazon.it/dp/{asin}",
                "price": re.sub(r'~~.*?~~', '', price_match.group(1)).strip() if price_match else "N/A",
                "rating": rating_match.group(1).strip() if rating_match else "N/A",
                "description": final_description,
                "full_text_length": len(final_description),
                "images": images
            })
        except Exception as e:
            st.error(f"Lỗi đọc file MD: {e}")
    return scraped_data

def process_single_ocr(item):
    TEXT_THRESHOLD = 800 
    
    if item['full_text_length'] < TEXT_THRESHOLD:
        st.write(f"🔍 Sản phẩm {item['asin']} có mô tả mỏng. Đang chạy OCR...")
        
        ocr_prompt = """Sei un sistema OCR avanzato.
Compito: Estrai le specifiche tecniche, le caratteristiche e i punti di forza principali dalle immagini del prodotto.
REGOLE:
1. RESTITUISCI IL RISULTATO 100% IN ITALIANO.
2. Usa un elenco puntato breve e conciso. NESSUNA spiegazione aggiuntiva."""
        
        if 'images' in item and len(item['images']) > 0:
            gemini_contents = [ocr_prompt]
            target_images = item['images'][:5]
            has_valid_image = False
            
            for img_url in target_images:
                try:
                    res = requests.get(img_url, timeout=10)
                    if res.status_code == 200:
                        img = Image.open(io.BytesIO(res.content))
                        if img.mode != 'RGB': img = img.convert('RGB')
                        gemini_contents.append(img)
                        has_valid_image = True
                except: pass
            
            if has_valid_image:
                try:
                    ocr_result = call_gemini_with_retry(gemini_contents).text
                    item['description'] += "\n\n[DATI AGGIUNTIVI DALLE IMMAGINI OCR]:\n" + ocr_result
                except Exception as e:
                    st.warning(f"Không thể OCR cho {item['asin']}: {e}")
    return item

# --- GIAO DIỆN CHÍNH ---
st.title("🛠️ Hệ Thống Kịch Bản Amazon Italy (Mamma Mia Edition 🇮🇹)")

with st.sidebar:
    st.header("Cài Đặt Đầu Vào")
    seed_keywords = st.text_input("Từ khóa ngách (Tiếng Ý/Anh):", "macchina da caffè")
    selected_persona = st.selectbox("Chọn Persona Review:", list(PERSONA_DICT.keys()))
    specific_theme = st.text_input("Định hướng ngách cụ thể (Tùy chọn):", placeholder="VD: Per studenti, Design elegante...")
    trending_memes = st.text_input("🔥 Trend/Meme đang hot (Bỏ trống AI tự bốc):", placeholder="VD: che bomba, pazzesco...")
tab1, tab2 = st.tabs(["📌 BƯỚC 1: Lọc 15 Sản Phẩm IT", "✍️ BƯỚC 2: OCR & Viết Kịch Bản IT"])

# ==========================================
# GIAI ĐOẠN 1
# ==========================================
with tab1:
    st.header("Cung cấp tệp tìm kiếm thô (Amazon.it)")
    col1, col2 = st.columns(2)
    with col1:
        vidiq_files = st.file_uploader("1. Tệp Từ khóa VidIQ (.CSV)", type="csv", accept_multiple_files=True)
    with col2:
        md_files_search = st.file_uploader("2. Tệp Kết quả Amazon (.MD)", type="md", accept_multiple_files=True)
        
    if st.button("🚀 Xử lý Bước 1", type="primary"):
        if not vidiq_files or not md_files_search:
            st.warning("Vui lòng upload đủ file CSV và MD Tìm kiếm!")
            st.stop()
            
        with st.status("Đang phân tích Bước 1..."):
            dfs = []
            for file in vidiq_files:
                df_temp = pd.read_csv(file, sep=',', quotechar='"', on_bad_lines='skip')
                col_kw = next((c for c in df_temp.columns if 'keyword' in c.lower() or 'từ khóa' in c.lower()), None)
                col_vol = next((c for c in df_temp.columns if 'volume' in c.lower() or 'search' in c.lower()), None)
                if col_kw and col_vol:
                    df_temp = df_temp[[col_kw, col_vol]].dropna()
                    df_temp.columns = ['Keyword', 'Volume']
                    dfs.append(df_temp)
            vidiq_df = pd.concat(dfs, ignore_index=True).drop_duplicates(subset=['Keyword'])
            csv_data = vidiq_df.to_csv(index=False)
            
            md_texts = [f.getvalue().decode("utf-8", errors="ignore") for f in md_files_search]
            amazon_raw_data = parse_amazon_md_search(md_texts)
            
            st.write("Đang lọc Keyword tiếng Ý...")
            prompt1 = P1_TEMPLATE.replace("{csv_data}", csv_data).replace("{seed_keywords}", seed_keywords)
            res1 = call_gemini_with_retry(prompt1, response_mime_type="application/json")
            keywords_json = clean_and_parse_json(res1.text)
            
            st.write("Đang chọn Top 15 Italy...")
            prompt2 = P2_TEMPLATE.replace("{amazon_data}", json.dumps(amazon_raw_data, ensure_ascii=False)).replace("{keywords_json}", json.dumps(keywords_json, ensure_ascii=False))
            if specific_theme.strip():
                prompt2 += f"\n\nLƯU Ý: Hãy ưu tiên tìm các sản phẩm phù hợp nhất với chủ đề/ngách sau: '{specific_theme}'."
            res2 = call_gemini_with_retry(prompt2, response_mime_type="application/json")
            top_15_json = clean_and_parse_json(res2.text)
            
            st.session_state['saved_keywords'] = keywords_json
            st.session_state['top_15_json'] = top_15_json
            
        st.success("✅ Đã chốt danh sách 15 sản phẩm tối ưu cho Ý! Copy link mở tab lấy MD chi tiết.")
        st.markdown("### 🎯 DANH SÁCH 15 LINK:")
        items_list = top_15_json.get('top_15', []) if isinstance(top_15_json, dict) else top_15_json
        for item in items_list:
            url = item.get('url', '')
            asin = item.get('asin', 'UNKNOWN')
            if url:
                html_link = f'👉 **{asin}**: <a href="{url}" target="_blank">{url}</a>'
                st.markdown(html_link, unsafe_allow_html=True)
            else:
                st.write(f"👉 **{asin}**: Không có URL")

# ==========================================
# GIAI ĐOẠN 2
# ==========================================
with tab2:
    st.header("Xử lý 15 sản phẩm chi tiết")
    detailed_md_files = st.file_uploader("Upload 15 file .MD chi tiết", type="md", accept_multiple_files=True)
    
    if st.button("✨ Chốt Top 5 & Xuất Kịch Bản Tiếng Ý", type="primary"):
        if not detailed_md_files:
            st.warning("Vui lòng upload file MD chi tiết!")
            st.stop()
        if 'saved_keywords' not in st.session_state or 'top_15_json' not in st.session_state:
            st.error("Dữ liệu trống. Vui lòng chạy lại BƯỚC 1 trước!")
            st.stop()
            
        with st.status("Đang phân tích và viết kịch bản phong cách Ý..."):
            md_contents = [f.getvalue().decode("utf-8", errors="ignore") for f in detailed_md_files]
            scraped_details = parse_detailed_md_files(md_contents)
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                scraped_details = list(executor.map(process_single_ocr, scraped_details))
                
            st.write("Giám khảo AI chấm điểm Top 5...")
            prompt3 = P3_TEMPLATE.replace("{scraped_data}", json.dumps(scraped_details, ensure_ascii=False))
            if specific_theme.strip():
                prompt3 += f"\n\nLƯU Ý TỪ ĐẠO DIỄN: Tiêu chí cốt lõi để chọn Top 5 là bám sát chủ đề: '{specific_theme}'."
            res3 = call_gemini_with_retry(prompt3, response_mime_type="application/json", target_model=PRO_MODEL_ID)
            top5_decision = clean_and_parse_json(res3.text)
            
            if isinstance(top5_decision, list): top5_decision = top5_decision[0]
            
            selected_asins = [
                top5_decision.get('top_5_alternative_1'), top5_decision.get('top_4_alternative_2'),
                top5_decision.get('top_3_value_for_money'), top5_decision.get('top_2_premium'),
                top5_decision.get('top_1_best_overall')
            ]
            selected_asins = [asin for asin in selected_asins if asin]
            
            final_5_data = []
            rank_labels = ["Top 5", "Top 4", "Top 3", "Top 2", "Top 1"]
            for idx, asin in enumerate(selected_asins):
                for item in scraped_details:
                    if item['asin'] == asin:
                        item_copy = item.copy()
                        item_copy['ASSIGNED_RANK'] = rank_labels[idx]
                        final_5_data.append(item_copy)
                        break
            
            matched_keywords = set()
            top_15_json = st.session_state.get('top_15_json', [])
            items_list = top_15_json.get('top_15', []) if isinstance(top_15_json, dict) else top_15_json
            for item in items_list:
                if item.get('asin') in selected_asins:
                    for kw in item.get('relevant_keywords', []): matched_keywords.add(kw.strip().lower())
            
            keywords_json = st.session_state['saved_keywords']
            original_kws_dict = { kw['keyword'].strip().lower(): kw for kw in keywords_json.get('keywords', []) }
            
            valid_final_keywords = [original_kws_dict[kw] for kw in matched_keywords if kw in original_kws_dict]
            valid_final_keywords = sorted(valid_final_keywords, key=lambda x: int(str(x.get('volume', 0)).replace(',', '').strip() or 0), reverse=True)
            seo_keywords_str = ", ".join([item['keyword'] for item in valid_final_keywords[:15]])
            
            st.write("Đang viết Script (Sử dụng TTS Emotion Tags)...")
            
            valid_tag_candidates = []
            for kw in keywords_json.get('keywords', []):
                vol_str = str(kw.get('volume', '0')).replace(',', '').strip()
                if vol_str == '<750': continue
                try:
                    if int(vol_str) >= 750:
                        valid_tag_candidates.append(kw['keyword'])
                except: pass
            tag_candidates_str = ", ".join(valid_tag_candidates)
            
            if trending_memes.strip():
                meme_instruction = f"- **Espressioni obbligatorie**: Inserisci in modo naturale queste espressioni: {trending_memes}"
            else:
                meme_list_str = " | ".join(MEME_VAULT)
                meme_instruction = f"- **Italian Meme/Slang Vault**: Per rendere il copione autentico, SCEGLI 2 O 3 di queste espressioni e inseriscile in modo naturale: [{meme_list_str}]."
            
            prompt4 = P4_TEMPLATE.replace(
                "{final_5_data}", json.dumps(final_5_data, ensure_ascii=False)
            ).replace("{refined_keywords}", seo_keywords_str)\
             .replace("{tag_candidates_str}", tag_candidates_str)\
             .replace("{seed_keywords}", seed_keywords)\
             .replace("{selected_persona}", selected_persona)\
             .replace("{persona_traits}", PERSONA_DICT[selected_persona])\
             .replace("{meme_instruction}", meme_instruction)
            
            if specific_theme.strip():
                theme_instruction = f"- **Target Niche/Theme**: {specific_theme}\n[DIREZIONE CONTENUTI]: Focalizzati sui bisogni del target '{specific_theme}'."
                prompt4 = prompt4.replace("## INPUT", f"## INPUT\n{theme_instruction}")

            res4 = call_gemini_with_retry(prompt4, target_model=PRO_MODEL_ID)
            main_script = res4.text
            
            for item in final_5_data:
                rank_label = item.get('ASSIGNED_RANK', '') 
                if rank_label:
                    rank_num = rank_label.replace('Top ', '').strip() 
                    placeholder = f"{{LINK_{rank_num}}}"
                    main_script = main_script.replace(placeholder, item.get('url', ''))

        st.success("🎉 Hoàn tất Kịch bản tiếng Ý! (Che spettacolo!)")
        st.text_area("Kịch Bản Hoàn Chỉnh (Tiếng Ý)", value=main_script, height=600)
        
        with st.expander("🔍 Xem dữ liệu Debug (Top 5 & OCR)"):
            st.json(final_5_data)