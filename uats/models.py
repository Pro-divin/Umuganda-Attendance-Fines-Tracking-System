from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from django.utils import timezone

class CustomUser(AbstractUser):
    USER_TYPE_CHOICES = (
        (1, 'Citizen'),
        (2, 'Local Leader'),
        (3, 'Sector Official'),
    )
    user_type = models.PositiveSmallIntegerField(choices=USER_TYPE_CHOICES, default=1)
    national_id = models.CharField(max_length=20, unique=True)
    phone_number = models.CharField(max_length=15)
    sector = models.CharField(max_length=100)
    cell = models.CharField(max_length=100)
    village = models.CharField(max_length=100, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    
    # Add these to prevent reverse accessor clashes
    groups = models.ManyToManyField(
        Group,
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name='custom_user_set',
        related_query_name='custom_user'
    )
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name='custom_user_set',
        related_query_name='custom_user'
    )
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.get_user_type_display()})"
    
    def clean(self):
        # Validate phone number format
        if not self.phone_number.startswith('+250'):
            raise ValidationError("Phone number must start with +250")
        if len(self.phone_number) != 13:
            raise ValidationError("Phone number must be 13 digits including country code")
        
        # Validate national ID format
        if len(self.national_id) != 16 or not self.national_id.isdigit():
            raise ValidationError("National ID must be 16 digits")
    
    @property
    def unread_notifications_count(self):
        return self.notifications.filter(is_read=False).count()

class UmugandaSession(models.Model):
    date = models.DateField()
    sector = models.CharField(max_length=100)
    cell = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('date', 'sector', 'cell')
        ordering = ['-date']
    
    def __str__(self):
        return f"Umuganda on {self.date} for {self.cell}"
    
    def clean(self):
        # Ensure session date is not in the future
        if self.date > timezone.now().date():
            raise ValidationError("Session date cannot be in the future")
    
    def get_attendance_stats(self):
        attendances = self.attendances.all()
        total_citizens = CustomUser.objects.filter(
            sector=self.sector,
            cell=self.cell,
            user_type=1
        ).count()
        
        stats = {
            'present': attendances.filter(status='present').count(),
            'absent': attendances.filter(status='absent').count(),
            'late': attendances.filter(status='late').count(),
            'excused': attendances.filter(status='excused').count(),
        }
        
        if total_citizens > 0:
            stats['attendance_rate'] = round((stats['present'] / total_citizens) * 100, 2)
        else:
            stats['attendance_rate'] = 0
            
        return stats

class Attendance(models.Model):
    STATUS_CHOICES = (
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('excused', 'Excused'),
    )
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='attendances')
    session = models.ForeignKey(UmugandaSession, on_delete=models.CASCADE, related_name='attendances')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    recorded_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='recorded_attendances')
    notes = models.TextField(blank=True)
    
    class Meta:
        unique_together = ('user', 'session')
        ordering = ['-session__date']
    
    def __str__(self):
        return f"{self.user} - {self.session}: {self.get_status_display()}"
    
    def save(self, *args, **kwargs):
        # Automatically create fine if status is absent
        if self.status == 'absent' and not hasattr(self, 'fine'):
            Fine.objects.create(
                user=self.user,
                attendance=self,
                amount=5000,  # Default fine amount (5000 RWF)
                status='unpaid'
            )
        super().save(*args, **kwargs)

class Fine(models.Model):
    STATUS_CHOICES = (
        ('unpaid', 'Unpaid'),
        ('paid', 'Paid'),
        ('waived', 'Waived'),
    )
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='fines')
    attendance = models.OneToOneField(Attendance, on_delete=models.CASCADE, related_name='fine')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='unpaid')
    issued_date = models.DateTimeField(auto_now_add=True)
    paid_date = models.DateTimeField(null=True, blank=True)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    payment_method = models.CharField(max_length=50, blank=True, null=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-issued_date']
    
    def __str__(self):
        return f"Fine #{self.id} - {self.user}: {self.amount} RWF ({self.status})"
    
    def save(self, *args, **kwargs):
        if self.status == 'paid' and not self.paid_date:
            self.paid_date = timezone.now()
        super().save(*args, **kwargs)

# models.py
class Notification(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=100)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)  # Add this field
    created_at = models.DateTimeField(auto_now_add=True)
    link = models.CharField(max_length=200, blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Notification for {self.user}: {self.title}"
    
    def mark_as_read(self):
        """Mark notification as read if not already read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()
            return True
        return False
@receiver(post_save, sender=Fine)
def create_fine_notification(sender, instance, created, **kwargs):
    if created:
        Notification.objects.create(
            user=instance.user,
            title="New Fine Issued",
            message=f"You have been issued a fine of {instance.amount} RWF for missing Umuganda on {instance.attendance.session.date}.",
            link=f"/fines/{instance.id}"
        )