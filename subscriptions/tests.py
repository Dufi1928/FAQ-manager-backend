from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from faq_app.models import Shop
from .models import Plan, Subscription
from unittest.mock import patch

class SubscriptionTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.shop = Shop.objects.create(shop_domain="sub-test.myshopify.com", shop_name="Sub Shop")
        self.client.force_authenticate(user=self.shop)
        
        self.plan = Plan.objects.create(name="Pro Plan", price=9.99, is_active=True)

    def test_list_plans(self):
        response = self.client.get('/api/subscriptions/plans/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Handle pagination
        results = response.data['results'] if 'results' in response.data else response.data
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['name'], "Pro Plan")

    @patch('subscriptions.views.requests.post')
    def test_create_charge(self, mock_post):
        # Mock Shopify response
        mock_post.return_value.status_code = 201
        mock_post.return_value.json.return_value = {
            "recurring_application_charge": {
                "id": 12345,
                "confirmation_url": "https://shopify.com/confirm",
                "status": "pending"
            }
        }

        response = self.client.post('/api/subscriptions/create_charge/', {"plan_id": self.plan.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['confirmation_url'], "https://shopify.com/confirm")
        
        # Check DB
        sub = Subscription.objects.get(shop=self.shop)
        self.assertEqual(sub.status, 'pending')
        self.assertEqual(sub.shopify_charge_id, '12345')

    @patch('subscriptions.views.requests.get')
    @patch('subscriptions.views.requests.post')
    def test_callback_activation(self, mock_post, mock_get):
        # Setup pending sub
        Subscription.objects.create(shop=self.shop, plan=self.plan, shopify_charge_id="12345", status="pending")

        # Mock GET info
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "recurring_application_charge": {
                "id": 12345,
                "status": "accepted"
            }
        }
        
        # Mock POST activate
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {}

        response = self.client.get('/api/subscriptions/callback/?charge_id=12345')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check DB
        sub = Subscription.objects.get(shop=self.shop)
        self.assertEqual(sub.status, 'active')
        self.assertIsNotNone(sub.activated_on)
