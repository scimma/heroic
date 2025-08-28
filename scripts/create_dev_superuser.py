#!/usr/bin/env python
"""
Create a development superuser and display its API token
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'local_settings')
django.setup()

from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token

# Create or get superuser
username = 'admin'
email = 'admin@example.com'
password = 'admin123'  # Change this in production!

try:
    user = User.objects.get(username=username)
    print(f"Superuser '{username}' already exists")
except User.DoesNotExist:
    user = User.objects.create_superuser(username=username, email=email, password=password)
    print(f"Created superuser '{username}' with password '{password}'")

# Create or get token
token, created = Token.objects.get_or_create(user=user)

print(f"\nAPI Token: {token.key}")
print(f"\nTo use the API, add this header to your requests:")
print(f"Authorization: Token {token.key}")
print(f"\nExample curl command:")
print(f"""curl -X POST http://localhost:8000/api/observatories/ \\
  -H "Authorization: Token {token.key}" \\
  -H "Content-Type: application/json" \\
  -d '{{"id": "ligo", "name": "Laser Interferometer Gravitational-Wave Observatory"}}'""")