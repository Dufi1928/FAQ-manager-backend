import os
import json
import requests
from django.conf import settings

def generate_faq_for_product(product, api_config=None, num_questions=5, language="fr"):
    """
    Generate FAQ for a product using Anthropic/Claude (with fallback logic).
    Language: 'fr', 'en', or 'both'
    """
    
    # 1. Determine API Key and Model
    api_key = None
    model = "claude-3-haiku-20240307" # Default cheap model
    
    if api_config and api_config.has_custom_anthropic_key and api_config.anthropic_api_key_encrypted:
        api_key = api_config.anthropic_api_key_encrypted # TODO: Add decryption
        model = api_config.claude_model or model
        print(f"[AI Service] Using CUSTOM API Key. Model: {model}")
    else:
        # System-wide default key
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        print(f"[AI Service] Using DEFAULT API Key. Present: {bool(api_key)}")
        
    if not api_key:
        print("[AI Service] ERROR: No API Key available.")
        return {"error": "No API Key available (Anthropic)"}

    # 2. Determine Prompt
    system_prompt = f"""You are a helpful assistant for an e-commerce store. 
    Generate {num_questions} Frequently Asked Questions (FAQ) with answers based on the product description provided.
    
    You MUST output the content in THREE languages: French (fr), English (en), and Spanish (es).
    
    Return the output STRICTLY as a JSON object with the following structure:
    {{
        "fr": [ {{ "question": "...", "answer": "..." }}, ... ],
        "en": [ {{ "question": "...", "answer": "..." }}, ... ],
        "es": [ {{ "question": "...", "answer": "..." }}, ... ]
    }}
    
    Do not include any other text, markdown formatting, or explanations. Only the JSON object."""
    
    if api_config and api_config.custom_prompt:
        system_prompt = api_config.custom_prompt # Note: Custom prompts might break the strict JSON structure if not careful.

    # 3. Prepare Product Data
    product_context = f"""
    Product Title: {product.title}
    Product Type: {product.product_type}
    Vendor: {product.vendor}
    Description: {product.body_html}
    """

    # 4. Call Anthropic API
    headers = {
        "content-type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01"
    }
    
    # Anthropic Messages format
    payload = {
        "model": model,
        "max_tokens": 2000, # Increased for 3 languages
        "system": system_prompt,
        "messages": [
            {"role": "user", "content": f"Generate trilingual FAQ for this product:\n{product_context}"}
        ],
        "temperature": 0.7
    }
    
    try:
        print(f"[AI Service] Sending request to Anthropic... Model: {model}")
        response = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        
        content = data['content'][0]['text']
        print(f"[AI Service] Response received. Length: {len(content)}")
        
        # Clean potential markdown block if AI included it
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        return json.loads(content)
        
    except Exception as e:
        print(f"[AI Service] Anthropic API Error: {str(e)}")
        if 'response' in locals():
            print(f"[AI Service] Response text: {response.text}")
        return {"error": str(e)}
