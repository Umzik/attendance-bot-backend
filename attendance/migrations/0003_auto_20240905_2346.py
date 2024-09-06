from django.db import migrations
from django.contrib.auth.hashers import make_password


def create_users(apps, schema_editor):
    User = apps.get_model('attendance', 'User')  # Replace 'your_app_name' with your app's name
    users = [
        'kamol', 'asilbek', 'saidabror', 'zarshid', 'bahriddin',
        'diyora', 'oyatillo', 'husan', 'maxsud', 'bobur',
        'islom', 'axror', 'sardor', 'arofat'
    ]

    for username in users:
        user = User(username=username, password=make_password('1'), role='employee')
        user.save()


class Migration(migrations.Migration):
    dependencies = [
        ('attendance', '0002_officelocation'),  # Replace 'previous_migration' with your last migration
    ]

    operations = [
        migrations.RunPython(create_users),
    ]
