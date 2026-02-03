from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ShopViewSet, ProductViewSet, FAQViewSet, 
    ActivityLogViewSet, ConfigViewSet, HealthCheckView,
    SyncAuthView, FAQDesignViewSet, UninstallShopView,
    BulkActionViewSet
)

from .views_storefront import StorefrontFAQView, StorefrontProductSearchView

router = DefaultRouter()
router.register(r'shops', ShopViewSet)
router.register(r'products', ProductViewSet)
router.register(r'faq', FAQViewSet)
router.register(r'logs', ActivityLogViewSet)
router.register(r'config', ConfigViewSet, basename='config')
router.register(r'design', FAQDesignViewSet, basename='design')
router.register(r'bulk', BulkActionViewSet, basename='bulk')

urlpatterns = [
    path('health/', HealthCheckView.as_view(), name='health config'),
    path('auth/sync/', SyncAuthView.as_view(), name='auth-sync'),
    path('auth/uninstall/', UninstallShopView.as_view(), name='auth-uninstall'),
    path('storefront/faq/', StorefrontFAQView.as_view(), name='storefront-faq'),
    path('storefront/products/search/', StorefrontProductSearchView.as_view(), name='storefront-products-search'),
    path('', include(router.urls)),
]
