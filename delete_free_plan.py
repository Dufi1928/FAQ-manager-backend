import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'faq_project.settings')
django.setup()

from subscriptions.models import Plan

plans = Plan.objects.filter(name="Gratuit")
count = plans.count()
plans.delete()
print(f"Deleted {count} 'Gratuit' plans.")

# Verify remaining
print("\nRemaining Plans:")
for p in Plan.objects.all().order_by('id'):
    print(f"{p.id}: {p.name} - {p.price} €")
