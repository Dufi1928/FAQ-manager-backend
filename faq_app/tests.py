from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from .models import Shop, Product, FAQ
import jwt
import os
from datetime import datetime, timedelta

class ShopModelTest(TestCase):
    def test_create_shop(self):
        shop = Shop.objects.create(shop_domain="test.myshopify.com", shop_name="Test Shop")
        self.assertEqual(shop.shop_domain, "test.myshopify.com")
        self.assertTrue(shop.is_active)

class ProductModelTest(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(shop_domain="test.myshopify.com", shop_name="Test Shop")

    def test_create_product(self):
        product = Product.objects.create(
            shop=self.shop,
            shopify_id="123456789",
            title="Test Product"
        )
        self.assertEqual(product.title, "Test Product")
        self.assertEqual(product.shop, self.shop)

class APITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.shop = Shop.objects.create(shop_domain="test.myshopify.com", shop_name="Test Shop")
        
        # Generate a mock JWT token
        secret = os.environ.get('SHOPIFY_API_SECRET', 'your_secret_here')
        payload = {
            "iss": "https://test.myshopify.com/admin",
            "dest": "https://test.myshopify.com",
            "aud": "api_key",
            "sub": "123",
            "exp": datetime.utcnow() + timedelta(minutes=10),
            "nbf": datetime.utcnow(),
            "iat": datetime.utcnow(),
            "jti": "00000000-0000-0000-0000-000000000000"
        }
        self.token = jwt.encode(payload, secret, algorithm='HS256')
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.token)

    def test_get_shops(self):
        response = self.client.get('/api/shops/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_create_product_api(self):
        data = {
            "shop": self.shop.id,
            "shopify_id": "987654321",
            "title": "API Product"
        }
        response = self.client.post('/api/products/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(Product.objects.get().title, "API Product")

    def test_search_product(self):
        Product.objects.create(shop=self.shop, shopify_id="1", title="Apple")
        Product.objects.create(shop=self.shop, shopify_id="2", title="Banana")
        
        response = self.client.get('/api/products/?search=Apple')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['title'], "Apple")

class StorefrontAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.shop = Shop.objects.create(shop_domain="storefront.myshopify.com", shop_name="Storefront Shop")
        self.product = Product.objects.create(
            shop=self.shop,
            shopify_id="999",
            title="Storefront Product",
            handle="storefront-product"
        )
        self.faq = FAQ.objects.create(
            product=self.product,
            questions_answers=[{"question": "Q?", "answer": "A!"}],
            html_content="<p>Q? A!</p>",
            num_questions=1
        )

    def test_get_faq_by_product_id(self):
        response = self.client.get(f'/api/storefront/faq/?shop={self.shop.shop_domain}&product_id={self.product.shopify_id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['num_questions'], 1)

    def test_get_faq_by_handle(self):
        response = self.client.get(f'/api/storefront/faq/?shop={self.shop.shop_domain}&handle={self.product.handle}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['num_questions'], 1)

    def test_missing_params(self):
        response = self.client.get('/api/storefront/faq/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

class TestStorefrontProductSearch(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.shop = Shop.objects.create(shop_domain="test-search.myshopify.com", shop_name="Search Shop")
        
        Product.objects.create(shop=self.shop, shopify_id="101", title="Organic Apple", handle="organic-apple")
        Product.objects.create(shop=self.shop, shopify_id="102", title="Red Apple", handle="red-apple")
        Product.objects.create(shop=self.shop, shopify_id="103", title="Banana", handle="banana")
        
        # Another shop's product
        other_shop = Shop.objects.create(shop_domain="other.myshopify.com")
        Product.objects.create(shop=other_shop, shopify_id="201", title="Green Apple", handle="green-apple")

    def test_search_products(self):
        response = self.client.get(f'/api/storefront/products/search/?shop={self.shop.shop_domain}&q=Apple')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2) # Should match Organic Apple and Red Apple
        
        titles = [p['title'] for p in response.data]
        self.assertIn("Organic Apple", titles)
        self.assertIn("Red Apple", titles)
        self.assertNotIn("Banana", titles)
        self.assertNotIn("Green Apple", titles) # Should not match other shop's product

    def test_search_empty_query(self):
        # Empty query should return all products for the shop (limited to 20)
        response = self.client.get(f'/api/storefront/products/search/?shop={self.shop.shop_domain}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)

    def test_missing_shop(self):
        response = self.client.get('/api/storefront/products/search/?q=Apple')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

