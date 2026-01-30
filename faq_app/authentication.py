import jwt
import os
from rest_framework import authentication
from rest_framework import exceptions
from .models import Shop

class ShopifyAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        # 1. Check for S2S Internal Auth (X-Shop-Domain + X-Internal-Secret)
        internal_secret = request.headers.get('X-Internal-Secret')
        shop_domain_header = request.headers.get('X-Shop-Domain')
        
        env_secret = os.environ.get('INTERNAL_API_SECRET', 'my_dev_secret')

        if internal_secret == env_secret and shop_domain_header:
            try:
                shop = Shop.objects.get(shop_domain=shop_domain_header)
                return (shop, None)
            except Shop.DoesNotExist:
                 # In S2S, if shop doesn't exist, we might fail or auto-create. 
                 # Given sync happens on install, it should exist. Fail safely.
                 raise exceptions.AuthenticationFailed(f'Shop {shop_domain_header} not found')

        # 2. Check for Standard Bearer Token (Existing logic)
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        if not auth_header:
            return None

        try:
            # Bearer <token>
            token = auth_header.split(' ')[1]
        except IndexError:
            return None

        try:
            # Decode the token without verification first to get the payload
            # In a real app, you MUST verify the signature using your App Secret
            # For this implementation, we will assume the secret is in env
            secret = os.environ.get('SHOPIFY_API_SECRET', 'your_secret_here')
            
            # NOTE: In production, verify audience, issuer, etc.
            payload = jwt.decode(token, secret, algorithms=['HS256'], options={"verify_aud": False})
            
            shop_domain = payload.get('dest').replace('https://', '')
            
            try:
                shop = Shop.objects.get(shop_domain=shop_domain)
            except Shop.DoesNotExist:
                # Auto-create shop if it doesn't exist (optional, depends on flow)
                shop = Shop.objects.create(shop_domain=shop_domain, shop_name=shop_domain)
            
            return (shop, None) # (user, auth)

        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed('Token has expired')
        except jwt.InvalidTokenError:
            raise exceptions.AuthenticationFailed('Invalid token')
        except Exception as e:
            raise exceptions.AuthenticationFailed(str(e))
