# Generated manually to rename Product.id to Product.shopify_id

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('faq_app', '0002_alter_apiconfiguration_id_alter_faq_id_alter_shop_id'),
    ]

    operations = [
        migrations.RunSQL(
            # Rename the 'id' column to 'shopify_id'
            sql="ALTER TABLE products CHANGE COLUMN id shopify_id VARCHAR(50) NOT NULL;",
            reverse_sql="ALTER TABLE products CHANGE COLUMN shopify_id id VARCHAR(50) NOT NULL;",
        ),
    ]
