from django.urls import path
from django.contrib.auth import views as auth_views
from django.views.generic.base import RedirectView
from . import views
from .views import (
    UmugandaSessionListView,
    UmugandaSessionCreateView,
    AttendanceRecordView,
    AttendanceDetailView,
    AttendanceListView,
    FineListView,
    FineUpdateView,
    CitizenListView,
    CitizenDetailView,
)

urlpatterns = [
    # Root URL redirects to home
    path('', RedirectView.as_view(url='/home/', permanent=True), name='root-redirect'),
    
    # Authentication URLs
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    
    # Password Reset URLs
    path('password_reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    
    # Base URLs
    path('home/', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile, name='profile'),
    
    # Attendance URLs
    path('attendance/', AttendanceListView.as_view(), name='attendance-list'),
    path('sessions/', UmugandaSessionListView.as_view(), name='session-list'),
    path('sessions/new/', UmugandaSessionCreateView.as_view(), name='session-create'),
    path('sessions/<int:pk>/', views.session_detail, name='session-detail'),
    path('sessions/<int:pk>/record/', AttendanceRecordView.as_view(), name='record-attendance'),
    path('sessions/<int:pk>/toggle/', views.session_toggle, name='session-toggle'),
    path('attendances/<int:pk>/', AttendanceDetailView.as_view(), name='attendance-detail'),
    
    # Fine URLs
    path('fines/', FineListView.as_view(), name='fine-list'),
    path('fines/<int:pk>/', views.fine_detail, name='fine-detail'),
    path('fines/<int:pk>/update/', FineUpdateView.as_view(), name='fine-update'),
    path('fines/<int:pk>/pay/', views.pay_fine, name='fine-pay'),
    path('fines/<int:pk>/waive/', views.waive_fine, name='fine-waive'),
    path('fines/<int:fine_id>/pay/momo/', views.initiate_momo_payment, name='initiate-momo-payment'),
    
    # Mobile Money Callback URL
    path('momo/callback/', views.momo_payment_callback, name='momo-payment-callback'),
    
    # Citizen Management URLs
    path('citizens/', CitizenListView.as_view(), name='citizen-list'),
    path('citizens/<int:pk>/', CitizenDetailView.as_view(), name='citizen-detail'),
    
    # Report URLs
    path('reports/attendance/', views.attendance_report, name='attendance-report'),
    path('reports/fines/', views.fines_report, name='fines-report'),
    path('sessions/<int:session_id>/export/', views.export_attendance_csv, name='export-attendance'),
    
    # Notification URLs
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/<int:pk>/', views.notification_detail, name='notification-detail'),
    path('notifications/<int:pk>/redirect/', views.notification_redirect, name='notification-redirect'),
    path('notifications/<int:pk>/read/', views.mark_notification_read, name='mark-notification-read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark-all-notifications-read'),
]