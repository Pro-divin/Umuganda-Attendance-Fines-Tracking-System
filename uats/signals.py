from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CustomUser, Attendance

@receiver(post_save, sender=CustomUser)
def create_welcome_notification(sender, instance, created, **kwargs):
    if created:
        from .models import Notification
        Notification.objects.create(
            user=instance,
            title="Welcome to UATS",
            message="Thank you for registering with the Umuganda Attendance Tracking System.",
            link="/profile"
        )

@receiver(post_save, sender=Attendance)
def update_attendance_notification(sender, instance, created, **kwargs):
    from .models import Notification
    if created:
        Notification.objects.create(
            user=instance.user,
            title="Attendance Recorded",
            message=f"Your attendance for Umuganda on {instance.session.date} has been recorded as {instance.get_status_display()}.",
            link="/attendance"
        )
    else:
        Notification.objects.create(
            user=instance.user,
            title="Attendance Updated",
            message=f"Your attendance for Umuganda on {instance.session.date} has been updated to {instance.get_status_display()}.",
            link="/attendance"
        )