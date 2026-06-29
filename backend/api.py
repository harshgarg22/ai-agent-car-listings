import os
import numpy as np
import pandas as pd
import google.generativeai as genai
from fastapi import APIRouter, HTTPException
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

router = APIRouter()

INVENTORY_DF = None
PICKLE_PATH = os.path.join("data", "processed_inventory.pkl")

#reading the file all at once and keeping it in memory via the global variable
#saves time: in-memory caching
def load_inventory_dataframe():
    global INVENTORY_DF
    if INVENTORY_DF is None:
        if not os.path.exists(PICKLE_PATH):
            raise FileNotFoundError(f"Database file missing at {PICKLE_PATH}.")
        INVENTORY_DF = pd.read_pickle(PICKLE_PATH)
    return INVENTORY_DF

#func to calculate cosine similarity
def calculate_cosine_similarity(vec1, vec2):
    v1 = np.array(vec1)
    v2 = np.array(vec2)
    #prevent division by zero error
    if np.linalg.norm(v1) == 0 or np.linalg.norm(v2) == 0:
        return 0.0
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

#hybrid searching algorithm 
def execute_hybrid_search(
    query: str = None,  
    make: str = None,
    max_price: float = None, 
    min_year: int = None,
    trim: str = None,
    max_odometer: float = None,
    has_emi: bool = None,
    max_emi_monthly: float = None,
    max_emi_downpayment: float = None,
    top_k: int = 3
):
    """
    Upgraded Hybrid Search: Executes multi-attribute strict metadata filtering
    across your exact dataset schema before applying vector ranking.
    """
    df = load_inventory_dataframe()
    working_df = df.copy()

    # filtering based off the values in the query
    if make:
        working_df = working_df[working_df['make'].str.contains(make, case=False, na=False)]
        
    if max_price:
        working_df = working_df[working_df['total_price_aed'].fillna(float('inf')) <= max_price]
        
    if min_year:
        working_df = working_df[working_df['year'].fillna(0) >= min_year]
        
    if trim:
        working_df = working_df[working_df['trim'].str.contains(trim, case=False, na=False)]
        
    if max_odometer:
        working_df = working_df[working_df['odometer_kms'].fillna(float('inf')) <= max_odometer]
        
    if has_emi is not None:
        working_df = working_df[working_df['has_emi'] == has_emi]
        
    if max_emi_monthly:
        working_df = working_df[working_df['emi_monthly'].fillna(float('inf')) <= max_emi_monthly]
        
    if max_emi_downpayment:
        working_df = working_df[working_df['emi_downpayment'].fillna(float('inf')) <= max_emi_downpayment]

    if working_df.empty:
        return []

    # Define standard export columns
    columns_to_export = [
        'make', 'model', 'trim', 'year', 'total_price_aed', 'odometer_kms', 
        'has_emi', 'emi_monthly', 'emi_downpayment', 'cleaned_description', 
        'contact_numbers', 'photo_url'
    ]

    # semantic search using cosine similairty
    # If the user only gave hard numbers and no descriptive keywords, skip embedding to save costs
    if not query or str(query).strip() == "" or query.lower() == "none":
        top_matches = working_df.head(top_k)
        return top_matches[columns_to_export].to_dict(orient='records')

    try:
        response = genai.embed_content(
            model="models/gemini-embedding-2",
            content=query
        )
        query_vector = response['embedding']
    except Exception as e:
        print(f"Embedding failure: {e}")
        # fallback to pure metadata results if API fails
        return working_df.head(top_k)[columns_to_export].to_dict(orient='records')

    scores = []
    for _, row in working_df.iterrows():
        scores.append(calculate_cosine_similarity(query_vector, row['embedding']))
    
    working_df['similarity_score'] = scores
    top_matches = working_df.sort_values(by='similarity_score', ascending=False).head(top_k)
    
    return top_matches[columns_to_export].to_dict(orient='records')