from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.decorators.http import require_POST
from .models import CustomUser, UmugandaSession, Attendance, Fine, Notification
from .forms import (
    UserRegisterForm, 
    UserLoginForm,
    ProfileUpdateForm,
    UmugandaSessionForm,
    AttendanceForm,
    FineUpdateForm,
    FinePaymentForm,
    CitizenSearchForm
)
from django.db.models import Count, Sum, Q
import csv
from datetime import date, timedelta
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from django.views.decorators.csrf import csrf_exempt
import json

# Helper functions
def check_session_permission(user, session):
    """Check if user has permission to access a session"""
    if user.user_type == 2:  # Local Leader
        return session.cell == user.cell and session.sector == user.sector
    elif user.user_type == 3:  # Sector Official
        return session.sector == user.sector
    return False

def check_fine_permission(user, fine):
    """Check if user has permission to access a fine"""
    if user.user_type == 1:  # Citizen
        return fine.user == user
    elif user.user_type == 2:  # Local Leader
        return (fine.attendance.session.cell == user.cell and 
                fine.attendance.session.sector == user.sector)
    elif user.user_type == 3:  # Sector Official
        return fine.attendance.session.sector == user.sector
    return False

# Authentication Views
def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Account created successfully!')
            return redirect('dashboard')
    else:
        form = UserRegisterForm()
    return render(request, 'uats/auth/register.html', {'form': form})

