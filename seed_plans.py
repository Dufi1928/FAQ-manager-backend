import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'faq_project.settings')
django.setup()

from subscriptions.models import Plan

plans = [
    {
        'name': 'Basic',
        'price': 9.99,
        'currency': 'EUR',
        'features': {'interval': 'month', 'products_limit': 50, 'ai_generation_included': True},
        'description': 'Pour les petites boutiques',
    },
    {
        'name': 'Pro',
        'price': 29.99,
        'currency': 'EUR',
        'features': {'interval': 'month', 'products_limit': 500, 'ai_generation_included': True},
        'description': 'Pour les boutiques en croissance',
    },
    {
        'name': 'Unlimited',
        'price': 49.99,
        'currency': 'EUR',
        'features': {'interval': 'month', 'products_limit': 100000, 'ai_generation_included': True},
        'description': 'Illimité',
    }
]

for p_data in plans:
    plan, created = Plan.objects.update_or_create(
        name=p_data['name'],
        defaults={
            'price': p_data['price'],
            'currency': p_data['currency'],
            'features': p_data['features'],
            'description': p_data['description']
        }
    )
    if created:
        print(f"Plan created: {plan.name}")
    else:
        print(f"Plan updated: {plan.name}")
