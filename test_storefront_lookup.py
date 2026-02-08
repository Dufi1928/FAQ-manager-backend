import os
import django
import sys

# Setup Django environment
sys.path.append('/Users/ivan/Desktop/Projects/FRELANCE/FAQ APP/DJANGO_BACKEND')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'faq_project.settings')
django.setup()

from faq_app.models import Shop, Product

shop_domain = "ivan-shop-b2b.myshopify.com"
product_id_input_1 = "10076002124083"
product_id_input_2 = "gid://shopify/Product/10076002124083"
handle_input = "l-essentiel-le-t-shirt-blanc-en-coton-premium"

print(f"Testing lookup for Shop: {shop_domain}")

try:
    shop = Shop.objects.get(shop_domain=shop_domain)
    print("Shop found.")
except Shop.DoesNotExist:
    print("Shop NOT found.")
    exit()

def find_product(p_id, p_handle):
    print(f"\nLooking up: ID='{p_id}', Handle='{p_handle}'")
    product = None
    
    # Strategy 1: exact match
    if p_id:
        try:
            product = Product.objects.get(shop=shop, shopify_id=p_id)
            print(f"[Strategy 1] Found by exact ID: {product.shopify_id}")
            return product
        except Product.DoesNotExist:
            pass
            
        # Strategy 2: numeric string (remove 'gid://shopify/Product/')
        clean_id = str(p_id).replace("gid://shopify/Product/", "")
        try:
            product = Product.objects.get(shop=shop, shopify_id=clean_id)
            print(f"[Strategy 2] Found by clean ID: {product.shopify_id}")
            return product
        except Product.DoesNotExist:
            print(f"[Strategy 2] Failed with clean ID: {clean_id}")
            pass
            
    # Strategy 3: Handle
    if not product and p_handle:
        try:
            product = Product.objects.get(shop=shop, handle=p_handle)
            print(f"[Strategy 3] Found by handle: {product.shopify_id}")
            return product
        except Product.DoesNotExist:
            print(f"[Strategy 3] Failed with handle: {p_handle}")
            pass
            
    return None

# Test Cases
find_product(product_id_input_1, None)
find_product(product_id_input_2, None)
find_product(None, handle_input)
find_product("99999999", handle_input) # Wrong ID, correct handle
