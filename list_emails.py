import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "faq_project.settings")
django.setup()

from faq_app.models import Shop

print("Boutiques dans la base de données :")
print("=" * 50)

shops = Shop.objects.all()

if shops.exists():
    for shop in shops:
        print(f"Domaine: {shop.shop_domain}")
        print(f"Nom: {shop.shop_name}")
        print("-" * 50)
else:
    print("Aucune boutique trouvée dans la base de données.")

print("\n" + "=" * 50)
print(f"Total: {shops.count()} boutiques")

