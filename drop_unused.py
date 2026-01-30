
from django.db import connection

def drop_table():
    with connection.cursor() as cursor:
        try:
            cursor.execute("DROP TABLE alembic_version")
            print("Dropped table alembic_version")
        except Exception as e:
            print(f"Error dropping table: {e}")

if __name__ == "__main__":
    import os
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'faq_project.settings')
    django.setup()
    drop_table()
