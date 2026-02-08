import os
import django
import sys
import json

# Setup Django environment
sys.path.append('/Users/ivan/Desktop/Projects/FRELANCE/FAQ APP/DJANGO_BACKEND')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'faq_project.settings')
django.setup()

from faq_app.models import FAQ
from faq_app.serializers import FAQSerializer

print("--- FAQ 17 DETAILS ---")
try:
    faq = FAQ.objects.get(id=17)
    print(f"Product: {faq.product.title}")
    print(f"Shop: {faq.product.shop.shop_domain}")
    print(f"Product ID (DB): '{faq.product.shopify_id}'")
    print(f"Product Handle: '{faq.product.handle}'")
    print(f"Is Active: {faq.is_active}")
    print(f"QA Count: {len(faq.questions_answers)}")
    print("QA Content (first item):", faq.questions_answers[0] if faq.questions_answers else "EMPTY")
    
    print("\n--- SERIALIZER OUTPUT ---")
    serializer = FAQSerializer(faq)
    print(json.dumps(serializer.data, indent=2))
    
except FAQ.DoesNotExist:
    print("FAQ 17 not found")
except Exception as e:
    print(f"Error: {e}")
