import os
import json
import time
import re
import pandas as pd
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY not found in .env file.")
genai.configure(api_key=api_key)

# Initialize the data extraction model
extraction_model = genai.GenerativeModel('gemini-2.5-flash')

EXTRACTION_PROMPT = """
You are a data extraction agent. Analyze the following JSON array containing car listings. Each listing has an "id" and a "text" description.
Extract the financial and technical data for EACH car and return a JSON array of results.

Rules:
1. Return ONLY a valid JSON array of objects. No markdown formatting.
2. The output array MUST contain the exact same number of items as the input.
3. Include the "id" in your output exactly as provided so the data maps correctly.
4. For missing values, output null.

Expected Output Schema for EACH item:
{
  "id": integer,
  "total_price_aed": integer or null,
  "odometer_kms": integer or null,
  "payment_plan": {
    "is_available": boolean,
    "emi_monthly_aed": integer or null,
    "down_payment": string or null,
    "duration_years": integer or null
  }
}

Input Batch:
"""

def extract_phone_numbers(text: str) -> str:
    """
    Extracts UAE phone numbers from raw text. Handles spaces and hyphens gracefully.
    """
    if not text or pd.isna(text):
        return None
        
    # Remove spaces and hyphens to normalize (e.g., "+971 50 123 4567" -> "+971501234567")
    normalized_text = str(text).replace(" ", "").replace("-", "")
    
    # Strict UAE pattern: +971, 00971, or 0, followed by area/mobile code, then 7 digits.
    phone_pattern = r'(?:\+971|00971|0)(?:5[024568]|4|2|3|6|7|9)\d{7}\b'
    
    matches = re.findall(phone_pattern, normalized_text)
    if matches:
        return ", ".join(list(set(matches)))
    return None

def clean_description_noise(text: str) -> str:
    """
    Strips out common structural noise, disclaimer sections, and showroom boilerplate.
    """
    if not text or pd.isna(text):
        return ""
    
    cleaned = str(text).replace("<br>", "\n").replace("<br/>", "\n")
    
    cutoff_markers = [
        "-----------------------------------------",
        "Buy this car with confidence from",
        "What is dubizzle cars?",
        "Follow us on our Social Media Pages",
        "Check out our website:",
        "Find us on Google Maps",
        "Selling Your Car to Us:"
    ]
    
    for marker in cutoff_markers:
        if marker in cleaned:
            cleaned = cleaned.split(marker)[0]
            
    return cleaned.strip()

def extract_in_batches(df, batch_size=20):
    extracted_results = []
    total_rows = len(df)

    for i in range(0, total_rows, batch_size):
        batch_df = df.iloc[i:i+batch_size]
        print(f"Processing batch {i//batch_size + 1}/{(total_rows//batch_size) + (1 if total_rows%batch_size!=0 else 0)} (Rows {i} to {i+len(batch_df)-1})...")

        batch_payload = []
        for idx, row in batch_df.iterrows():
            # Pass the CLEANED description to the LLM so it doesn't get confused by boilerplate
            text = str(row.get('title', '')) + " \n " + str(row.get('cleaned_description', ''))
            batch_payload.append({"id": idx, "text": text})

        payload_str = json.dumps(batch_payload)

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = extraction_model.generate_content(
                    EXTRACTION_PROMPT + payload_str,
                    generation_config={"response_mime_type": "application/json"}
                )
                
                batch_results = json.loads(response.text)
                extracted_results.extend(batch_results)
                break 

            except Exception as e:
                if "429" in str(e) or "Quota exceeded" in str(e):
                    print(f"Rate limit hit by Google. Waiting 90 seconds to reset quota...")
                    time.sleep(90)
                else:
                    print(f"Unexpected error on batch: {e}")
                    for item in batch_payload:
                        extracted_results.append({"id": item["id"], "total_price_aed": None, "odometer_kms": None})
                    break

        print("Batch successful. Waiting 90 seconds to respect rate limits...")
        time.sleep(90)

    return extracted_results

def preprocess_and_embed():
    print("Starting Comprehensive Pre-processing Pipeline...")
    
    raw_file_path = os.path.join("data", "Copy of sample_cars_dataset.xlsx")
    if not os.path.exists(raw_file_path):
        raise FileNotFoundError(f"Cannot find dataset at {raw_file_path}")

    if raw_file_path.endswith('.xlsx'):
        df = pd.read_excel(raw_file_path)
    else:
        df = pd.read_csv(raw_file_path)

    df.columns = [str(col).lower().strip().replace(' ', '_') for col in df.columns]
    
    if 'description' not in df.columns:
        df['description'] = ''
    if 'title' not in df.columns:
        df['title'] = ''

    df['description'] = df['description'].fillna('')
    df['title'] = df['title'].fillna('')

    print("Extracting contact info and purifying description text...")
    df['contact_numbers'] = df['description'].apply(extract_phone_numbers)
    df['cleaned_description'] = df['description'].apply(clean_description_noise)

    print("Phase 1: Extracting structured JSON in batches...")
    extracted_data_list = extract_in_batches(df, batch_size=10)
    
    extracted_dict = {res.get('id', -1): res for res in extracted_data_list if isinstance(res, dict)}
    
    df['total_price_aed'] = df.index.map(lambda idx: extracted_dict.get(idx, {}).get('total_price_aed'))
    df['odometer_kms'] = df.index.map(lambda idx: extracted_dict.get(idx, {}).get('odometer_kms'))
    df['has_emi'] = df.index.map(lambda idx: extracted_dict.get(idx, {}).get('payment_plan', {}).get('is_available', False))
    df['emi_monthly'] = df.index.map(lambda idx: extracted_dict.get(idx, {}).get('payment_plan', {}).get('emi_monthly_aed'))
    df['emi_downpayment'] = df.index.map(lambda idx: extracted_dict.get(idx, {}).get('payment_plan', {}).get('down_payment'))

    print("Phase 2: Generating Vector Embeddings natively...")
    # Generate embeddings based ONLY on the cleaned description
    df['semantic_text'] = (
        "Car: " + df.get('year', '').astype(str) + " " + df.get('make', '').astype(str) + " " + df.get('model', '').astype(str) + "\n" +
        "Details: " + df.get('title', '').fillna('') + " " + df['cleaned_description']
    )

    embeddings = []
    for index, row in df.iterrows():
        try:
            result = genai.embed_content(
                model="models/gemini-embedding-2", 
                content=row['semantic_text']
            )
            embeddings.append(result['embedding'])
            time.sleep(0.5) 
        except Exception as e:
            print(f"Embedding failed on row {index}: {e}")
            embeddings.append([0.0] * 768) 

    df['embedding'] = embeddings
    
    output_path_pkl = os.path.join("data", "processed_inventory.pkl")
    output_path_csv = os.path.join("data", "processed_inventory_audit.csv")
    
    df.to_pickle(output_path_pkl)
    df.to_csv(output_path_csv, index=False)
    
    print(f"Success! Pipeline complete. Check {output_path_csv} to audit the data.")

if __name__ == "__main__":
    preprocess_and_embed()