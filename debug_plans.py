import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'faq_project.settings')
django.setup()

from subscriptions.models import Plan

print(f"{'ID':<5} {'Name':<15} {'Price':<10} {'Currency':<10}")
print("-" * 45)

for p in Plan.objects.all().order_by('id'):
    print(f"{p.id:<5} {p.name:<15} {p.price:<10} {p.currency:<10}")
