import os
import django
import sys

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection

def main():
    print("Clearing metrics tables and migrations from database...")
    with connection.cursor() as cursor:
        # Drop dependent tables first
        cursor.execute("DROP TABLE IF EXISTS metrics_metricreading CASCADE;")
        cursor.execute("DROP TABLE IF EXISTS metrics_server CASCADE;")
        
        # Clear migration log
        cursor.execute("DELETE FROM django_migrations WHERE app = 'metrics';")
        
    print("Database metrics resources cleared successfully!")

if __name__ == "__main__":
    main()
