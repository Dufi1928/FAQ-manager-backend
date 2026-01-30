import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'faq_project.settings')
django.setup()

from faq_app.models import Shop, Product, FAQ

shop_domain = "ivan-shop-b2b.myshopify.com"
handle = "cailloux-delicieux-vanille-bourbon-parfum-solide-jardin-de-mon-grand-pere"

print(f"Checking for Shop: {shop_domain}")
try:
    shop = Shop.objects.get(shop_domain=shop_domain)
    print(f"✅ Shop found: {shop}")
except Shop.DoesNotExist:
    print(f"❌ Shop NOT found.")
    sys.exit(1)

print(f"Checking for Product with handle: {handle}")
try:
    product = Product.objects.get(shop=shop, handle=handle)
    print(f"✅ Product found: {product.title} (ID: {product.shopify_id})")
    
    print("Checking for FAQs...")
    faqs = FAQ.objects.filter(product=product, is_active=True)
    if faqs.exists():
        print(f"✅ Active FAQs found: {faqs.count()}")
        for f in faqs:
            print(f" - FAQ ID: {f.id}, Questions: {f.num_questions}")
    else:
        print(f"❌ No active FAQs found for this product.")
        
except Product.DoesNotExist:
    print(f"❌ Product NOT found with handle: {handle}")
    # List a few products to see if handles look different
    print("Listing first 5 products for this shop:")
    for p in Product.objects.filter(shop=shop)[:5]:
        print(f" - {p.handle}")
