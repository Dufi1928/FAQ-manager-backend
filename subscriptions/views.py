from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.conf import settings
from .models import Plan, Subscription
from django.utils import timezone
from .serializers import PlanSerializer, SubscriptionSerializer
from faq_app.authentication import Shop
import shopify
import os
import ssl
import json
# BYPASS SSL VERIFICATION FOR DEV - Fixes [SSL: CERTIFICATE_VERIFY_FAILED]
ssl._create_default_https_context = ssl._create_unverified_context

class PlanViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Plan.objects.filter(is_active=True)
    serializer_class = PlanSerializer
    permission_classes = [permissions.AllowAny]


class SubscriptionViewSet(viewsets.ViewSet):
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        """
        Get current subscription for the shop.
        """
        shop = request.user
        if not isinstance(shop, Shop):
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            subscription = Subscription.objects.filter(
                shop=shop,
                status__iexact='active'
            ).order_by('-created_at').select_related('plan').first()
            
            if not subscription:
                return Response(None, status=status.HTTP_204_NO_CONTENT)
                
            serializer = SubscriptionSerializer(subscription)
            return Response(serializer.data)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Keep list for admin debugging or history if needed, but 'current' is the main one.
    def list(self, request):
         return self.current(request)

    @action(detail=False, methods=['post'])
    def subscribe(self, request):
        """
        Initiate a GraphQL AppSubscriptionCreate.
        Body: { "plan_id": 1 }
        """
        shop = request.user
        plan_id = request.data.get('plan_id')
        
        plan = get_object_or_404(Plan, pk=plan_id)
        
        # 1. Setup Shopify Session
        shop_domain = shop.shop_domain
        access_token = shop.shopify_access_token_encrypted # Assuming plaintext for Dev
        api_version = '2024-04'
        
        # Validate token
        if not access_token:
             return Response({"error": "No access token found for shop"}, status=status.HTTP_400_BAD_REQUEST)
        
        session = shopify.Session(shop_domain, api_version, access_token)
        shopify.ShopifyResource.activate_session(session)
        
        try:
            # Check for existing active subscription to determine replacement behavior
            existing_sub = None
            replacement_behavior = None
            
            # Get existing active subscription (safe, takes latest if multiple, case-insensitive)
            existing_sub = Subscription.objects.filter(shop=shop, status__iexact='active').order_by('-created_at').first()
            
            print(f"[SUBSCRIBE] Plan requested: {plan.name}, ID: {plan.id}, Price: {plan.price}")
            if existing_sub:
                 print(f"[SUBSCRIBE] Found existing active sub: {existing_sub.id} - Plan: {existing_sub.plan.name} - Price: {existing_sub.plan.price}")
            else:
                 print(f"[SUBSCRIBE] No existing active subscription found in DB for shop {shop.shop_domain}")
            
            # Determine replacement behavior based on price comparison
            if existing_sub:
                current_price = float(existing_sub.plan.price)
                new_price = float(plan.price)
                
                if new_price > current_price:
                    # Upgrade: apply immediately with automatic proration
                    replacement_behavior = "APPLY_IMMEDIATELY"
                    print(f"[SUBSCRIBE] Upgrade detected: {existing_sub.plan.name} (${current_price}) → {plan.name} (${new_price})")
                    print(f"[SUBSCRIBE] Using APPLY_IMMEDIATELY - Shopify will prorate automatically")
                elif new_price < current_price:
                    # Downgrade: apply at next billing cycle
                    replacement_behavior = "APPLY_ON_NEXT_BILLING_CYCLE"
                    print(f"[SUBSCRIBE] Downgrade detected: {existing_sub.plan.name} (${current_price}) → {plan.name} (${new_price})")
                    print(f"[SUBSCRIBE] Using APPLY_ON_NEXT_BILLING_CYCLE - will activate at period end")
                else:
                    # Same price (e.g., interval change)
                    replacement_behavior = "APPLY_IMMEDIATELY"
            
            # 2. Construct Return URL
            host_url = os.environ.get('APP_URL') or request.build_absolute_uri('/')[:-1]
            if 'ngrok' in host_url or 'trycloudflare' in host_url:
                 if not host_url.startswith('https'):
                      host_url = host_url.replace('http', 'https')
    
            return_url = f"{host_url}/api/subscriptions/callback/?plan_id={plan.id}&shop={shop_domain}"
            
            # 3. GraphQL Mutation with replacementBehavior
            query = """
            mutation AppSubscriptionCreate($name: String!, $lineItems: [AppSubscriptionLineItemInput!]!, $returnUrl: URL!, $test: Boolean, $replacementBehavior: AppSubscriptionReplacementBehavior) {
              appSubscriptionCreate(name: $name, returnUrl: $returnUrl, lineItems: $lineItems, test: $test, replacementBehavior: $replacementBehavior) {
                userErrors {
                  field
                  message
                }
                appSubscription {
                  id
                  status
                  currentPeriodEnd
                }
                confirmationUrl
              }
            }
            """
            
            test_mode = True # Always True for Dev/Freelance request context
            
            # Extract billing interval from request ('monthly' or 'annual')
            billing_interval = request.data.get('billing_interval', 'monthly')
            
            price_amount = float(plan.price)
            if price_amount <= 0:
                 # Should not happen given current plans, but if free tier re-introduced:
                 return Response({"error": "Cannot bill 0 amount"}, status=status.HTTP_400_BAD_REQUEST)

            # Calculate final price based on interval
            # Annual = 11 months (1 free month discount)
            if billing_interval == 'annual':
                final_price = price_amount * 11
                shopify_interval = "ANNUAL"
            else:
                final_price = price_amount
                shopify_interval = "EVERY_30_DAYS"

            variables = {
                "name": f"{plan.name} Plan",
                "returnUrl": return_url,
                "test": test_mode,
                "lineItems": [{
                    "plan": {
                        "appRecurringPricingDetails": {
                            "price": {
                                "amount": final_price,
                                "currencyCode": plan.currency or "EUR"
                            },
                             "interval": shopify_interval
                        }
                    }
                }]
            }
            
            # Add replacementBehavior if there's an existing subscription
            if replacement_behavior:
                variables["replacementBehavior"] = replacement_behavior
                print(f"[SUBSCRIBE] Adding replacementBehavior: {replacement_behavior}")
            
            # Execute
            client = shopify.GraphQL()
            result = client.execute(query, variables)
            data =  json.loads(result)
            
            if 'errors' in data:
                 return Response({"error": "GraphQL Error", "details": data['errors']}, status=status.HTTP_400_BAD_REQUEST)
            
            payload = data['data']['appSubscriptionCreate']
            user_errors = payload.get('userErrors', [])
            
            if user_errors:
                 return Response({"error": "Subscription Error", "details": user_errors}, status=status.HTTP_400_BAD_REQUEST)
            
            confirmation_url = payload['confirmationUrl']
            subscription_gid = payload['appSubscription']['id'] # gid://shopify/AppSubscription/123456
            
            # 4. Save Pending Subscription
            # We store the GID as shopify_charge_id
            # CHANGE: Use create() instead of update_or_create to avoid overwriting active subscription
            Subscription.objects.create(
                shop=shop,
                plan=plan,
                shopify_charge_id=subscription_gid,
                status='pending'
            )
            
            return Response({"confirmation_url": confirmation_url})
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            shopify.ShopifyResource.clear_session()

    @action(detail=False, methods=['post'])
    def cancel(self, request):
        """
        Cancel the current subscription.
        """
        shop = request.user
        sub = Subscription.objects.filter(shop=shop, status__iexact='active').order_by('-created_at').first()
        if not sub:
             return Response({"error": "No active subscription to cancel"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Internal cleanup only if no charge ID or free tier logic (if we had one)
        if not sub.shopify_charge_id:
             sub.status = 'cancelled'
             sub.cancelled_on = timezone.now()
             sub.save()
             return Response({"message": "Subscription cancelled"})
             
        # Shopify Cancel
        shop_domain = shop.shop_domain
        access_token = shop.shopify_access_token_encrypted
        api_version = '2024-04'
        session = shopify.Session(shop_domain, api_version, access_token)
        shopify.ShopifyResource.activate_session(session)
        
        try:
            query = """
            mutation AppSubscriptionCancel($id: ID!) {
              appSubscriptionCancel(id: $id) {
                userErrors {
                  field
                  message
                }
                appSubscription {
                  id
                  status
                }
              }
            }
            """
            
            client = shopify.GraphQL()
            result = client.execute(query, {"id": sub.shopify_charge_id})
            
            # TODO: Check userErrors in result if needed
            
            sub.status = 'cancelled'
            sub.cancelled_on = timezone.now()
            sub.save()
            return Response({"message": "Subscription cancelled"})
            
        except Exception as e:
             return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
             shopify.ShopifyResource.clear_session()


    @action(detail=False, methods=['get'], permission_classes=[])
    def callback(self, request):
        """
        Handle callback from Shopify after subscription approval.
        This is called by Shopify directly, not by authenticated user.
        """
        
        # Get shop from URL parameters (not from request.user)
        shop_domain = request.GET.get('shop')
        charge_id = request.GET.get('charge_id') # Shopify sends this
        print(f"[CALLBACK] Received callback for shop: {shop_domain}, charge_id: {charge_id}")
        
        if not shop_domain:
            return Response({"error": "Missing shop parameter"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            from faq_app.models import Shop
            shop = Shop.objects.get(shop_domain=shop_domain)
            print(f"[CALLBACK] Found shop in database: {shop.id}")
        except Shop.DoesNotExist:
            print(f"[CALLBACK] ERROR: Shop not found: {shop_domain}")
            return Response({"error": "Shop not found"}, status=status.HTTP_404_NOT_FOUND)
        
        # 1. Find subscription by charge_id first so we get the exact one
        sub = None
        if charge_id:
            # Try exact match or match with GID prefix
            sub = Subscription.objects.filter(shop=shop, shopify_charge_id__endswith=charge_id).first()
        
        # Fallback to most recent if not found by ID (legacy behavior)
        if not sub:
             sub = Subscription.objects.filter(shop=shop).order_by('-created_at').first()
             
        if not sub:
              print(f"[CALLBACK] ERROR: No subscription found")
              return Response({"error": "No subscription found"}, status=status.HTTP_400_BAD_REQUEST)
              
        print(f"[CALLBACK] Found subscription ID: {sub.id}, status: {sub.status}, charge_id: {sub.shopify_charge_id}")

        # 2. Verify status on Shopify via GraphQL
        shop_domain = shop.shop_domain
        access_token = shop.shopify_access_token_encrypted
        api_version = '2024-04'
        
        session = shopify.Session(shop_domain, api_version, access_token)
        shopify.ShopifyResource.activate_session(session)
        
        try:
            gid = sub.shopify_charge_id
            
            query = """
            query AppSubscriptionStatus($id: ID!) {
              node(id: $id) {
                ... on AppSubscription {
                  status
                }
              }
            }
            """
            
            client = shopify.GraphQL()
            result = client.execute(query, {"id": gid})
            data = json.loads(result)
            
            print(f"[CALLBACK] Shopify GraphQL response: {data}")
            
            if 'data' not in data or not data['data']['node']:
                 print(f"[CALLBACK] ERROR: Subscription not found on Shopify")
                 return Response({"error": "Subscription not found on Shopify"}, status=status.HTTP_404_NOT_FOUND)
            
            status_value = data['data']['node']['status']
            print(f"[CALLBACK] Shopify subscription status: {status_value}")
            
            if status_value == 'ACTIVE':
                 sub.status = 'active'
                 sub.activated_on = timezone.now()
                 sub.save()
                 print(f"[CALLBACK] ✓ Subscription activated! ID: {sub.id}")
                 
                 store_name = shop_domain.replace('.myshopify.com', '')
                 # Redirect to products page after successful subscription
                 frontend_url = f"https://admin.shopify.com/store/{store_name}/apps/faq-manager-v1/app/products" 
                 
                 import django.shortcuts
                 return django.shortcuts.redirect(frontend_url)
            else:
                 print(f"[CALLBACK] Subscription status is {status_value}, not activating")
             
            return Response({"error": f"Subscription status is {status_value}"})
            
        except Exception as e:
             return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
             shopify.ShopifyResource.clear_session()
