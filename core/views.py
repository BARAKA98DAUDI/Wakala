from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib import messages
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.timezone import now, localtime
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.db.models import Sum
import json
import openpyxl
from openpyxl.styles import Font
from xhtml2pdf import pisa
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

# Translation
from django.utils.translation import gettext as _

# Models
from .models import (
    Transaction,
    Refill,
    Wallet,
    WalletStartBalance,
    DailyWalletStart
)

# Forms
from .forms import (
    RefillForm,
    RegisterForm,
    TransactionForm,
    DailyWalletStartForm
)

# Utils
from .utils import send_low_balance_alert


@login_required
def dashboard(request):
    user = request.user

    if user.role != "admin" and not user.is_superuser:
        today = localtime().date()
        agent_wallets = Wallet.objects.filter(agent=user)

        have_all_floats = (
            DailyWalletStart.objects.filter(
                agent=user, date=today, wallet__in=agent_wallets
            ).count()
            == agent_wallets.count()
        )
        if not have_all_floats:
            messages.warning(request, _("You must set float for all your wallets before accessing the dashboard."))
            return redirect("set_start_float")

    today = now().date()
    week_ago = today - timedelta(days=7)
    user = request.user

    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    selected_network = request.GET.get('network')

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date() if start_date_str else week_ago
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date() if end_date_str else today
    except ValueError:
        messages.error(request, _("Invalid date format provided."))
        start_date = week_ago
        end_date = today

    if user.role == 'admin':
        wallets = Wallet.objects.all()
        base_transactions = Transaction.objects.all()
    else:
        wallets = Wallet.objects.filter(agent=user)
        base_transactions = Transaction.objects.filter(wallet__agent=user)

    transactions = base_transactions.filter(timestamp__date__range=[start_date, end_date])

    if selected_network:
        transactions = transactions.filter(wallet__network__name=selected_network)

    start_dict = dict(DailyWalletStart.objects.filter(agent=user, date=today).values_list('wallet', 'start_balance'))
    refill_dict = Refill.objects.filter(wallet__in=wallets, timestamp__date=today)\
        .values('wallet').annotate(total=Sum('amount'))
    refill_map = {r['wallet']: r['total'] for r in refill_dict}

    wallet_data = []
    for wallet in wallets:
        start = start_dict.get(wallet.id, 0)
        refill = refill_map.get(wallet.id, 0)
        cash_in = base_transactions.filter(wallet=wallet, type='cash_in', timestamp__date=today)\
            .aggregate(Sum('amount'))['amount__sum'] or 0
        cash_out = base_transactions.filter(wallet=wallet, type='cash_out', timestamp__date=today)\
            .aggregate(Sum('amount'))['amount__sum'] or 0
        wallet_data.append({
            'wallet': wallet,
            'start': start,
            'refill': refill,
            'cash_in': cash_in,
            'cash_out': cash_out,
            'today_balance': start + refill + cash_in - cash_out
        })

    total_in = transactions.filter(type='cash_in').aggregate(Sum('amount'))['amount__sum'] or 0
    total_out = transactions.filter(type='cash_out').aggregate(Sum('amount'))['amount__sum'] or 0
    today_in = base_transactions.filter(type='cash_in', timestamp__date=today).aggregate(Sum('amount'))['amount__sum'] or 0
    today_out = base_transactions.filter(type='cash_out', timestamp__date=today).aggregate(Sum('amount'))['amount__sum'] or 0
    wallet_balances = wallets.values('network__name').annotate(balance=Sum('balance'))

    if request.method == 'POST':
        form = DailyWalletStartForm(request.POST)
        if form.is_valid():
            DailyWalletStart.objects.update_or_create(
                agent=user,
                wallet=form.cleaned_data['wallet'],
                date=today,
                defaults={'start_balance': form.cleaned_data['start_balance']}
            )
            messages.success(request, _("Wallet start balance updated successfully."))
            return redirect('dashboard')
        else:
            messages.error(request, _("Invalid form data submitted."))
    else:
        form = DailyWalletStartForm()

    last_7_days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    labels = [_(d.strftime('%A')) for d in last_7_days]  # Translated weekday names
    cash_in_data = []
    cash_out_data = []

    for day in last_7_days:
        day_cash_in = base_transactions.filter(type='cash_in', timestamp__date=day).aggregate(Sum('amount'))['amount__sum'] or 0
        day_cash_out = base_transactions.filter(type='cash_out', timestamp__date=day).aggregate(Sum('amount'))['amount__sum'] or 0
        cash_in_data.append(float(day_cash_in))
        cash_out_data.append(float(day_cash_out))

    todays_transactions = base_transactions.filter(timestamp__date=today, type='cash_out')
    total_float = todays_transactions.aggregate(total=Sum('amount'))['total'] or 0
    float_count = todays_transactions.count()
    avg_float = total_float / float_count if float_count else 0

    available_networks = Wallet.objects.values_list('network__name', flat=True).distinct()

    context = {
        'wallets': wallets,
        'transactions': base_transactions.order_by('-timestamp')[:10],
        'total_in': total_in,
        'total_out': total_out,
        'today_in': today_in,
        'today_out': today_out,
        'wallet_balances': wallet_balances,
        'wallet_data': wallet_data,
        'form': form,
        'labels': json.dumps(labels),
        'cash_in_data': json.dumps(cash_in_data),
        'cash_out_data': json.dumps(cash_out_data),
        'total_float_today': total_float,
        'average_float_spent': avg_float,
        'available_networks': available_networks,
        'selected_network': selected_network,
        'start_date': start_date,
        'end_date': end_date,
        'title': _("Dashboard"),
    }

    return render(request, 'dashboard.html', context)


