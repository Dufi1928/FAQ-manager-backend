from rest_framework import serializers
from .models import Shop, Product, FAQ, ActivityLog, APIConfiguration, WebhookRegistration, FAQDesign

class ShopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = '__all__'
        extra_kwargs = {
            'password_hash': {'write_only': True},
            'shopify_access_token_encrypted': {'write_only': True}
        }

class ProductSerializer(serializers.ModelSerializer):
    faqs_count = serializers.SerializerMethodField()
    has_faq = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = '__all__'
    
    def get_has_faq(self, obj):
        """
        Check if product has any active FAQs
        """
        return obj.faqs.filter(is_active=True).exists()
    
    def get_faqs_count(self, obj):
        """
        Calculate total number of questions across all FAQs for this product
        """
        total = 0
        for faq in obj.faqs.filter(is_active=True):
            if faq.questions_answers:
                total += len(faq.questions_answers)
        return total

class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = ['id', 'product', 'questions_answers', 'questions_answers_en', 'questions_answers_es', 'num_questions', 'html_content', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']

class FAQDesignSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQDesign
        fields = [
            'id', 'title', 
            'question_color', 'answer_color', 'background_color', 'border_color',
            'font_family', 'font_size', 'border_radius',
            'question_icon_text', 'answer_icon_text',
            'question_icon_bg', 'question_icon_color',
            'answer_icon_bg', 'answer_icon_color',
            'custom_css', 'plan_features'
        ]
        read_only_fields = ['id']

    plan_features = serializers.SerializerMethodField()

    def get_plan_features(self, obj):
        try:
            # Check if shop has an active subscription
            subscription = getattr(obj.shop, 'subscription', None)
            if subscription and subscription.status == 'active':
                return subscription.plan.features
            
            # Default to Free plan features if no active subscription found
            # You might want to cache this or fetch "Free" plan from DB
            return {
                'max_questions': 10,
                'design_customization': False,
                'ai_generation': False
            }
        except Exception:
            return {
                'max_questions': 10,
                'design_customization': False,
                'ai_generation': False
            }


class ActivityLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityLog
        fields = '__all__'

class APIConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = APIConfiguration
        fields = '__all__'
        extra_kwargs = {
            'shopify_access_token_encrypted': {'write_only': True},
            'anthropic_api_key_encrypted': {'write_only': True},
            'openai_api_key_encrypted': {'write_only': True},
            'dataseo_api_key_encrypted': {'write_only': True}
        }

class WebhookRegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookRegistration
        fields = '__all__'
