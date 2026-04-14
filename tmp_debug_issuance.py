import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.test import Client
from django.contrib.auth import get_user_model
User = get_user_model()
user = User.objects.filter(groups__name='Management').first()
print('user', getattr(user, 'username', None))
client = Client()
client.force_login(user)
response = client.get('/history/issuance/management/')
print('status', response.status_code)
print(response.content[:4000].decode('utf-8', 'ignore'))
