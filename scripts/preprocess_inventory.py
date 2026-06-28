import os
import re
import time
import pandas as pd
from litellm import embedding
from dotenv import load_dotenv


load_dotenv()

def extract_numerical_features(row):
    """
    take the unstructured info in ther title and description column and extract and suitabke info
    here price and mileage/odometer (came up w this using visual examination of the dataset)
    """
    #combine title and description
    raw_text = str(row.get('title', '')) + " " + str(row.get('description', ''))
    
    # remove unnecessary symbols and replace multiple spaces w one single space
    cleaned_text = re.sub(r'[•\*\|_]+', ' ', raw_text)
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
    
    # extract price regex. aed 10000 or 10000 aed both work
    price_val = None
    price_pattern = re.compile(
        r'(?:AED\s*)([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,})|([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,})(?:\s*AED)', 
        re.IGNORECASE
    )
    price_match = price_pattern.search(cleaned_text)
    if price_match:
        clean_price = (price_match.group(1) or price_match.group(2)).replace(',', '')
        price_val = float(clean_price)

    # extract odometer info
    odo_val = None
    odo_pattern = re.compile(
        r'(?:Odometer|Mileage|Kms)[\s:;\-]*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)|([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)[\s:;\-]*(?:kms|km)\b', 
        re.IGNORECASE
    )
    odo_match = odo_pattern.search(cleaned_text)
    if odo_match:
        clean_odo = (odo_match.group(1) or odo_match.group(2)).replace(',', '')
        odo_val = float(clean_odo)

    return pd.Series({
        'clean_text': cleaned_text, 
        'extracted_price': price_val, 
        'extracted_odometer': odo_val
    })

def preprocess_and_embed():
    print("Starting data pre-processing...")
    
    raw_file_path = os.path.join("data", "Copy of sample_cars_dataset.xlsx")
    
    if not os.path.exists(raw_file_path):
        raise FileNotFoundError(f"Cannot find the raw dataset at {raw_file_path}. Ensure it is inside the data/ folder.")

    print(f"Loading raw dataset from {raw_file_path}...")
    
    if raw_file_path.endswith('.xlsx'):
        df = pd.read_excel(raw_file_path)
    else:
        df = pd.read_csv(raw_file_path)

    # removing any spaces in the columns, stripping spaces before and after, lowercasing everything
    df.columns = [str(col).lower().strip().replace(' ', '_') for col in df.columns]
    
    #just a sanity check to see if description and title and available in the columns
    if 'description' not in df.columns:
        df['description'] = ''
    if 'title' not in df.columns:
        df['title'] = ''

    df['description'] = df['description'].fillna('')
    df['title'] = df['title'].fillna('')

    #calling the previous function to handle the regex and detection
    print("Cleaning text and extracting exact numerical data...")
    extracted_features = df.apply(extract_numerical_features, axis=1)
    df = pd.concat([df, extracted_features], axis=1)

    #checking how many values were extracted
    found_prices = df['extracted_price'].notna().sum()
    found_odos = df['extracted_odometer'].notna().sum()
    print(f"Successfully extracted: {found_prices} Prices | {found_odos} Odometers.")

    df['semantic_text'] = (
        "Car: " + df.get('year', '').astype(str) + " " + df.get('make', '').astype(str) + " " + df.get('model', '').astype(str) + " " +
        "Details: " + df['clean_text']
    )

    print(f"Generating embeddings for {len(df)} cars. This will take a few seconds...")
    
    embeddings = []
    for index, row in df.iterrows():
        try:
            response = embedding(
                model="gemini/gemini-embedding-2", 
                input=row['semantic_text']
            )
            vector = response['data'][0]['embedding']
            embeddings.append(vector)
            
            time.sleep(0.5)
            
        except Exception as e:
            print(f"Failed to embed row {index}: {e}")
            embeddings.append([0.0] * 768) 

    df['embedding'] = embeddings
    
    # Save the final processed file
    output_path = os.path.join("data", "processed_inventory.pkl")
    df.to_pickle(output_path)
    
    output_path_csv = os.path.join("data", "processed_inventory_audit.csv")
    df.to_csv(output_path_csv, index=False)
    
    print(f"Success! Pre-processed dataset saved to {output_path}")

if __name__ == "__main__":
    preprocess_and_embed()