import os
import django
from django.db import connection

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'faq_project.settings')
django.setup()

with connection.cursor() as cursor:
    cursor.execute("DESCRIBE shops")
    columns = cursor.fetchall()
    for col in columns:
        print(col)
        
    print("-" * 20)
    cursor.execute("SHOW TABLE STATUS LIKE 'shops'")
    status = cursor.fetchone()
    print(status)
