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
            subscription = Subscription.objects.get(shop=shop)
            serializer = SubscriptionSerializer(subscription)
            return Response(serializer.data)
        except Subscription.DoesNotExist:
            return Response(None, status=status.HTTP_204_NO_CONTENT)

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
            # 2. Construct Return URL
            host_url = os.environ.get('APP_URL') or request.build_absolute_uri('/')[:-1]
            if 'ngrok' in host_url or 'trycloudflare' in host_url:
                 if not host_url.startswith('https'):
                      host_url = host_url.replace('http', 'https')
    
            return_url = f"{host_url}/api/subscriptions/callback/?plan_id={plan.id}"
            
            # 3. GraphQL Mutation
            query = """
            mutation AppSubscriptionCreate($name: String!, $lineItems: [AppSubscriptionLineItemInput!]!, $returnUrl: URL!, $test: Boolean) {
              appSubscriptionCreate(name: $name, returnUrl: $returnUrl, lineItems: $lineItems, test: $test) {
                userErrors {
                  field
                  message
                }
                appSubscription {
                  id
                }
                confirmationUrl
              }
            }
            """
            
            test_mode = True # Always True for Dev/Freelance request context
            
            price_amount = float(plan.price)
            if price_amount <= 0:
                 # Should not happen given current plans, but if free tier re-introduced:
                 return Response({"error": "Cannot bill 0 amount"}, status=status.HTTP_400_BAD_REQUEST)

            variables = {
                "name": f"{plan.name} Plan",
                "returnUrl": return_url,
                "test": test_mode,
                "lineItems": [{
                    "plan": {
                        "appRecurringPricingDetails": {
                            "price": {
                                "amount": price_amount,
                                "currencyCode": "USD" # Assuming USD. If EUR needed, adjust.
                            },
                             "interval": "EVERY_30_DAYS"
                        }
                    }
                }]
            }
            
            # Execute
            client = shopify.GraphQL()
            result = client.execute(query, variables)
            data =  shopify.json.loads(result)
            
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
            Subscription.objects.update_or_create(
                shop=shop,
                defaults={
                    'plan': plan,
                    'shopify_charge_id': subscription_gid,
                    'status': 'pending'
                }
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
        try:
            sub = Subscription.objects.get(shop=shop, status='active')
        except Subscription.DoesNotExist:
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


    @action(detail=False, methods=['get'])
    def callback(self, request):
        """
        Handle callback from Shopify.
        """
        shop = request.user
        
        # 1. Find pending subscription
        try:
             # Get the most recent pending or active (status might have updated?)
             sub = Subscription.objects.filter(shop=shop).order_by('-updated_at').first()
             if not sub or not sub.shopify_charge_id:
                  return Response({"error": "No pending subscription found"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
             return Response({"error": "Database error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
            data = shopify.json.loads(result)
            
            if 'data' not in data or not data['data']['node']:
                 # Try adding/removing gid prefix if mismatch? 
                 # But we stored exactly what create returned.
                 return Response({"error": "Subscription not found on Shopify"}, status=status.HTTP_404_NOT_FOUND)
            
            status_value = data['data']['node']['status']
            
            if status_value == 'ACTIVE':
                 sub.status = 'active'
                 sub.activated_on = timezone.now()
                 sub.save()
                 
                 store_name = shop_domain.replace('.myshopify.com', '')
                 # Using the valid app handle found in shopify.app.toml
                 frontend_url = f"https://admin.shopify.com/store/{store_name}/apps/faq-app-frontend/app/pricing" 
                 
                 import django.shortcuts
                 return django.shortcuts.redirect(frontend_url)
            
            return Response({"error": f"Subscription status is {status_value}"})
            
        except Exception as e:
             return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
             shopify.ShopifyResource.clear_session()
