from django.core.management.base import BaseCommand
from subscriptions.models import Plan

class Command(BaseCommand):
    help = 'Initialize subscription plans (Free and Premium)'

    def handle(self, *args, **options):
        plans = [
            {
                'name': 'Basic',
                'description': 'Essential FAQ for small shops.',
                'price': 4.99,
                'features': {
                    'max_products': 50,
                    'max_questions': 500,
                    'max_ai_questions': 5,
                    'design_customization': False, # Locked for Basic
                    'ai_generation': True,
                    'priority_support': False
                }
            },
            {
                'name': 'Pro',
                'description': 'Advanced customization for growing businesses.',
                'price': 15.00,
                'features': {
                    'max_products': 500,
                    'max_questions': 5000,
                    'max_ai_questions': 20,
                    'design_customization': True,
                    'ai_generation': True,
                    'priority_support': False
                }
            },
            {
                'name': 'Unlimited',
                'description': 'Unlimited power for high-volume stores.',
                'price': 35.00,
                'features': {
                    'max_products': 999999,
                    'max_questions': 999999,
                    'max_ai_questions': 50,
                    'design_customization': True,
                    'ai_generation': True,
                    'priority_support': True
                }
            }
        ]

        for p_data in plans:
            plan, created = Plan.objects.get_or_create(
                name=p_data['name'],
                defaults={
                    'description': p_data['description'],
                    'price': p_data['price'],
                    'features': p_data['features'],
                    'is_active': True
                }
            )
            
            # Update existing plans if needed (e.g. to update features)
            if not created:
                plan.description = p_data['description']
                plan.price = p_data['price']
                plan.features = p_data['features']
                plan.save()
                self.stdout.write(self.style.SUCCESS(f'Updated plan: {plan.name}'))
            else:
                self.stdout.write(self.style.SUCCESS(f'Created plan: {plan.name}'))

        self.stdout.write(self.style.SUCCESS('Successfully initialized plans'))
