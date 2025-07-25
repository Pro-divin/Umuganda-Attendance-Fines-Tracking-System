from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.core.exceptions import ValidationError
from .models import CustomUser, UmugandaSession, Attendance, Fine
from django.utils import timezone

class UserRegisterForm(UserCreationForm):
    national_id = forms.CharField(max_length=20, required=True)
    phone_number = forms.CharField(max_length=15, required=True)
    sector = forms.CharField(max_length=100, required=True)
    cell = forms.CharField(max_length=100, required=True)
    village = forms.CharField(max_length=100, required=False)
    date_of_birth = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    profile_picture = forms.ImageField(required=False)
    
    class Meta:
        model = CustomUser
        fields = [
            'first_name', 
            'last_name',
            'username',
            'email',
            'national_id',
            'phone_number',
            'sector',
            'cell',
            'village',
            'date_of_birth',
            'profile_picture',
            'password1',
            'password2',
            'user_type',
        ]
        widgets = {
            'user_type': forms.HiddenInput(),
        }
    
    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if not phone_number.startswith('+250'):
            raise ValidationError("Phone number must start with +250")
        if len(phone_number) != 13:
            raise ValidationError("Phone number must be 13 digits including country code")
        return phone_number
    
    def clean_national_id(self):
        national_id = self.cleaned_data.get('national_id')
        if len(national_id) != 16 or not national_id.isdigit():
            raise ValidationError("National ID must be 16 digits")
        return national_id

class UserLoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={'autofocus': True}))

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = [
            'first_name',
            'last_name',
            'email',
            'phone_number',
            'profile_picture',
            'sector',
            'cell',
            'village',
            'date_of_birth',
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
        }

class UmugandaSessionForm(forms.ModelForm):
    class Meta:
        model = UmugandaSession
        fields = ['date', 'description']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def clean_date(self):
        date = self.cleaned_data.get('date')
        if date > timezone.now().date():
            raise ValidationError("Session date cannot be in the future")
        return date

class AttendanceForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields = ['status', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

class FineUpdateForm(forms.ModelForm):
    class Meta:
        model = Fine
        fields = ['status', 'amount', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount <= 0:
            raise ValidationError("Fine amount must be positive")
        return amount

class CitizenSearchForm(forms.Form):
    search = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'placeholder': 'Search by name, ID or phone...'
    }))

class FinePaymentForm(forms.Form):
    payment_method = forms.CharField(
        initial='MTN Mobile Money',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'readonly': 'readonly',
            'value': 'MTN Mobile Money'
        }),
        label="Payment Method",
        required=False
    )
    
    transaction_id = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter MTN MOMO Transaction ID (e.g., 7AB1234C56)'
        }),
        required=True,
        label="Transaction ID",
        help_text="Enter the exact transaction ID received from MTN Mobile Money payment"
    )
    
    def clean_transaction_id(self):
        transaction_id = self.cleaned_data.get('transaction_id')
        if len(transaction_id) < 8:
            raise ValidationError("Transaction ID must be at least 8 characters")
        if not any(char.isdigit() for char in transaction_id):
            raise ValidationError("Transaction ID must contain numbers")
        if not any(char.isalpha() for char in transaction_id):
            raise ValidationError("Transaction ID must contain letters")
        return transaction_id
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['payment_method'].initial = 'MTN Mobile Money'
        self.fields['payment_method'].widget.attrs.update({
            'style': 'background-color: #f8f9fa; cursor: not-allowed;'
        })