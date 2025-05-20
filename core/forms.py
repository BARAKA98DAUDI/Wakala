from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, Transaction, Refill
from .models import DailyWalletStart

class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password1', 'password2']


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['wallet', 'type', 'amount', 'commission']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)  # Use default None to avoid crash
        super(TransactionForm, self).__init__(*args, **kwargs)
        if user:
            self.fields['wallet'].queryset = user.wallet_set.all()


class RefillForm(forms.ModelForm):
    class Meta:
        model = Refill
        fields = ['wallet', 'amount']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(RefillForm, self).__init__(*args, **kwargs)
        if user:
            self.fields['wallet'].queryset = user.wallet_set.all()


class CustomUserForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'role', 'password']
        


class DailyWalletStartForm(forms.ModelForm):
    class Meta:
        model = DailyWalletStart
        fields = ['wallet', 'start_balance']
