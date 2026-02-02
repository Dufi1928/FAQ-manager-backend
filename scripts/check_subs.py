import os
import django
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'faq_project.settings')
django.setup()

from subscriptions.models import Subscription, Shop

def check_subs():
    shops = Shop.objects.all()
    for shop in shops:
        print(f"Shop: {shop.shop_domain}")
        sub = shop.subscriptions.filter(status='active').order_by('-created_at').first()
        if sub:
            print(f"  Active Sub: {sub.plan.name} (ID: {sub.plan.id})")
            print(f"  Features applied: {sub.plan.features}")
        else:
            print("  No active subscription (Free Tier)")

if __name__ == "__main__":
    check_subs()
