import threading
import time
import os
from django.utils import timezone
from ..models import BulkGenerationJob, Product, FAQ, ActivityLog
from .ai_service import generate_faq_for_product

def validate_and_save_faq(product, faqs_data, shop):
    """
    Validates AI response and saves FAQ to database.
    Returns (success, count, error_message)
    """
    def is_valid_faq(f):
        return isinstance(f, dict) and 'question' in f and 'answer' in f

    def filter_valid_faqs(raw_list):
        if not isinstance(raw_list, list):
            return []
        return [f for f in raw_list if is_valid_faq(f)]

    valid_faqs_fr = []
    valid_faqs_en = []
    valid_faqs_es = []

    if isinstance(faqs_data, dict):
        valid_faqs_fr = filter_valid_faqs(faqs_data.get('fr', []))
        valid_faqs_en = filter_valid_faqs(faqs_data.get('en', []))
        valid_faqs_es = filter_valid_faqs(faqs_data.get('es', []))
    elif isinstance(faqs_data, list):
        valid_faqs_fr = filter_valid_faqs(faqs_data)

    if not valid_faqs_fr and not valid_faqs_en and not valid_faqs_es:
        return False, 0, "AI generated empty or invalid content"

    # Update or create
    try:
        faq, created = FAQ.objects.get_or_create(product=product, defaults={
            'questions_answers': valid_faqs_fr or [],
            'questions_answers_en': valid_faqs_en,
            'questions_answers_es': valid_faqs_es,
            'num_questions': len(valid_faqs_fr),
            'html_content': "", 
            'is_active': True
        })
        
        if not created:
            faq.questions_answers = valid_faqs_fr or []
            faq.questions_answers_en = valid_faqs_en
            faq.questions_answers_es = valid_faqs_es
            faq.num_questions = len(valid_faqs_fr)
            faq.save()
            
        # Log success
        ActivityLog.objects.create(
            id=str(os.urandom(16).hex()),
            shop=shop,
            level='success',
            operation='generate_faq_bulk',
            message=f"Generated {len(valid_faqs_fr)} questions for product '{product.title}'."
        )
        return True, len(valid_faqs_fr), None

    except Exception as e:
        return False, 0, str(e)


class BulkFAQGenerator(threading.Thread):
    def __init__(self, job_id):
        super().__init__()
        self.job_id = job_id
        self.daemon = True # Daemon thread dies if main process dies

    def run(self):
        try:
            job = BulkGenerationJob.objects.get(id=self.job_id)
        except BulkGenerationJob.DoesNotExist:
            print(f"[Bulk] Job {self.job_id} not found.")
            return

        print(f"[Bulk] Starting job {self.job_id} for shop {job.shop.shop_domain}")
        job.status = 'RUNNING'
        job.save()

        try:
            # 1. Select Products
            products = Product.objects.filter(shop=job.shop)
            if job.mode == 'MISSING_ONLY':
                products = products.filter(has_faq=False)
            
            # Count total (might have changed since creation)
            total = products.count()
            job.total_products = total
            job.save()

            if total == 0:
                job.status = 'COMPLETED'
                job.save()
                return

            # 2. Iterate
            processed_count = 0
            
            # Get API Config once
            shop = job.shop
            api_config = None
            if hasattr(shop, 'api_configuration'):
                api_config = shop.api_configuration
                
            # Check Subscription Limits (Global cap check could be here)
            # For now, we rely on generate_faq checking logic or unlimited for bulk
            # Ideally we should check if they have quota left. 
            # Assuming 'Unlimited' or 'Pro' allows bulk.
            
            # Retrieve max questions from plan
            max_questions = 3
            active_sub = shop.subscriptions.filter(status='active').first()
            if active_sub and active_sub.plan:
                max_questions = active_sub.plan.features.get('max_ai_questions', 3)

            for product in products:
                # Refresh job status to check cancellation
                job.refresh_from_db()
                if job.status == 'CANCELLED':
                    print(f"[Bulk] Job {self.job_id} cancelled.")
                    return

                # Update current product
                job.current_product_title = product.title
                job.save()

                # Generate
                print(f"[Bulk] Generating for {product.title}...")
                faqs_data = generate_faq_for_product(
                    product, 
                    api_config, 
                    num_questions=max_questions
                )

                # Save
                success, count, error = validate_and_save_faq(product, faqs_data, shop)
                
                if success:
                    # Update product status
                    product.has_faq = True
                    product.save()
                else:
                    print(f"[Bulk] Failed for {product.title}: {error}")
                    ActivityLog.objects.create(
                        id=str(os.urandom(16).hex()),
                        shop=shop,
                        level='error',
                        operation='generate_faq_bulk',
                        product=product,
                        product_title=product.title,
                        message=f"Bulk generation failed: {error}"
                    )

                # Update Progress
                processed_count += 1
                job.processed_products = processed_count
                job.save()
                
                # Small delay to be nice to API
                time.sleep(0.5)

            # Done
            job.status = 'COMPLETED'
            job.completed_at = timezone.now()
            job.current_product_title = None
            job.save()
            print(f"[Bulk] Job {self.job_id} completed.")

        except Exception as e:
            print(f"[Bulk] Job {self.job_id} failed: {e}")
            job.refresh_from_db()
            job.status = 'FAILED'
            job.error_message = str(e)
            job.save()
