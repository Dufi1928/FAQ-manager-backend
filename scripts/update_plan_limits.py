import os
import django
import sys

# Setup Django environment
sys.path.append('/Users/ivan/Desktop/Projects/FRELANCE/FAQ APP/DJANGO_BACKEND')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'faq_project.settings')
django.setup()

from subscriptions.models import Plan

def update_plans():
    print("Updating plan limits...")
    
    # helper to update features dict
    def update_plan_features(name, products, questions):
        try:
            # Case insensitive search just in case
            plans = Plan.objects.filter(name__iexact=name)
            for plan in plans:
                if plan.features is None:
                    plan.features = {}
                
                # Update both keys to be safe (code uses both in different places?)
                # views.py uses 'products_limit' in sync and 'max_products' in generate_faq logic?
                # Actually views.py uses:
                # sync: active_subscription.plan.features.get('products_limit', 250)
                # generate_faq: active_subscription.plan.features.get('max_ai_questions', 5)
                # But let's check generate_faq logic again.
                
                plan.features['products_limit'] = products
                plan.features['max_products'] = products 
                plan.features['max_ai_questions'] = questions
                plan.save()
                print(f"Updated {plan.name} (ID: {plan.id}): products={products}, questions={questions}")
                
            if not plans.exists():
                print(f"Plan '{name}' not found")
                
        except Exception as e:
            print(f"Error updating {name}: {e}")

    # Basic: 50 products, 3 AI questions
    update_plan_features('Basic', 50, 3)

    # Pro: 250 products, 5 AI questions
    update_plan_features('Pro', 250, 5)

    # Unlimited: No limit (999999), 7 AI questions
    update_plan_features('Unlimited', 999999, 7)

if __name__ == '__main__':
    update_plans()
