from django.db import models
from django.utils import timezone

class Shop(models.Model):
    """
    Represents a shop (tenant).
    """
    shop_domain = models.CharField(max_length=255, unique=True, db_index=True)
    shop_name = models.CharField(max_length=255)
    shopify_access_token_encrypted = models.TextField(null=True, blank=True)
    password_hash = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    last_activity_at = models.DateTimeField(default=timezone.now)

    @property
    def is_authenticated(self):
        return True

    def __str__(self):
        return f"{self.shop_domain}: {self.shop_name}"

    class Meta:
        db_table = 'shops'


class Product(models.Model):
    """
    Cached Shopify product.
    """
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='products')
    shopify_id = models.CharField(max_length=50, primary_key=True) # Renamed from id to avoid conflict, but mapped to Shopify ID
    title = models.CharField(max_length=500, db_index=True)
    body_html = models.TextField(null=True, blank=True)
    handle = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    vendor = models.CharField(max_length=255, null=True, blank=True)
    product_type = models.CharField(max_length=255, null=True, blank=True)
    image_url = models.URLField(max_length=500, null=True, blank=True)  # Product thumbnail image
    
    has_faq = models.BooleanField(default=False, db_index=True)
    should_regenerate = models.BooleanField(default=True)
    
    shopify_created_at = models.DateTimeField(null=True, blank=True)
    shopify_updated_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    last_synced_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.shopify_id}: {self.title}"

    class Meta:
        db_table = 'products'
        indexes = [
            models.Index(fields=['shop', 'has_faq', 'should_regenerate']),
            models.Index(fields=['shop', 'updated_at']),
        ]


class FAQ(models.Model):
    """
    Generated FAQ content.
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='faqs')
    questions_answers = models.JSONField() # List of {"question": "...", "answer": "..."} - Default/French
    questions_answers_en = models.JSONField(null=True, blank=True) # English
    questions_answers_es = models.JSONField(null=True, blank=True) # Spanish
    html_content = models.TextField()
    num_questions = models.IntegerField()
    
    generated_with_claude = models.BooleanField(default=True)
    generated_with_dataseo = models.BooleanField(default=True)
    generation_duration_seconds = models.IntegerField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    was_manual_edit = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"FAQ for {self.product_id}"

    class Meta:
        db_table = 'faqs'
        indexes = [
            models.Index(fields=['product', 'is_active']),
        ]


class ActivityLog(models.Model):
    """
    System activity logs.
    """
    id = models.CharField(max_length=50, primary_key=True) # UUID
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='logs')
    level = models.CharField(max_length=20, db_index=True) # info, warning, error, success
    operation = models.CharField(max_length=100, db_index=True)
    
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='logs')
    product_title = models.CharField(max_length=500, null=True, blank=True)
    
    message = models.TextField()
    details = models.JSONField(null=True, blank=True)
    
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    def __str__(self):
        return f"{self.level} - {self.operation}"

    class Meta:
        db_table = 'activity_logs'
        indexes = [
            models.Index(fields=['shop', 'level', 'timestamp']),
            models.Index(fields=['shop', 'operation', 'timestamp']),
            models.Index(fields=['shop', 'timestamp']),
        ]


class APIConfiguration(models.Model):
    """
    API keys and configuration per shop.
    """
    shop = models.OneToOneField(Shop, on_delete=models.CASCADE, related_name='api_configuration')
    
    shopify_store_url = models.CharField(max_length=255)
    shopify_access_token_encrypted = models.TextField()
    shopify_api_version = models.CharField(max_length=50, null=True, blank=True)
    
    anthropic_api_key_encrypted = models.TextField(null=True, blank=True)
    has_custom_anthropic_key = models.BooleanField(default=False)
    
    openai_api_key_encrypted = models.TextField(null=True, blank=True)
    has_custom_openai_key = models.BooleanField(default=False)
    
    dataseo_api_key_encrypted = models.TextField(null=True, blank=True)
    has_custom_dataseo_key = models.BooleanField(default=False)
    
    CLAUDE_MODEL_CHOICES = [
        ('claude-3-haiku-20240307', 'Claude 3 Haiku (Plus rapide/Économique)'),
        ('claude-3-sonnet-20240229', 'Claude 3 Sonnet (Équilibré)'),
        ('claude-3-5-sonnet-20240620', 'Claude 3.5 Sonnet (Recommandé/Intelligent)'),
        ('claude-3-opus-20240229', 'Claude 3 Opus (Puissance maximale)'),
    ]
    
    claude_model = models.CharField(
        max_length=100, 
        choices=CLAUDE_MODEL_CHOICES, 
        default='claude-3-haiku-20240307'
    )
    
    custom_prompt = models.TextField(null=True, blank=True, help_text="Custom system prompt for FAQ generation")
    
    use_default_keys = models.BooleanField(default=True)
    
    is_active = models.BooleanField(default=True)
    last_validated_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Config for {self.shopify_store_url}"

    class Meta:
        db_table = 'api_configurations'


class WebhookRegistration(models.Model):
    """
    Tracked webhooks.
    """
    id = models.CharField(max_length=50, primary_key=True) # Shopify Webhook ID
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='webhook_registrations')
    topic = models.CharField(max_length=100, db_index=True)
    address = models.CharField(max_length=500)
    
    is_active = models.BooleanField(default=True)
    last_received_at = models.DateTimeField(null=True, blank=True)
    total_received = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(default=timezone.now)
    shopify_created_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Webhook registration for {self.topic} on {self.shop.shop_domain}"


class FAQDesign(models.Model):
    """
    Stores visual customization settings for the FAQ display.
    """
    shop = models.OneToOneField(Shop, on_delete=models.CASCADE, related_name='faq_design')
    
    # Content
    title = models.CharField(max_length=200, default="Questions Fréquentes", help_text="Title of the FAQ section")
    
    # Layout Model
    LAYOUT_CHOICES = [
        ('classic', 'Accordéon Classique'),
        ('modern', 'Accordéon Moderne'),
        ('minimal', 'Liste Minimaliste'),
        ('cards', 'Grille de Cartes'),
    ]
    layout_model = models.CharField(max_length=50, choices=LAYOUT_CHOICES, default='classic')

    # Colors
    question_color = models.CharField(max_length=20, default="#1e293b")
    answer_color = models.CharField(max_length=20, default="#475569")
    background_color = models.CharField(max_length=20, default="#ffffff")
    border_color = models.CharField(max_length=20, default="#e2e8f0")
    
    # Typography & Spacing
    font_family = models.CharField(max_length=100, default="system-ui", help_text="Font family")
    font_size = models.IntegerField(default=16, help_text="Font size in pixels")
    border_radius = models.IntegerField(default=12, help_text="Border radius in pixels")
    
    # Icon Customization
    question_icon_text = models.CharField(max_length=10, default="Q", help_text="Text/emoji for question icon")
    answer_icon_text = models.CharField(max_length=10, default="R", help_text="Text/emoji for answer icon")
    question_icon_bg = models.CharField(max_length=20, default="#e0f2fe", help_text="Background color for Q icon")
    question_icon_color = models.CharField(max_length=20, default="#0369a1", help_text="Text color for Q icon")
    answer_icon_bg = models.CharField(max_length=20, default="#f0fdf4", help_text="Background color for R icon")
    answer_icon_color = models.CharField(max_length=20, default="#15803d", help_text="Text color for R icon")
    
    # Advanced
    custom_css = models.TextField(blank=True, null=True, help_text="Custom CSS to override styles")
    
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Design for {self.shop.shop_domain}"

    class Meta:
        db_table = 'faq_designs'
