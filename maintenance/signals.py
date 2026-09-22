from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.contrib.auth.models import Group


@receiver(post_migrate)
def create_roles(sender, **kwargs):
    if sender.name != "maintenance":
        return
    for name in ["مدیر اصلی", "سرپرست نت", "تکنسین", "اپراتور", "انبار و تدارکات"]:
        Group.objects.get_or_create(name=name)
