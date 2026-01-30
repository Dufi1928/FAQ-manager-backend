from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .models import Shop, Product, FAQ, FAQDesign
from .serializers import FAQSerializer, ProductSerializer, FAQDesignSerializer
from django.shortcuts import get_object_or_404
from django.db.models import Q

class StorefrontFAQView(APIView):
    """
    Public API endpoint to fetch FAQs for a specific product.
    Query Params:
    - shop: The shop domain (e.g., my-shop.myshopify.com)
    - product_id: The Shopify Product ID (optional)
    - handle: The Product Handle (optional)
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        shop_domain = request.query_params.get('shop')
        product_id = request.query_params.get('product_id')
        handle = request.query_params.get('handle')

        print(f"[{timezone.now()}] [StorefrontFAQView] Request: shop={shop_domain}, product_id={product_id}, handle={handle}")

        if not shop_domain:
            print(f"[{timezone.now()}] [StorefrontFAQView] Error: Missing shop parameter")
            return Response({"error": "Missing 'shop' parameter"}, status=status.HTTP_400_BAD_REQUEST)

        if not product_id and not handle:
            print(f"[{timezone.now()}] [StorefrontFAQView] Error: Missing product_id or handle")
            return Response({"error": "Missing 'product_id' or 'handle' parameter"}, status=status.HTTP_400_BAD_REQUEST)

        # Find the shop
        try:
            shop = Shop.objects.get(shop_domain=shop_domain)
        except Shop.DoesNotExist:
            print(f"[{timezone.now()}] [StorefrontFAQView] Error: Shop {shop_domain} not found")
            return Response({"error": "Shop not found"}, status=status.HTTP_404_NOT_FOUND)

        # Find the product
        product = None
        
        # Strategy 1: exact match
        if product_id:
            try:
                product = Product.objects.get(shop=shop, shopify_id=product_id)
                print(f"[{timezone.now()}] [StorefrontFAQView] Found product by exact ID: {product}")
            except Product.DoesNotExist:
                # Strategy 2: numeric string (remove 'gid://shopify/Product/')
                clean_id = str(product_id).replace("gid://shopify/Product/", "")
                try:
                    product = Product.objects.get(shop=shop, shopify_id=clean_id)
                    print(f"[{timezone.now()}] [StorefrontFAQView] Found product by clean ID: {product}")
                except Product.DoesNotExist:
                    pass
        
        # Strategy 3: Handle
        if not product and handle:
            try:
                product = Product.objects.get(shop=shop, handle=handle)
                print(f"[{timezone.now()}] [StorefrontFAQView] Found product by handle: {product}")
            except Product.DoesNotExist:
                pass

        if not product:
            print(f"[{timezone.now()}] [StorefrontFAQView] Error: Product not found for shop {shop_domain}. ID: {product_id}, Handle: {handle}")
            return Response({"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND)

        # Get the active FAQ
        try:
            faq = FAQ.objects.filter(product=product, is_active=True).latest('created_at')
            print(f"[{timezone.now()}] [StorefrontFAQView] Found FAQ: {faq.id}")
        except FAQ.DoesNotExist:
            print(f"[{timezone.now()}] [StorefrontFAQView] Warning: No active FAQ for product {product}")
            return Response({"error": "No active FAQ found for this product"}, status=status.HTTP_404_NOT_FOUND)

        # Get design settings
        design_data = {}
        try:
            design = FAQDesign.objects.get(shop=shop)
            design_data = FAQDesignSerializer(design).data
        except FAQDesign.DoesNotExist:
            # Return default design if none exists
            design_data = {
                "question_color": "#1e293b",
                "answer_color": "#475569",
                "background_color": "#ffffff",
                "border_color": "#e2e8f0",
                "font_size": 16,
                "border_radius": 12,
                "custom_css": ""
            }

        serializer = FAQSerializer(faq)
        return Response({
            "faq": serializer.data,
            "design": design_data
        })


class StorefrontProductSearchView(APIView):
    """
    Public API endpoint to search products by title.
    Query Params:
    - shop: The shop domain (e.g., my-shop.myshopify.com)
    - q: The search query (optional, matches against title)
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        shop_domain = request.query_params.get('shop')
        query = request.query_params.get('q', '').strip()

        if not shop_domain:
            return Response({"error": "Missing 'shop' parameter"}, status=status.HTTP_400_BAD_REQUEST)

        # Find the shop
        shop = get_object_or_404(Shop, shop_domain=shop_domain)

        # Filter products
        products = Product.objects.filter(shop=shop)
        
        if query:
            products = products.filter(title__icontains=query)
        
        # Limit results to 20 to avoid over-fetching
        products = products[:20]

        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)
