import os
import pandas as pd
import requests
import google.generativeai as genai
from dotenv import load_dotenv
from tabulate import tabulate
import json
import io

# Load environment variables from .env file
load_dotenv()

# Configuration
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1PtYHhTapnRp8bOVYCxkAaEb37G_7iva99xnmoO-lvG0/export?format=csv"
SKILL_FILE_PATH = "lead_scoring_skill.md"
API_KEY = os.getenv("GEMINI_API_KEY")

def setup_gemini():
    """Configures the Gemini AI model."""
    if not API_KEY:
        print("Error: GEMINI_API_KEY not found in environment or .env file.")
        exit(1)
    
    genai.configure(api_key=API_KEY)
    
    # Load the skill instructions from the markdown file
    with open(SKILL_FILE_PATH, "r", encoding="utf-8") as f:
        skill_content = f.read()
    
    # Initialize the model with system instructions
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=f"You are a professional Lead Scoring Assistant for Real Estate. Use the following criteria:\n\n{skill_content}"
    )
    return model

def fetch_leads():
    """Downloads lead data from the Google Sheet."""
    print(f"Fetching lead data from Google Sheets...")
    response = requests.get(GOOGLE_SHEET_URL)
    response.raise_for_status()
    
    # Load into pandas DataFrame
    df = pd.read_csv(io.StringIO(response.text))
    return df

def score_lead(model, lead_data):
    """Sends a single lead to Gemini for scoring."""
    lead_json = lead_data.to_json()
    prompt = f"Evaluate this lead and return a JSON object as specified in the instructions:\n{lead_json}"
    
    try:
        response = model.generate_content(prompt)
        # Extract JSON from response (handling potential markdown formatting)
        text = response.text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
            
        return json.loads(text)
    except Exception as e:
        return {
            "id": lead_data.get("id", "N/A"),
            "score": 0,
            "category": "Error",
            "reasoning": f"Failed to process: {str(e)}"
        }

def main():
    print("--- Real Estate Lead Scoring App ---")
    
    # Setup
    model = setup_gemini()
    df = fetch_leads()
    
    results = []
    print(f"Processing {len(df)} leads...")
    
    for _, row in df.iterrows():
        print(f" Scoring Lead ID: {row['id']} - {row['ten_khach']}...", end="\r")
        score_result = score_lead(model, row)
        
        # Append combined info
        results.append({
            "ID": score_result.get("id"),
            "Customer": row["ten_khach"],
            "Score": score_result.get("score"),
            "Category": score_result.get("category"),
            "Reasoning": score_result.get("reasoning")
        })
    
    print("\n\nScoring Complete!\n")
    
    # Display results as a table
    print(tabulate(results, headers="keys", tablefmt="grid"))
    
    # Optional: Save results to CSV
    # pd.DataFrame(results).to_csv("scored_leads.csv", index=False)
    # print("\nResults saved to scored_leads.csv")

if __name__ == "__main__":
    main()