def user_login(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {user.first_name}!')
                return redirect('dashboard')
    else:
        form = UserLoginForm()
    return render(request, 'uats/auth/login.html', {'form': form})

def user_logout(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('home')

# Base Views
def home(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'uats/home.html')

@login_required
def dashboard(request):
    user = request.user
    context = {}
    
    if user.user_type == 1:  # Citizen
        # Get all attendance records with session info
        attendances = Attendance.objects.filter(
            user=user
        ).select_related('session').order_by('-session__date')
        
        # Separate completed and upcoming sessions
        today = timezone.now().date()
        completed_attendances = attendances.filter(session__date__lte=today)
        upcoming_attendances = attendances.filter(session__date__gt=today)
        
        # Calculate statistics only for completed sessions
        total_sessions = completed_attendances.count()
        present_count = completed_attendances.filter(status='present').count()
        absent_count = completed_attendances.filter(status='absent').count()
        late_count = completed_attendances.filter(status='late').count()
        excused_count = completed_attendances.filter(status='excused').count()
        
        attendance_rate = 0
        if total_sessions > 0:
            attendance_rate = round((present_count / total_sessions) * 100, 2)
        
        context.update({
            'completed_attendances': completed_attendances[:5],
            'upcoming_attendances': upcoming_attendances[:3],
            'fines': Fine.objects.filter(user=user).order_by('-issued_date')[:5],
            'notifications': Notification.objects.filter(
                user=user,
                is_read=False
            ).order_by('-created_at')[:5],
            'total_sessions': total_sessions,
            'present_count': present_count,
            'absent_count': absent_count,
            'late_count': late_count,
            'excused_count': excused_count,
            'attendance_rate': attendance_rate,
            'unpaid_fines_count': Fine.objects.filter(
                user=user, 
                status='unpaid'
            ).count(),
        })
    
    elif user.user_type == 2:  # Local Leader
        sessions = UmugandaSession.objects.filter(
            cell=user.cell,
            sector=user.sector
        ).order_by('-date')[:5]
        
        recent_attendances = Attendance.objects.filter(
            session__cell=user.cell,
            session__sector=user.sector
        ).order_by('-timestamp')[:5]
        
        unpaid_fines = Fine.objects.filter(
            attendance__session__cell=user.cell,
            attendance__session__sector=user.sector,
            status='unpaid'
        ).count()
        
        context.update({
            'sessions': sessions,
            'recent_attendances': recent_attendances,
            'unpaid_fines': unpaid_fines,
        })
    
    elif user.user_type == 3:  # Sector Official
        unpaid_fines = Fine.objects.filter(
            attendance__session__sector=user.sector,
            status='unpaid'
        ).count()
        
        sessions = UmugandaSession.objects.filter(sector=user.sector).order_by('-date')[:5]
        
        if sessions.exists():
            last_session = sessions[0]
            present_count = Attendance.objects.filter(
                session=last_session,
                status='present'
            ).count()
            total_citizens = CustomUser.objects.filter(
                sector=user.sector,
                user_type=1
            ).count()
            attendance_rate = round((present_count / total_citizens) * 100, 2) if total_citizens else 0
            
            context['last_session_stats'] = {
                'session': last_session,
                'attendance_rate': attendance_rate,
                'present_count': present_count,
                'total_citizens': total_citizens,
            }
        
        context.update({
            'sessions': sessions,
            'unpaid_fines': unpaid_fines,
        })
    
    return render(request, 'uats/dashboard.html', context)

# MTN Mobile Money Payment Views
@login_required
@csrf_exempt
def initiate_momo_payment(request, fine_id):
    fine = get_object_or_404(Fine, pk=fine_id, user=request.user)
    
    if fine.status == 'paid':
        return JsonResponse({'status': 'error', 'message': 'Fine already paid'})
    
    momo = MTNMobileMoney()
    response = momo.request_payment(
        amount=fine.amount,
        phone_number=request.user.phone_number,
        external_id=str(fine.id),
        payee_note=f"Payment for fine #{fine.id}",
        payer_message=f"Umuganda fine payment"
    )
    
    if response['status'] == 'success':
        # Save the reference ID to your payment model
        fine.momo_reference = response['reference_id']
        fine.save()
        return JsonResponse({
            'status': 'success',
            'message': 'Payment request initiated',
            'reference_id': response['reference_id']
        })
    else:
        return JsonResponse({
            'status': 'error',
            'message': response.get('message', 'Payment request failed'),
            'details': response.get('response', {})
        }, status=400)

@csrf_exempt
def momo_payment_callback(request):
    """Handle MTN MOMO payment callback"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            reference_id = data.get('financialTransactionId')
            status = data.get('status')
            
            # Update payment status based on callback
            try:
                fine = Fine.objects.get(momo_reference=reference_id)
                if status == 'SUCCESSFUL':
                    fine.status = 'paid'
                    fine.payment_method = 'mobile_money'
                    fine.payment_date = timezone.now()
                    fine.save()
                    
                    Notification.objects.create(
                        user=fine.user,
                        title="Fine Payment Confirmation",
                        message=f"Your fine of {fine.amount} RWF has been paid successfully via Mobile Money.",
                        link=reverse('fine-detail', kwargs={'pk': fine.pk})
                    )
            except Fine.DoesNotExist:
                pass
            
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

# Profile Views
@login_required
def profile(request):
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated!')
            return redirect('profile')
    else:
        form = ProfileUpdateForm(instance=request.user)
    return render(request, 'uats/profile.html', {'form': form})

# Attendance Views
class AttendanceListView(LoginRequiredMixin, ListView):
    model = Attendance
    template_name = 'uats/attendance/attendance_list.html'
    context_object_name = 'attendances'
    paginate_by = 20
    
    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset().select_related('user', 'session')
        
        if user.user_type == 1:  # Citizen
            queryset = queryset.filter(user=user)
        elif user.user_type == 2:  # Local Leader
            queryset = queryset.filter(
                session__cell=user.cell,
                session__sector=user.sector
            )
        elif user.user_type == 3:  # Sector Official
            queryset = queryset.filter(session__sector=user.sector)
        
        date_filter = self.request.GET.get('date')
        if date_filter:
            queryset = queryset.filter(session__date=date_filter)
            
        return queryset.order_by('-session__date')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_date_filter'] = self.request.GET.get('date', '')
        
        if self.request.user.user_type in [2, 3]:
            context['available_dates'] = (
                Attendance.objects
                .dates('session__date', 'day')
                .distinct()
                .order_by('-session__date')
            )
            
        return context

class UmugandaSessionListView(LoginRequiredMixin, ListView):
    model = UmugandaSession
    template_name = 'uats/attendance/session_list.html'
    context_object_name = 'sessions'
    paginate_by = 10
    
    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()
        
        if user.user_type == 2:  # Local Leader
            queryset = queryset.filter(
                cell=user.cell,
                sector=user.sector
            )
        elif user.user_type == 3:  # Sector Official
            queryset = queryset.filter(sector=user.sector)
        
        return queryset.order_by('-date')

class UmugandaSessionCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = UmugandaSession
    form_class = UmugandaSessionForm
    template_name = 'uats/attendance/session_form.html'
    success_url = reverse_lazy('session-list')
    
    def test_func(self):
        return self.request.user.user_type in [2, 3]  # Only leaders and officials
    
    def form_valid(self, form):
        user = self.request.user
        form.instance.sector = user.sector
        if user.user_type == 2:  # Local Leader
            form.instance.cell = user.cell
        messages.success(self.request, 'Umuganda session created successfully!')
        return super().form_valid(form)

class AttendanceRecordView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Attendance
    form_class = AttendanceForm
    template_name = 'uats/attendance/record_attendance.html'
    
    def test_func(self):
        return self.request.user.user_type == 2  # Only local leaders
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        session = get_object_or_404(UmugandaSession, pk=self.kwargs.get('pk'))
        
        if not check_session_permission(self.request.user, session):
            raise PermissionDenied
        
        citizens = CustomUser.objects.filter(
            cell=self.request.user.cell,
            sector=self.request.user.sector,
            user_type=1
        ).order_by('last_name', 'first_name')
        
        attendances = Attendance.objects.filter(session=session).select_related('user')
        attendance_map = {att.user.id: att for att in attendances}
        
        context['session'] = session
        context['attendance_data'] = [{
            'user': citizen,
            'status': attendance_map.get(citizen.id, {}).get('status', ''),
            'notes': attendance_map.get(citizen.id, {}).get('notes', ''),
            'attendance_id': attendance_map.get(citizen.id, {}).get('id'),
        } for citizen in citizens]
        
        return context
    
    def post(self, request, *args, **kwargs):
        session = get_object_or_404(UmugandaSession, pk=self.kwargs.get('pk'))
        leader = request.user
        
        if not check_session_permission(leader, session):
            raise PermissionDenied
        
        for key, value in request.POST.items():
            if key.startswith('status_'):
                user_id = key.split('_')[1]
                try:
                    citizen = CustomUser.objects.get(pk=user_id)
                    status = value
                    notes = request.POST.get(f'notes_{user_id}', '')
                    
                    att, created = Attendance.objects.update_or_create(
                        user=citizen,
                        session=session,
                        defaults={
                            'status': status,
                            'recorded_by': leader,
                            'notes': notes,
                            'timestamp': timezone.now(),
                        }
                    )
                    
                    if status == 'absent':
                        Fine.objects.get_or_create(
                            user=citizen,
                            attendance=att,
                            defaults={
                                'amount': 5000,
                                'reason': 'Absence from Umuganda',
                                'due_date': timezone.now().date() + timedelta(days=30)
                            }
                        )
                    else:
                        Fine.objects.filter(attendance=att).delete()
                        
                except CustomUser.DoesNotExist:
                    messages.error(request, f"Invalid user ID: {user_id}")
                    continue
        
        messages.success(request, 'Attendance recorded successfully!')
        return redirect('session-detail', pk=session.id)

class AttendanceDetailView(LoginRequiredMixin, DetailView):
    model = Attendance
    template_name = 'uats/attendance/attendance_detail.html'
    context_object_name = 'attendance'
    
    def get_queryset(self):
        user = self.request.user
        if user.user_type == 1:
            return Attendance.objects.filter(user=user)
        elif user.user_type == 2:
            return Attendance.objects.filter(
                session__cell=user.cell, 
                session__sector=user.sector
            )
        elif user.user_type == 3:
            return Attendance.objects.filter(session__sector=user.sector)
        return Attendance.objects.none()

# Fine Views
class FineListView(LoginRequiredMixin, ListView):
    model = Fine
    template_name = 'uats/fines/fine_list.html'
    context_object_name = 'fines'
    paginate_by = 10
    
    def get_queryset(self):
        user = self.request.user
        queryset = Fine.objects.select_related('user', 'attendance__session')
        
        if user.user_type == 1:
            return queryset.filter(user=user)
        elif user.user_type == 2:
            return queryset.filter(
                attendance__session__cell=user.cell,
                attendance__session__sector=user.sector
            )
        elif user.user_type == 3:
            return queryset.filter(attendance__session__sector=user.sector)
        return Fine.objects.none()

class FineUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Fine
    form_class = FineUpdateForm
    template_name = 'uats/fines/fine_form.html'
    
    def test_func(self):
        return check_fine_permission(self.request.user, self.get_object())
    
    def get_success_url(self):
        messages.success(self.request, 'Fine updated successfully!')
        return reverse_lazy('fine-detail', kwargs={'pk': self.object.pk})

@login_required
def pay_fine(request, pk):
    fine = get_object_or_404(Fine, pk=pk)
    
    if fine.user != request.user:
        raise PermissionDenied
    
    if request.method == 'POST':
        form = FinePaymentForm(request.POST)
        if form.is_valid():
            fine.status = 'paid'
            fine.payment_method = form.cleaned_data['payment_method']
            fine.transaction_id = form.cleaned_data['transaction_id']
            fine.payment_date = timezone.now()
            fine.save()
            
            Notification.objects.create(
                user=fine.user,
                title="Fine Payment Confirmation",
                message=f"Your fine of {fine.amount} RWF has been paid successfully.",
                link=reverse('fine-detail', kwargs={'pk': fine.pk})
            )
            
            messages.success(request, 'Fine paid successfully!')
            return redirect('fine-detail', pk=fine.pk)
    else:
        form = FinePaymentForm()
    
    return render(request, 'uats/fines/pay_fine.html', {
        'fine': fine,
        'form': form,
    })

@login_required
def waive_fine(request, pk):
    if request.user.user_type not in [2, 3]:
        raise PermissionDenied
    
    fine = get_object_or_404(Fine, pk=pk)
    
    if not check_fine_permission(request.user, fine):
        raise PermissionDenied
    
    if request.method == 'POST':
        fine.status = 'waived'
        fine.waived_by = request.user
        fine.save()
        
        Notification.objects.create(
            user=fine.user,
            title="Fine Waived",
            message=f"Your fine of {fine.amount} RWF has been waived by {request.user.get_full_name()}.",
            link=reverse('fine-detail', kwargs={'pk': fine.pk})
        )
        
        messages.success(request, 'Fine has been waived successfully!')
        return redirect('fine-detail', pk=fine.pk)
    
    return render(request, 'uats/fines/waive_confirm.html', {'fine': fine})

@login_required
def fine_detail(request, pk):
    fine = get_object_or_404(Fine, pk=pk)
    if not check_fine_permission(request.user, fine):
        raise PermissionDenied
    
    can_pay = fine.status == 'unpaid' and fine.user == request.user
    can_waive = (fine.status == 'unpaid' and 
                 request.user.user_type in [2, 3] and 
                 check_fine_permission(request.user, fine))
    
    return render(request, 'uats/fines/fine_detail.html', {
        'fine': fine,
        'can_pay': can_pay,
        'can_waive': can_waive,
    })

# Citizen Management Views
class CitizenListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = CustomUser
    template_name = 'uats/citizens/citizen_list.html'
    context_object_name = 'citizens'
    paginate_by = 20
    
    def test_func(self):
        return self.request.user.user_type in [2, 3]
    
    def get_queryset(self):
        user = self.request.user
        queryset = CustomUser.objects.filter(user_type=1)
        
        if user.user_type == 2:
            queryset = queryset.filter(cell=user.cell, sector=user.sector)
        elif user.user_type == 3:
            queryset = queryset.filter(sector=user.sector)
        
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(national_id__icontains=search_query) |
                Q(phone_number__icontains=search_query)
            )
        
        return queryset.order_by('last_name', 'first_name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = CitizenSearchForm(self.request.GET or None)
        return context

class CitizenDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = CustomUser
    template_name = 'uats/citizens/citizen_detail.html'
    context_object_name = 'citizen'
    
    def test_func(self):
        user = self.request.user
        citizen = self.get_object()
        
        if user.user_type == 1:
            return citizen == user
        elif user.user_type == 2:
            return citizen.cell == user.cell and citizen.sector == user.sector
        elif user.user_type == 3:
            return citizen.sector == user.sector
        return False
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        citizen = self.object
        
        session_filter = Q(sector=citizen.sector)
        if citizen.cell:
            session_filter &= Q(cell=citizen.cell)

        total_sessions = UmugandaSession.objects.filter(
            session_filter, date__lte=timezone.now().date()
        ).count()

        present_count = Attendance.objects.filter(
            user=citizen, status='present', 
            session__in=UmugandaSession.objects.filter(session_filter)
        ).count()

        attendance_rate = round((present_count / total_sessions) * 100, 2) if total_sessions else 0
        
        context.update({
            'attendances': Attendance.objects.filter(user=citizen)
                .select_related('session').order_by('-session__date')[:10],
            'fines': Fine.objects.filter(user=citizen).order_by('-issued_date')[:10],
            'total_sessions': total_sessions,
            'present_count': present_count,
            'attendance_rate': attendance_rate,
        })
        return context

# Report Views
@login_required
def attendance_report(request):
    user = request.user
    if user.user_type == 1:
        return redirect('dashboard')
    
    year = request.GET.get('year', timezone.now().year)
    
    if user.user_type == 2:
        sessions = UmugandaSession.objects.filter(
            cell=user.cell, sector=user.sector, date__year=year
        ).order_by('date')
    else:
        sessions = UmugandaSession.objects.filter(
            sector=user.sector, date__year=year
        ).order_by('date')
    
    report_data = []
    for session in sessions:
        counts = Attendance.objects.filter(session=session).aggregate(
            present=Count('pk', filter=Q(status='present')),
            absent=Count('pk', filter=Q(status='absent')),
            late=Count('pk', filter=Q(status='late')),
            excused=Count('pk', filter=Q(status='excused')),
        )
        
        report_data.append({
            'session': session,
            'present': counts['present'] or 0,
            'absent': counts['absent'] or 0,
            'late': counts['late'] or 0,
            'excused': counts['excused'] or 0,
        })
    
    return render(request, 'uats/reports/attendance_report.html', {
        'report_data': report_data,
        'year': year,
        'available_years': UmugandaSession.objects.dates('date', 'year').distinct(),
    })

@login_required
def fines_report(request):
    user = request.user
    if user.user_type == 1:
        return redirect('dashboard')
    
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if user.user_type == 2:
        fines = Fine.objects.filter(
            attendance__session__cell=user.cell,
            attendance__session__sector=user.sector
        )
    else:
        fines = Fine.objects.filter(attendance__session__sector=user.sector)
    
    if start_date:
        fines = fines.filter(issued_date__gte=start_date)
    if end_date:
        fines = fines.filter(issued_date__lte=end_date)
    
    aggregates = fines.aggregate(
        total_fines=Count('pk'),
        total_amount=Sum('amount'),
        paid_fines=Count('pk', filter=Q(status='paid')),
        unpaid_fines=Count('pk', filter=Q(status='unpaid')),
        waived_fines=Count('pk', filter=Q(status='waived'))
    )
    
    return render(request, 'uats/reports/fines_report.html', {
        'fines': fines.select_related('user', 'attendance__session')[:50],
        'total_fines': aggregates['total_fines'] or 0,
        'total_amount': aggregates['total_amount'] or 0,
        'paid_fines': aggregates['paid_fines'] or 0,
        'unpaid_fines': aggregates['unpaid_fines'] or 0,
        'waived_fines': aggregates['waived_fines'] or 0,
        'start_date': start_date,
        'end_date': end_date,
    })

# Export Views
@login_required
def export_attendance_csv(request, session_id):
    session = get_object_or_404(UmugandaSession, pk=session_id)
    
    if not check_session_permission(request.user, session):
        raise PermissionDenied
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="attendance_{session.date}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['National ID', 'Name', 'Phone', 'Status', 'Recorded By', 'Timestamp', 'Notes'])
    
    attendances = Attendance.objects.filter(session=session).select_related('user', 'recorded_by')
    for att in attendances:
        writer.writerow([
            att.user.national_id,
            f"{att.user.first_name} {att.user.last_name}",
            att.user.phone_number,
            att.get_status_display(),
            f"{att.recorded_by.first_name} {att.recorded_by.last_name}" if att.recorded_by else '',
            att.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            att.notes,
        ])
    
    return response

# Notification Views
@login_required
def notifications(request):
    return render(request, 'uats/notifications/notification_list.html', {
        'notifications': Notification.objects.filter(user=request.user).order_by('-created_at'),
        'unread_count': Notification.objects.filter(user=request.user, is_read=False).count()
    })

@login_required
def notification_redirect(request, pk):
    """Handle notification clicks and mark as read"""
    notification = get_object_or_404(request.user.notifications, pk=pk)
    
    # Mark as read
    notification.mark_as_read()
    
    # Redirect to the notification link or fallback
    if notification.link:
        return redirect(notification.link)
    return redirect('dashboard')  # Fallback redirect

@csrf_exempt
@require_POST
@login_required
def mark_notification_read(request, pk):
    """API endpoint to mark notification as read"""
    notification = get_object_or_404(request.user.notifications, pk=pk)
    if notification.mark_as_read():
        return JsonResponse({'status': 'success', 'message': 'Notification marked as read'})
    return JsonResponse({'status': 'info', 'message': 'Notification was already read'})

@login_required
@require_POST
def mark_all_notifications_read(request):
    """Mark all notifications as read"""
    updated = Notification.objects.filter(
        user=request.user, 
        is_read=False
    ).update(is_read=True, read_at=timezone.now())
    
    return JsonResponse({
        'status': 'success',
        'message': f'{updated} notifications marked as read'
    })

@login_required
def notification_detail(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.mark_as_read()
    return render(request, 'uats/notifications/notification_detail.html', {
        'notification': notification
    })

@login_required
def session_detail(request, pk):
    session = get_object_or_404(UmugandaSession, pk=pk)
    if not check_session_permission(request.user, session):
        raise PermissionDenied
    
    stats = Attendance.objects.filter(session=session).aggregate(
        present=Count('pk', filter=Q(status='present')),
        absent=Count('pk', filter=Q(status='absent')),
        late=Count('pk', filter=Q(status='late')),
        excused=Count('pk', filter=Q(status='excused')),
    )
    
    return render(request, 'uats/attendance/session_detail.html', {
        'session': session,
        'present_count': stats['present'] or 0,
        'absent_count': stats['absent'] or 0,
        'late_count': stats['late'] or 0,
        'excused_count': stats['excused'] or 0,
    })

@login_required
@require_POST
def session_toggle(request, pk):
    session = get_object_or_404(UmugandaSession, pk=pk)
    
    if not (request.user.user_type == 3 or 
           (request.user.user_type == 2 and 
            session.cell == request.user.cell and 
            session.sector == request.user.sector)):
        messages.error(request, "Permission denied")
        return redirect('session-detail', pk=pk)
    
    session.is_active = not session.is_active
    session.save()
    messages.success(request, f"Session {'activated' if session.is_active else 'deactivated'}")
    return redirect('session-detail', pk=pk)