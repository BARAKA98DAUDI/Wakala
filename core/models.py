from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import CheckConstraint, Q
from django.utils.translation import gettext_lazy as _

# -------------------------
# Custom User Model
# -------------------------
class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('agent', 'Agent'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='agent')

    def __str__(self):
        return self.username

# -------------------------
# Network Model
# -------------------------
class Network(models.Model):
    name = models.CharField(max_length=100)
    logo = models.ImageField(upload_to='network_logos/', null=True, blank=True)

    def __str__(self):
        return self.name

# -------------------------
# Wallet Model
# -------------------------
class Wallet(models.Model):
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    network = models.ForeignKey(Network, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    min_threshold = models.DecimalField(max_digits=10, decimal_places=2, default=10000.00)
    last_alert_sent = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.agent.username} - {self.network.name}"

    def is_low_balance(self):
        return self.balance < self.min_threshold

# -------------------------
# Transaction Model
# -------------------------
class Transaction(models.Model):
    TYPE_CHOICES = [
        ('cash_in', 'Cash In'),
        ('cash_out', 'Cash Out'),
    ]
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    commission = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.wallet} - {self.type} - {self.amount}"




class Refill(models.Model):
    wallet   = models.ForeignKey("Wallet", on_delete=models.CASCADE)
    amount   = models.DecimalField(max_digits=14, decimal_places=2)   # ↑ roomier
    timestamp = models.DateTimeField(auto_now_add=True)

    # ---------- validation helpers ----------
    @staticmethod
    def _clean_amount_raw(raw):
        if raw is None:
            raise InvalidOperation("empty")

        if isinstance(raw, str):
            raw = raw.replace(",", "").strip()         
        amount = Decimal(str(raw))                   
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def clean(self):
        super().clean()
        try:
            self.amount = self._clean_amount_raw(self.amount)
        except InvalidOperation:
            raise ValidationError({"amount": _("Enter a valid monetary amount.")})
        if self.amount < 0:
            raise ValidationError({"amount": _("Amount must be positive.")})
        
    class Meta:
        constraints = [
            CheckConstraint(
                check=Q(amount__gte=0),
                name="refill_amount_non_negative",
            ),
        ]
        ordering = ["-timestamp"]

    def __str__(self):
        return _(
            "%(network)s – %(amount)s TZS on %(date)s"
        ) % {
            "network": self.wallet.network.name,
            "amount":  f"{self.amount:,.2f}",
            "date":    self.timestamp.strftime("%Y‑m‑d"),
        }

    
    
class WalletStartBalance(models.Model):
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE)
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    start_amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        unique_together = ('wallet', 'agent', 'date')

# -------------------------
# DailyWalletStart Model
# -------------------------
class DailyWalletStart(models.Model):
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE)
    date = models.DateField(default=timezone.now)
    start_balance = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        unique_together = ('agent', 'wallet', 'date')

    def __str__(self):
        return f"{self.agent.username} - {self.wallet.network.name} - {self.date} - {self.start_balance} TZS"
