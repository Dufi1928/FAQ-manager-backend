from django.db import models
from django.utils import timezone
from faq_app.models import Shop

class Plan(models.Model):
    """
    Subscription plans availability and features.
    """
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2) # Monthly price
    currency = models.CharField(max_length=3, default="USD")
    
    features = models.JSONField(default=dict) # e.g. {"max_products": 100, "ai_generation": True}
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} (${self.price})"

class Subscription(models.Model):
    """
    Active subscription linking a Shop to a Plan.
    """
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('frozen', 'Frozen'),
        ('cancelled', 'Cancelled'),
        ('pending', 'Pending'), # Waiting for approval
    ]

    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='subscriptions')
    
    shopify_charge_id = models.CharField(max_length=50, null=True, blank=True) # RecurringApplicationCharge ID
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    activated_on = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True) # For tracking billing cycles if needed
    
    # Pending downgrade tracking
    pending_plan = models.ForeignKey(Plan, on_delete=models.SET_NULL, null=True, blank=True, related_name='pending_subscriptions', help_text="Plan scheduled to activate at end of current period")
    pending_effective_date = models.DateTimeField(null=True, blank=True, help_text="When the pending plan will become active")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.shop} - {self.plan} ({self.status})"
