import os
import json
import requests


def fetch_active_theme_settings(shop_domain, access_token):
    """
    Fetches the active Shopify theme and its settings_data.json.
    Returns a dict with theme name, colors, fonts, etc.
    """
    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json",
    }
    api_base = f"https://{shop_domain}/admin/api/2024-01"

    # Step 1: Find the active theme
    themes_resp = requests.get(f"{api_base}/themes.json", headers=headers, timeout=10)
    themes_resp.raise_for_status()
    themes = themes_resp.json().get("themes", [])

    active_theme = next((t for t in themes if t.get("role") == "main"), None)
    if not active_theme:
        return None

    theme_id = active_theme["id"]
    theme_name = active_theme.get("name", "")

    # Step 2: Fetch settings_data.json (contains brand colors, fonts, etc.)
    asset_url = (
        f"{api_base}/themes/{theme_id}/assets.json"
        f"?asset[key]=config/settings_data.json"
    )
    asset_resp = requests.get(asset_url, headers=headers, timeout=10)
    asset_resp.raise_for_status()

    raw_value = asset_resp.json().get("asset", {}).get("value", "{}")
    settings_data = json.loads(raw_value) if isinstance(raw_value, str) else raw_value

    # Extract the "current" section which holds active customizations
    current = settings_data.get("current", {})

    return {
        "theme_name": theme_name,
        "settings": current,
    }


def fetch_shop_info(shop_domain, access_token):
    """Fetches basic shop metadata (name, currency, etc.)."""
    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json",
    }
    resp = requests.get(
        f"https://{shop_domain}/admin/api/2024-01/shop.json",
        headers=headers,
        timeout=10,
    )
    resp.raise_for_status()
    shop = resp.json().get("shop", {})
    return {
        "name": shop.get("name", ""),
        "currency": shop.get("currency", ""),
    }


def detect_design_from_theme(shop_domain, access_token):
    """
    Main entry point: fetches theme data, sends to Claude,
    and returns a suggested FAQDesign config dict.
    Returns {"suggested": {...}} or {"error": "..."}.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"error": "Clé API Anthropic non configurée."}

    # --- Gather context from Shopify ---
    try:
        theme_data = fetch_active_theme_settings(shop_domain, access_token)
    except Exception as e:
        return {"error": f"Impossible de récupérer le thème Shopify : {e}"}

    if not theme_data:
        return {"error": "Aucun thème actif trouvé sur cette boutique."}

    try:
        shop_info = fetch_shop_info(shop_domain, access_token)
    except Exception:
        shop_info = {}

    # --- Build Claude prompt ---
    system_prompt = (
        "You are a design assistant for a Shopify FAQ widget. "
        "Given the store's active theme settings, suggest optimal visual design values "
        "for the FAQ widget that match the store's branding. "
        "Always ensure good contrast (WCAG AA minimum). "
        "Return ONLY a valid JSON object — no markdown, no explanations."
    )

    user_prompt = f"""Store name: {shop_info.get('name', shop_domain)}
Theme name: {theme_data['theme_name']}

Active theme settings (Shopify settings_data.json "current" section):
{json.dumps(theme_data['settings'], indent=2)}

Return a JSON object with EXACTLY these fields:
{{
  "question_color": "hex color for question text",
  "answer_color": "hex color for answer/body text",
  "background_color": "hex color for FAQ section background",
  "border_color": "hex color for borders/dividers",
  "font_family": "CSS-compatible font family (use the store body font if detectable, else system-ui)",
  "font_size": <integer 14–20>,
  "border_radius": <integer 0–24>,
  "question_icon_bg": "hex color for Q icon background (light tint of accent color)",
  "question_icon_color": "hex color for Q icon text (the accent color itself)",
  "answer_icon_bg": "hex color for R icon background (light tint of secondary color)",
  "answer_icon_color": "hex color for R icon text (the secondary color itself)",
  "layout_model": "classic" | "modern" | "minimal" | "cards"
}}

Guidelines:
- Derive colors from the theme's color palette (colors_text, colors_background_1, colors_accent_1, etc.)
- Choose layout_model based on the store's style: minimal for luxury/clean brands, cards for vibrant/product-heavy stores, modern for contemporary brands, classic as default
- Ensure question_color and answer_color contrast well against background_color"""

    # --- Call Anthropic API ---
    payload = {
        "model": "claude-3-haiku-20240307",
        "max_tokens": 600,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
        "temperature": 0.2,
    }
    headers_api = {
        "content-type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers_api,
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        content = resp.json()["content"][0]["text"].strip()

        # Strip markdown code blocks if present
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        suggested = json.loads(content)

        # Validate required keys are present
        required = {
            "question_color", "answer_color", "background_color", "border_color",
            "font_family", "font_size", "border_radius",
            "question_icon_bg", "question_icon_color",
            "answer_icon_bg", "answer_icon_color", "layout_model",
        }
        missing = required - set(suggested.keys())
        if missing:
            return {"error": f"Réponse Claude incomplète, champs manquants : {missing}"}

        return {
            "suggested": suggested,
            "theme_name": theme_data["theme_name"],
            "shop_name": shop_info.get("name", shop_domain),
        }

    except Exception as e:
        return {"error": f"Erreur lors de l'analyse Claude : {e}"}
