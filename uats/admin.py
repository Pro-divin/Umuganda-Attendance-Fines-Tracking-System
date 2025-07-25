from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils import timezone
from .models import CustomUser, UmugandaSession, Attendance, Fine, Notification

# Custom User Admin
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'get_full_name', 'user_type', 
                   'sector', 'cell', 'is_active', 'is_staff')
    list_filter = ('user_type', 'sector', 'cell', 'is_staff', 'is_active')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'national_id')
    ordering = ('last_name', 'first_name')
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': (
            'first_name', 'last_name', 'email', 
            'national_id', 'phone_number', 'date_of_birth', 'profile_picture'
        )}),
        ('Location Info', {'fields': ('sector', 'cell', 'village')}),
        ('Permissions', {'fields': (
            'user_type', 'is_active', 'is_staff', 
            'is_superuser', 'groups', 'user_permissions'
        )}),
        ('Important Dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username', 'password1', 'password2',
                'first_name', 'last_name', 'email',
                'user_type', 'sector', 'cell'
            ),
        }),
    )

# Umuganda Session Admin
@admin.register(UmugandaSession)
class UmugandaSessionAdmin(admin.ModelAdmin):
    list_display = ('date', 'sector', 'cell', 'is_active', 'created_at')
    list_filter = ('is_active', 'sector', 'cell', 'date')
    search_fields = ('description', 'sector', 'cell')
    date_hierarchy = 'date'
    ordering = ('-date',)
    actions = ['activate_sessions', 'deactivate_sessions']
    
    def activate_sessions(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} sessions activated')
    activate_sessions.short_description = "Activate selected sessions"
    
    def deactivate_sessions(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} sessions deactivated')
    deactivate_sessions.short_description = "Deactivate selected sessions"

# Attendance Admin
@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'session_info', 'status', 'timestamp', 'recorded_by')
    list_filter = ('status', 'session__sector', 'session__cell', 'session__date')
    search_fields = (
        'user__first_name', 'user__last_name', 
        'user__national_id', 'notes'
    )
    raw_id_fields = ('user', 'session', 'recorded_by')
    date_hierarchy = 'timestamp'
    ordering = ('-timestamp',)
    
    def session_info(self, obj):
        return f"{obj.session.date} - {obj.session.cell}"
    session_info.short_description = 'Session'

# Fine Admin
@admin.register(Fine)
class FineAdmin(admin.ModelAdmin):
    list_display = ('user', 'attendance_info', 'amount', 'status', 
                   'issued_date', 'paid_date')
    list_filter = ('status', 'attendance__session__sector', 
                 'attendance__session__cell')
    search_fields = (
        'user__first_name', 'user__last_name', 
        'user__national_id', 'transaction_id'
    )
    raw_id_fields = ('user', 'attendance')
    date_hierarchy = 'issued_date'
    ordering = ('-issued_date',)
    actions = ['mark_as_paid', 'mark_as_unpaid', 'waive_fines']
    
    def attendance_info(self, obj):
        return f"{obj.attendance.session.date} - {obj.attendance.user}"
    attendance_info.short_description = 'Attendance'
    
    def mark_as_paid(self, request, queryset):
        updated = queryset.update(status='paid', paid_date=timezone.now())
        self.message_user(request, f'{updated} fines marked as paid')
    mark_as_paid.short_description = "Mark selected fines as paid"
    
    def mark_as_unpaid(self, request, queryset):
        updated = queryset.update(status='unpaid', paid_date=None)
        self.message_user(request, f'{updated} fines marked as unpaid')
    mark_as_unpaid.short_description = "Mark selected fines as unpaid"
    
    def waive_fines(self, request, queryset):
        updated = queryset.update(status='waived')
        self.message_user(request, f'{updated} fines waived')
    waive_fines.short_description = "Waive selected fines"

# Notification Admin
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'is_read', 'created_at', 'short_message')
    list_filter = ('is_read', 'created_at')
    search_fields = ('user__username', 'title', 'message')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    actions = ['mark_as_read', 'mark_as_unread']
    
    def short_message(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
    short_message.short_description = 'Message'
    
    def mark_as_read(self, request, queryset):
        updated = queryset.update(is_read=True)
        self.message_user(request, f'{updated} notifications marked as read')
    mark_as_read.short_description = "Mark selected notifications as read"
    
    def mark_as_unread(self, request, queryset):
        updated = queryset.update(is_read=False)
        self.message_user(request, f'{updated} notifications marked as unread')
    mark_as_unread.short_description = "Mark selected notifications as unread"