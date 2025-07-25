# uats/templatetags/notification_tags.py
from django import template
from django.contrib.auth import get_user_model

register = template.Library()

@register.filter
def unread_notifications_count(user):
    return user.notifications.filter(is_read=False).count()