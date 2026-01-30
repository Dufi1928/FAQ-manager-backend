#!/usr/bin/env python
"""
Script to check and fix Product table structure
"""
import os
import sys
import django

# Setup Django settings
sys.path.insert(0, '/Users/ivan/Desktop/Projects/FRELANCE/FAQ APP/DJANGO_BACKEND')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'faq_project.settings')
django.setup()

from django.db import connection

def check_products_table():
    """Check the structure of the products table"""
    with connection.cursor() as cursor:
        # Show the current table structure
        cursor.execute("DESCRIBE products;")
        columns = cursor.fetchall()
        
        print("Current products table structure:")
        print("-" * 80)
        for col in columns:
            print(f"{col[0]:30} {col[1]:20} NULL={col[2]} Key={col[3]}")
        print("-" * 80)
        
        # Check if shopify_id column exists
        column_names = [col[0] for col in columns]
        
        if 'shopify_id' not in column_names:
            print("\n❌ ERROR: shopify_id column is missing!")
            print("\nAttempting to fix by adding shopify_id column...")
            
            # Check if there's an 'id' column that should be renamed
            if 'id' in column_names:
                print("Found 'id' column. This might be the issue.")
                print("\nSuggested fix:")
                print("1. The table structure doesn't match the model")
                print("2. We need to recreate the table or manually alter it")
                
                # Let's check if there's any data
                cursor.execute("SELECT COUNT(*) FROM products;")
                count = cursor.fetchone()[0]
                print(f"\nCurrent row count in products table: {count}")
                
                if count == 0:
                    print("\n✓ Table is empty. Safe to recreate.")
                    print("\nExecuting: DROP TABLE products;")
                    cursor.execute("DROP TABLE products;")
                    print("✓ Table dropped successfully")
                    
                    print("\nPlease run: python manage.py migrate faq_app")
                else:
                    print(f"\n⚠️  Table has {count} rows. Manual intervention required.")
                    print("You need to backup data and recreate the table.")
            else:
                print("Column 'id' not found either. Table structure is completely wrong.")
        else:
            print("\n✅ shopify_id column exists!")
            print("The database structure is correct.")

if __name__ == '__main__':
    try:
        check_products_table()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