def register(request): 
    """
    User registration view.
    """
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, _("Registration successful. Welcome!"))
            return redirect('dashboard')
        else:
            messages.error(request, _("There was an error in your registration form."))
    else:
        form = RegisterForm()
    return render(request, 'register.html', {'form': form, 'title': _("Register")})





@login_required
def add_transaction(request):
    """
    View to add a transaction (cash_in or cash_out) and update wallet balance.
    Sends low balance alert if balance falls below threshold.
    """
    if request.method == 'POST':
        form = TransactionForm(request.POST, user=request.user)
        if form.is_valid():
            transaction = form.save(commit=False)
            if transaction.type == 'cash_in':
                transaction.wallet.balance += transaction.amount
            elif transaction.type == 'cash_out':
                transaction.wallet.balance -= transaction.amount

            transaction.wallet.save()
            transaction.save()

            # Check if low balance alert needed
            low_balance = transaction.wallet.balance < transaction.wallet.min_threshold
            threshold_time = now() - timedelta(hours=6)
            if low_balance and (not transaction.wallet.last_alert_sent or transaction.wallet.last_alert_sent < threshold_time):
                send_low_balance_alert(transaction.wallet)
                transaction.wallet.last_alert_sent = now()
                transaction.wallet.save()

            messages.success(request, _("Transaction saved!"))
            return redirect('dashboard')
    else:
        form = TransactionForm(user=request.user)

    return render(request, 'add_transaction.html', {'form': form})


@login_required
def export_transactions_pdf(request):
    """
    Export transactions as a PDF file.
    """
    user = request.user
    if user.role == 'admin':
        transactions = Transaction.objects.all().order_by('-timestamp')
    else:
        transactions = Transaction.objects.filter(wallet__agent=user).order_by('-timestamp')

    html = render_to_string('transactions_pdf.html', {'transactions': transactions})
    response = HttpResponse(content_type='application/pdf')
    # Use gettext for filename
    response['Content-Disposition'] = _('attachment; filename="transactions.pdf"')

    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse(_('PDF generation failed'))
    return response


@login_required
def export_transactions_excel(request):
    """
    Export transactions as an Excel (.xlsx) file.
    """
    user = request.user
    if user.role == 'admin':
        transactions = Transaction.objects.all().order_by('-timestamp')
    else:
        transactions = Transaction.objects.filter(wallet__agent=user).order_by('-timestamp')

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = _("Transactions")
    headers = [_('Date'), _('Network'), _('Type'), _('Amount')]
    ws.append(headers)

    # Bold headers
    for col in ws.iter_cols(min_row=1, max_row=1, min_col=1, max_col=4):
        for cell in col:
            cell.font = Font(bold=True)

    # Fill transaction rows
    for tx in transactions:
        network_name = tx.wallet.network.name if hasattr(tx.wallet.network, 'name') else _('N/A')
        ws.append([
            tx.timestamp.strftime('%Y-%m-%d %H:%M'),
            network_name,
            _(tx.type),  # Translate transaction type (e.g. cash_in/cash_out)
            tx.amount
        ])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    # Translate filename
    response['Content-Disposition'] = _('attachment; filename="transactions.xlsx"')
    wb.save(response)
    return response


def _to_two_dp(value):
    """
    Normalize any (str / float / Decimal / int) to a Decimal
    with exactly two decimal places.
    """
    if isinstance(value, str):
        value = value.replace(",", "").strip()
    dec = Decimal(str(value))
    return dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@login_required
def refill_wallet(request):
    user = request.user

    if request.method == "POST":
        form = RefillForm(request.POST, user=user)
        if form.is_valid():
            refill = form.save(commit=False)

            try:
                amount = _to_two_dp(refill.amount)
                balance = _to_two_dp(refill.wallet.balance or 0)
                refill.wallet.balance = balance + amount
            except InvalidOperation:
                messages.error(request, _("❌ Enter a valid monetary amount."))
                return redirect("refill_wallet")

            refill.amount = amount
            refill.wallet.save()
            refill.save()

            messages.success(request, _("✅ Refill successful and balance updated."))
            return redirect("dashboard")

    else:
        form = RefillForm(user=user)

    if not user.is_superuser and getattr(user, "role", "") != "admin":
        form.fields["wallet"].queryset = Wallet.objects.filter(agent=user)

    return render(request, "refill_wallet.html", {"form": form})


