import os
import django
import sys

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'faq_project.settings')
django.setup()

from subscriptions.models import Plan

def check_plans():
    plans = Plan.objects.all()
    print(f"Found {plans.count()} plans:")
    for plan in plans:
        print(f"Plan: {plan.name} (Active: {plan.is_active})")
        print(f"  Features: {plan.features}")
        print("-" * 30)

if __name__ == "__main__":
    check_plans()
