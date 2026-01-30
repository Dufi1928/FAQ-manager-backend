import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'faq_project.settings')
django.setup()

from subscriptions.models import Plan

plans = [
    {
        'name': 'Gratuit',
        'price': 0,
        'features': {'interval': 'forever', 'products_limit': 10, 'ai_generation_included': False},
        'description': 'Pour commencer',
    },
    {
        'name': 'Basic',
        'price': 9.99,
        'features': {'interval': 'month', 'products_limit': 100, 'ai_generation_included': True},
        'description': 'Pour les petites boutiques',
    },
    {
        'name': 'Pro',
        'price': 29.99,
        'features': {'interval': 'month', 'products_limit': 1000, 'ai_generation_included': True},
        'description': 'Pour les boutiques en croissance',
    },
    {
        'name': 'Enterprise',
        'price': 99.99,
        'features': {'interval': 'month', 'products_limit': 100000, 'ai_generation_included': True},
        'description': 'Illimité',
    }
]

for p_data in plans:
    plan, created = Plan.objects.get_or_create(
        name=p_data['name'],
        defaults=p_data
    )
    if created:
        print(f"Plan created: {plan.name}")
    else:
        print(f"Plan exists: {plan.name}")
