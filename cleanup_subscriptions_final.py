import os
import django
from django.db import connection

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'faq_project.settings')
django.setup()

with connection.cursor() as cursor:
    # Drop tables if they exist
    cursor.execute("DROP TABLE IF EXISTS subscriptions_subscription")
    cursor.execute("DROP TABLE IF EXISTS subscriptions_plan")
    
    # Remove migration record
    cursor.execute("DELETE FROM django_migrations WHERE app='subscriptions'")
    print("Cleaned up subscriptions tables and migration records.")
