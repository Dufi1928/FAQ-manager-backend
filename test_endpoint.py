import requests
import json

base_url = "http://127.0.0.1:8000/api"
shop = "ivan-shop-b2b.myshopify.com"
handle = "cailloux-delicieux-vanille-bourbon-parfum-solide-jardin-de-mon-grand-pere"
product_id = "9426629787955"

url = f"{base_url}/storefront/faq/"
params = {
    "shop": shop,
    "product_id": product_id,
    "handle": handle
}

print(f"Testing Backend API: {url}")
try:
    response = requests.get(url, params=params)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        print("✅ Success! Response:")
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"❌ Failed. Response: {response.text}")
except Exception as e:
    print(f"❌ Error connecting to backend: {e}")
