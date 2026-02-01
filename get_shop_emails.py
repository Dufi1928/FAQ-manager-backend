import os
import django
import requests

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "faq_project.settings")
django.setup()

from faq_app.models import Shop

print("Emails des propriétaires de boutiques :")
print("=" * 60)

shops = Shop.objects.filter(is_active=True)

if shops.exists():
    for shop in shops:
        try:
            # Utiliser directement le token (peut être stocké en clair malgré le nom du champ)
            access_token = shop.shopify_access_token_encrypted
            
            if not access_token:
                print(f"⚠️  Pas de token pour {shop.shop_domain}")
                print("-" * 60)
                continue
            
            # Appeler l'API Shopify pour récupérer les informations du shop
            url = f"https://{shop.shop_domain}/admin/api/2024-01/shop.json"
            headers = {
                "X-Shopify-Access-Token": access_token
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                shop_data = response.json().get('shop', {})
                email = shop_data.get('email', 'Email non disponible')
                owner = shop_data.get('shop_owner', 'Propriétaire non disponible')
                
                print(f"📧 Email: {email}")
                print(f"👤 Propriétaire: {owner}")
                print(f"🏪 Boutique: {shop.shop_domain}")
                print("-" * 60)
            else:
                print(f"⚠️  Erreur API pour {shop.shop_domain}: {response.status_code}")
                print(f"   Message: {response.text[:100]}")
                print("-" * 60)
                
        except Exception as e:
            print(f"❌ Erreur pour {shop.shop_domain}: {str(e)}")
            print("-" * 60)
else:
    print("Aucune boutique active trouvée.")

print("\n" + "=" * 60)
print(f"Total: {shops.count()} boutiques actives")

