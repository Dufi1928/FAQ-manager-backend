from rest_framework import viewsets, status, permissions, generics, filters
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count
from django.utils import timezone
import requests
import os

from .models import Shop, Product, FAQ, ActivityLog, APIConfiguration, WebhookRegistration, FAQDesign
from .serializers import (
    ShopSerializer, ProductSerializer, FAQSerializer, 
    ActivityLogSerializer, APIConfigurationSerializer, 
    WebhookRegistrationSerializer, FAQDesignSerializer
)
from .authentication import ShopifyAuthentication

class ShopViewSet(viewsets.ModelViewSet):
    queryset = Shop.objects.all()
    serializer_class = ShopSerializer
    authentication_classes = [ShopifyAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['shop_domain', 'shop_name']
    ordering_fields = ['created_at', 'updated_at']

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Shop.objects.none()
        return Shop.objects.filter(id=self.request.user.id)


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    authentication_classes = [ShopifyAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    filterset_fields = ['has_faq']
    search_fields = ['title', 'handle', 'vendor', 'shopify_id']
    ordering_fields = ['created_at', 'updated_at', 'title']

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Product.objects.none()
        return Product.objects.filter(shop=self.request.user)

    @action(detail=False, methods=['post'])
    def sync(self, request):
        """
        Trigger manual product sync from Shopify.
        """
        shop = request.user
        shop_domain = shop.shop_domain
        access_token = shop.shopify_access_token_encrypted # TODO: Decrypt if needed
        
        # Check active subscription to determine product limit
        product_limit = 1
        try:
             # NEW LOGIC FOR FOREIGNKEY
             active_subscription = shop.subscriptions.filter(status='active').order_by('-created_at').first()
             
             if active_subscription and active_subscription.plan:
                  product_limit = active_subscription.plan.features.get('products_limit', 250)
             else:
                  product_limit = 1 # Free tier limit updated to 1
        except Exception as e:
             print(f"Sync subscription check error: {e}")
             product_limit = 1

        # 1. Fetch products from Shopify
        url = f"https://{shop_domain}/admin/api/2024-01/products.json?limit={product_limit}"
        headers = {
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                products_data = response.json().get('products', [])
                
                created_count = 0
                updated_count = 0
                
                for p_data in products_data:
                    # Extract image URL from Shopify product data
                    image_url = None
                    if p_data.get('images') and len(p_data['images']) > 0:
                        image_url = p_data['images'][0].get('src')
                    
                    product, created = Product.objects.update_or_create(
                        shop=shop,
                        shopify_id=str(p_data['id']),
                        defaults={
                            'title': p_data['title'],
                            'handle': p_data['handle'],
                            'vendor': p_data['vendor'],
                            'product_type': p_data['product_type'],
                            'body_html': p_data['body_html'] or "",
                            'image_url': image_url,
                            'shopify_created_at': p_data['created_at'],
                            'shopify_updated_at': p_data['updated_at'],
                            'last_synced_at': timezone.now()
                        }
                    )
                    if created:
                        created_count += 1
                    else:
                        updated_count += 1
                        
                # Log success
                ActivityLog.objects.create(
                    id=str(os.urandom(16).hex()), # Simple ID generation
                    shop=shop,
                    level='success',
                    operation='manual_sync',
                    message=f"Synced {len(products_data)} products ({created_count} new, {updated_count} updated)."
                )
                
                return Response({"status": "success", "count": len(products_data)})
            else:
                return Response({"error": "Shopify API Error", "details": response.text}, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FAQViewSet(viewsets.ModelViewSet):
    queryset = FAQ.objects.all()
    serializer_class = FAQSerializer
    authentication_classes = [ShopifyAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    filterset_fields = ['product']
    search_fields = ['product__title', 'questions_answers']
    ordering_fields = ['created_at', 'updated_at']

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return FAQ.objects.none()
        queryset = FAQ.objects.filter(product__shop=self.request.user)
        
        # Manually filter by product_id (shopify_id) from query params
        product_id = self.request.query_params.get('product_id')
        if product_id:
            queryset = queryset.filter(product__shopify_id=product_id)
            
        return queryset




    def generate_faq(self, request):
        """
        Generate FAQ for a specific product.
        """
        product_id = request.data.get('productId')
        if not product_id:
            return Response({"error": "Missing productId"}, status=status.HTTP_400_BAD_REQUEST)
            
        shop = request.user
        
        # Check subscription limits
        try:
            max_ai_questions = 3 # Default Free limit
            
            active_subscription = shop.subscriptions.filter(status='active').order_by('-created_at').first()
            if active_subscription and active_subscription.plan:
                 features = active_subscription.plan.features
                 max_ai_questions = features.get('max_ai_questions', 3)
            
        except Exception as e:
             return Response({"error": f"Subscription check failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            product = Product.objects.get(shop=shop, shopify_id=product_id)
            
            # Get API Config
            api_config = None
            if hasattr(shop, 'api_configuration'):
                api_config = shop.api_configuration
            
            # Generate FAQ
            from .services.ai_service import generate_faq_for_product
            requested_num = request.data.get('num_questions', 5)
            try:
                requested_num = int(requested_num)
            except ValueError:
                requested_num = 5
            
            # Cap at plan limit
            num_questions = min(requested_num, max_ai_questions)
            
            # Wrapper for validation
            def is_valid_faq(f):
                return isinstance(f, dict) and 'question' in f and 'answer' in f

            def filter_valid_faqs(raw_list):
                if not isinstance(raw_list, list):
                    return []
                return [f for f in raw_list if is_valid_faq(f)]

            # Extract languages
            valid_faqs_fr = []
            valid_faqs_en = []
            valid_faqs_es = []
            
            # Call AI Service
            faqs_data = generate_faq_for_product(product, api_config, num_questions=num_questions)

            if isinstance(faqs_data, dict):
                valid_faqs_fr = filter_valid_faqs(faqs_data.get('fr', []))
                valid_faqs_en = filter_valid_faqs(faqs_data.get('en', []))
                valid_faqs_es = filter_valid_faqs(faqs_data.get('es', []))
            elif isinstance(faqs_data, list):
                # Fallback if AI messes up and returns a flat list (assume FR)
                valid_faqs_fr = filter_valid_faqs(faqs_data)

            if not valid_faqs_fr and not valid_faqs_en and not valid_faqs_es:
                return Response(
                    {"error": "AI generated empty or invalid content", "raw_data": faqs_data}, 
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY
                )

            # Update or create
            faq, created = FAQ.objects.get_or_create(product=product, defaults={
                'questions_answers': valid_faqs_fr or [], # Default FR (required by model)
                'questions_answers_en': valid_faqs_en,
                'questions_answers_es': valid_faqs_es,
                'num_questions': len(valid_faqs_fr), # Track FR count as primary
                'html_content': "", 
                'is_active': True
            })
            
            if not created:
                faq.questions_answers = valid_faqs_fr or []
                faq.questions_answers_en = valid_faqs_en
                faq.questions_answers_es = valid_faqs_es
                faq.num_questions = len(valid_faqs_fr)
                faq.save()
            
            # Log generation success
            try:
                ActivityLog.objects.create(
                    id=str(os.urandom(16).hex()),
                    shop=shop,
                    level='success',
                    operation='generate_faq',
                    message=f"Generated {len(valid_faqs_fr)} questions for product '{product.title}'."
                )
            except Exception as e:
                print(f"Log creation failed: {e}")

            return Response({
                "status": "success", 
                "faq_id": faq.id, 
                "count": len(valid_faqs_fr),
                "details": {
                    "fr": len(valid_faqs_fr),
                    "en": len(valid_faqs_en),
                    "es": len(valid_faqs_es)
                }
            })
            
        except Product.DoesNotExist:
            return Response({"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[GenerateFAQView] Error: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ActivityLogViewSet(viewsets.ModelViewSet):
    queryset = ActivityLog.objects.all()
    serializer_class = ActivityLogSerializer
    authentication_classes = [ShopifyAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['level', 'operation', 'message', 'product_title']
    ordering_fields = ['timestamp', 'level']

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return ActivityLog.objects.none()
        return ActivityLog.objects.filter(shop=self.request.user).order_by('-timestamp')

    @action(detail=False, methods=['delete'])
    def clear(self, request):
        logs = ActivityLog.objects.filter(shop=request.user) # Changed request.shop to request.user
        logs.delete()
        return Response({'status': 'cleared'})

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get summary stats for logs.
        """
        # Simple aggregation - Clear ordering to fix group by
        stats = self.get_queryset().order_by().values('level').annotate(count=Count('level'))
        
        # Format: { level_counts: { success: 10, error: 2, ... } }
        data = { "level_counts": {} }
        for item in stats:
            data["level_counts"][item['level']] = item['count']
            
        return Response(data)

class APIConfigurationViewSet(viewsets.ModelViewSet):
    queryset = APIConfiguration.objects.all()
    serializer_class = APIConfigurationSerializer
    authentication_classes = [ShopifyAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['shopify_store_url']

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return APIConfiguration.objects.none()
        return APIConfiguration.objects.filter(shop=self.request.user)

    @action(detail=False, methods=['get', 'post'], url_path='keys')
    def keys(self, request):
        """
        Get or set API keys and configuration.
        """
        shop = request.user
        
        # Get or create config
        config, created = APIConfiguration.objects.get_or_create(shop=shop, defaults={
            'shopify_store_url': f"https://{shop.shop_domain}",
            'use_default_keys': True
        })
        
        # Check Plan: Prioritize highest price if multiple active (overlap handling)
        plan_name = "Gratuit"
        subscription = shop.subscriptions.filter(status__iexact='active').order_by('-plan__price', '-created_at').first()
        if subscription and subscription.plan:
             plan_name = subscription.plan.name
        
        is_unlimited = (plan_name == 'Unlimited')
        
        if request.method == 'GET':
            serializer = self.get_serializer(config)
            data = serializer.data
            # We don't return encrypted keys, but we can indicate if they exist
            data['has_anthropic_key'] = config.has_custom_anthropic_key
            data['custom_prompt'] = config.custom_prompt
            data['claude_model'] = config.claude_model
            data['plan_name'] = plan_name
            return Response(data)
            
        elif request.method == 'POST':
            anthropic_key = request.data.get('anthropic_api_key')
            claude_model = request.data.get('claude_model')
            custom_prompt = request.data.get('custom_prompt')
            
            # Only allow API Key updates if Unlimited
            if is_unlimited:
                if anthropic_key:
                    config.anthropic_api_key_encrypted = anthropic_key # TODO: Encrypt
                    config.has_custom_anthropic_key = True
                    config.use_default_keys = False
                    
                if claude_model:
                    config.claude_model = claude_model
            
            # Always allow custom prompt
            if custom_prompt is not None:
                config.custom_prompt = custom_prompt
                
            config.save()
            return Response({"status": "success", "plan": plan_name})


class WebhookRegistrationViewSet(viewsets.ModelViewSet):
    queryset = WebhookRegistration.objects.all()
    serializer_class = WebhookRegistrationSerializer
    authentication_classes = [ShopifyAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['topic', 'address']

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return WebhookRegistration.objects.none()
        return WebhookRegistration.objects.filter(shop=self.request.user)
# Aliases to match urls.py usage
LogViewSet = ActivityLogViewSet
ConfigViewSet = APIConfigurationViewSet

class HealthCheckView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response({"status": "ok"})

class SyncAuthView(APIView):
    """
    Internal endpoint to sync Shopify auth data from Remix app.
    Secured by X-Internal-Secret.
    """
    authentication_classes = [] # No auth required, self-secured
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        secret = request.headers.get('X-Internal-Secret')
        internal_secret = os.environ.get('INTERNAL_API_SECRET', 'my_dev_secret')  # Match valid secret
        
        if secret != internal_secret:
             return Response({"error": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)
             
        shop_domain = request.data.get('shop')
        access_token = request.data.get('access_token')
        
        if not shop_domain or not access_token:
             return Response({"error": "Missing data"}, status=status.HTTP_400_BAD_REQUEST)
             
        # Update or Create Shop
        shop, created = Shop.objects.update_or_create(
            shop_domain=shop_domain,
            defaults={
                'shopify_access_token_encrypted': access_token, # TODO: Encrypt! Storing plain for dev
                'shop_name': shop_domain, # Fallback name
                'is_active': True 
            }
        )
        
        # Also update API Config if it exists
        APIConfiguration.objects.update_or_create(
            shop=shop,
            defaults={
                'shopify_store_url': f"https://{shop.shop_domain}",
                'shopify_access_token_encrypted': access_token, 
                'use_default_keys': True
            }
        )

        # Assign default 'Gratuit' plan if no subscription
        from subscriptions.models import Plan, Subscription
        if not hasattr(shop, 'subscription'):
            try:
                free_plan = Plan.objects.get(name="Gratuit")
                Subscription.objects.create(
                    shop=shop,
                    plan=free_plan,
                    status='active'
                )
                print(f"Assigned default 'Gratuit' plan to {shop_domain}")
            except Plan.DoesNotExist:
                print("Error: 'Gratuit' plan not found. Run seed_plans.py.")
        
        return Response({"status": "synced"})


class UninstallShopView(APIView):
    """
    Internal endpoint to clean up shop data upon uninstall.
    Secured by X-Internal-Secret.
    """
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        secret = request.headers.get('X-Internal-Secret')
        internal_secret = os.environ.get('INTERNAL_API_SECRET', 'my_dev_secret')
        
        print(f"[{timezone.now()}] [UninstallShopView] Request received.")
        print(f"[{timezone.now()}] [UninstallShopView] Secret provided: {'******' if secret else 'NONE'}")
        
        if secret != internal_secret:
             print(f"[{timezone.now()}] [UninstallShopView] Unauthorized: Invalid secret.")
             return Response({"error": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)
             
        shop_domain = request.data.get('shop')
        print(f"[{timezone.now()}] [UninstallShopView] Target shop: {shop_domain}")
        
        if not shop_domain:
             return Response({"error": "Missing shop domain"}, status=status.HTTP_400_BAD_REQUEST)
             
        try:
            shop = Shop.objects.get(shop_domain=shop_domain)
            # Delete shop - this cascades to Products, FAQs, Logs, Config, etc.
            count, deleted_dict = shop.delete()
            print(f"[{timezone.now()}] [UninstallShopView] Success! Deleted: {deleted_dict}")
            return Response({"status": "deleted", "message": f"Shop {shop_domain} and all data removed.", "details": deleted_dict})
        except Shop.DoesNotExist:
            print(f"[{timezone.now()}] [UninstallShopView] Shop {shop_domain} NOT FOUND.")
            return Response({"status": "ignored", "message": "Shop not found or already deleted."})
        except Exception as e:
            print(f"[{timezone.now()}] [UninstallShopView] ERROR: {str(e)}")
            return Response({"error": str(e)}, status=500)


class FAQDesignViewSet(viewsets.GenericViewSet, generics.RetrieveUpdateAPIView):
    """
    Manage visual customization settings.
    """
    serializer_class = FAQDesignSerializer
    authentication_classes = [ShopifyAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        # Get or create design for the authenticated shop
        obj, created = FAQDesign.objects.get_or_create(shop=self.request.user)
        return obj

    def list(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        # Inject plan name
        data = serializer.data
        # Inject plan name - Prioritize expensive
        shop = request.user
        plan_name = "Gratuit"
        subscription = shop.subscriptions.filter(status__iexact='active').order_by('-plan__price', '-created_at').first()
        if subscription and subscription.plan:
             plan_name = subscription.plan.name
        
        # If serializer.data is immutable (ReturnDict), copying might be needed depending on DRF version,
        # but usually it allows assignment or we cast to dict. Safe approach:
        data = dict(data)
        data['plan_name'] = plan_name
        
        return Response(data)

    def perform_update(self, serializer):
        shop = self.request.user
        
        # Check subscription status - Prioritize expensive
        subscription = shop.subscriptions.filter(status__iexact='active').order_by('-plan__price', '-created_at').first()
        can_customize = False
        if subscription and subscription.status == 'active':
            features = subscription.plan.features
            if isinstance(features, dict):
                can_customize = features.get('design_customization', False)
        
        # If not allowed to customize, revert premium fields to defaults
        if not can_customize:
            serializer.save(
                font_family='system-ui',
                question_icon_text='Q',
                answer_icon_text='R'
            )
        else:
            serializer.save()

from .models import Shop, Product, FAQ, ActivityLog, APIConfiguration, WebhookRegistration, FAQDesign, BulkGenerationJob
from .services.bulk_service import BulkFAQGenerator

class BulkActionViewSet(viewsets.ViewSet):
    """
    Manage Bulk FAQ Generation Jobs.
    """
    authentication_classes = [ShopifyAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['post'])
    def start(self, request):
        shop = request.user
        mode = request.data.get('mode', 'MISSING_ONLY')
        
        # Check if active job exists
        active_job = BulkGenerationJob.objects.filter(
            shop=shop, 
            status__in=['PENDING', 'RUNNING']
        ).first()
        
        if active_job:
            return Response(
                {"error": "A bulk job is already running"},
                status=status.HTTP_409_CONFLICT
            )
            
        # Check Plan Restriction
        active_sub = shop.subscriptions.filter(status='active').order_by('-created_at').first()
        plan_name = active_sub.plan.name if active_sub and active_sub.plan else "Free"
        
        if plan_name != "Unlimited":
             return Response(
                {"error": "Bulk generation is restricted to the Unlimited plan."},
                status=status.HTTP_403_FORBIDDEN
            )
            
        # Create Job
        # Count target products roughly
        total_qs = Product.objects.filter(shop=shop)
        if mode == 'MISSING_ONLY':
            total_qs = total_qs.filter(has_faq=False)
        
        count = total_qs.count()
        if count == 0:
             return Response(
                {"error": "No products match criteria"},
                status=status.HTTP_400_BAD_REQUEST
            )

        job = BulkGenerationJob.objects.create(
            shop=shop,
            mode=mode,
            total_products=count,
            status='PENDING'
        )
        
        # Start Thread
        try:
            thread = BulkFAQGenerator(job.id)
            thread.start()
        except Exception as e:
            job.status = 'FAILED'
            job.error_message = f"Failed to start thread: {e}"
            job.save()
            return Response({"error": str(e)}, status=500)
            
        return Response({
            "status": "started",
            "job_id": job.id,
            "total_products": count
        })

    @action(detail=False, methods=['post'])
    def cancel(self, request):
        shop = request.user
        
        active_job = BulkGenerationJob.objects.filter(
            shop=shop, 
            status__in=['PENDING', 'RUNNING']
        ).first()
        
        if not active_job:
            return Response({"error": "No active job to cancel"}, status=404)
            
        active_job.status = 'CANCELLED'
        active_job.save()
        
        return Response({"status": "cancelled"})

    @action(detail=False, methods=['get'])
    def status(self, request):
        shop = request.user
        
        # Get latest job
        job = BulkGenerationJob.objects.filter(shop=shop).order_by('-created_at').first()
        
        if not job:
            return Response({"status": "none"})
            
        return Response({
            "id": job.id,
            "status": job.status,
            "mode": job.mode,
            "total_products": job.total_products,
            "processed_products": job.processed_products,
            "progress": (job.processed_products / job.total_products * 100) if job.total_products > 0 else 0,
            "current_product": job.current_product_title,
            "created_at": job.created_at,
            "error_message": job.error_message
        })