@login_required
def refill_history(request):
    """
    View to display the history of wallet refills.
    Admins see all; agents see only theirs.
    """
    user = request.user
    if user.role == 'admin':
        refills = Refill.objects.all().order_by('-timestamp')
    else:
        refills = Refill.objects.filter(wallet__agent=user).order_by('-timestamp')

    return render(request, 'refill_history.html', {'refills': refills})


@login_required
def set_start_float(request):
    """Agents must record today’s start-float once per calendar day."""
    user = request.user
    if user.role == "admin" or user.is_superuser:
        return redirect("dashboard")

    today = localtime().date()

    # delete yesterday’s entries
    DailyWalletStart.objects.filter(agent=user).exclude(date=today).delete()

    wallets = Wallet.objects.filter(agent=user)
    recorded_ids = DailyWalletStart.objects.filter(
        agent=user, date=today, wallet__in=wallets
    ).values_list("wallet_id", flat=True)
    wallets_missing = wallets.exclude(id__in=recorded_ids)

    # handle submission
    if request.method == "POST":
        for wallet in wallets_missing:
            amt = request.POST.get(f"start_{wallet.id}")
            if amt:
                DailyWalletStart.objects.update_or_create(
                    agent=user, wallet=wallet, date=today,
                    defaults={"start_balance": float(amt)}
                )
        messages.success(request, _("✅ Start balances set successfully."))
        return redirect("dashboard")

    if not wallets_missing.exists():
        return redirect("dashboard")

    return render(request, "set_start_float.html",
                  {"wallets": wallets_missing, "today": today})


@login_required
def generate_pdf(request, report_type="daily"):
    response = HttpResponse(content_type='application/pdf')
    # Use translatable string for filename
    response['Content-Disposition'] = f'inline; filename="{_(report_type)}_summary.pdf"'

    p = canvas.Canvas(response, pagesize=letter)
    p.setFont("Helvetica", 16)
    title = _("📊 Wakala Daily Summary Report") if report_type == "daily" else _("📊 Wakala Weekly Summary Report")
    p.drawString(180, 750, title)

    today = datetime.today().date()
    if report_type == "daily":
        start_date = end_date = today
    else:
        end_date = today
        start_date = end_date - timedelta(days=7)

    p.setFont("Helvetica", 12)
    p.drawString(200, 730, _("Date Range: ") + f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")

    transactions = Transaction.objects.filter(timestamp__date__range=[start_date, end_date]).order_by('-timestamp')

    p.setFont("Helvetica", 10)
    p.drawString(50, 690, _("ID"))
    p.drawString(100, 690, _("Network"))
    p.drawString(200, 690, _("Cash In"))
    p.drawString(300, 690, _("Cash Out"))

    y = 670
    total_cash_in = 0
    total_cash_out = 0

    for tx in transactions:
        network = tx.wallet.network if hasattr(tx.wallet, 'network') else _('N/A')
        amount = tx.amount

        if tx.type == 'cash_in':
            cash_in = amount
            cash_out = 0
            total_cash_in += amount
        else:
            cash_in = 0
            cash_out = amount
            total_cash_out += amount

        p.drawString(50, y, str(tx.id))
        p.drawString(100, y, str(network))
        p.drawString(200, y, f"{cash_in}")
        p.drawString(300, y, f"{cash_out}")
        y -= 20
        if y < 100:
            p.showPage()
            y = 750

    p.setFont("Helvetica-Bold", 12)
    y -= 40
    p.drawString(50, y, _("Total Cash In: ") + f"{total_cash_in}")
    p.drawString(50, y - 20, _("Total Cash Out: ") + f"{total_cash_out}")
    p.drawString(50, y - 40, _("Balance: ") + f"{total_cash_in - total_cash_out}")

    p.showPage()
    p.save()
    return response


@login_required
def transaction_history(request):
    """Show a filtered list of transactions (last 30 days by default)."""

    today = now().date()
    start_date = today - timedelta(days=30)

    # --- Base queryset: last 30-day window ---
    qs = Transaction.objects.filter(timestamp__date__range=[start_date, today])

    # --- Optional network filter ---
    network = request.GET.get('network')
    if network:
        qs = qs.filter(wallet__network__name=network)

    # --- Optional type filter (cash_in / cash_out) ---
    tx_type = request.GET.get('type')
    if tx_type in {"cash_in", "cash_out"}:
        qs = qs.filter(type=tx_type)

    # Eager-load related objects and order newest first
    qs = qs.select_related('wallet', 'wallet__network').order_by('-timestamp')

    # All networks (uploaded by admin) for the dropdown
    available_networks = (
        Wallet.objects.values_list('network__name', flat=True)
        .distinct()
        .order_by('network__name')
    )

    context = {
        'transactions': qs,
        'network': network,
        'transaction_type': tx_type,
        'start_date': start_date,
        'end_date': today,
        'available_networks': available_networks,
    }
    return render(request, 'transaction_history.html', context)
