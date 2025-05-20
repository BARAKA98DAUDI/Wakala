from django.urls import path,include
from . import views
from .views import (
    register,
    export_transactions_pdf,
    export_transactions_excel,
    refill_wallet,
    refill_history,
    set_start_float,
    
)

urlpatterns = [ 
    path('i18n/', include('django.conf.urls.i18n')),       
    path('transaction-history/', views.transaction_history, name='transaction_history'),
    path('generate_pdf/daily/', views.generate_pdf, {'report_type': 'daily'}, name='generate_daily_pdf'),
    path('generate_pdf/weekly/', views.generate_pdf, {'report_type': 'weekly'}, name='generate_weekly_pdf'),
    path('set-start-float/', set_start_float, name='set_start_float'),
    path('refill/', refill_wallet, name='refill_wallet'),
    path('refill-history/', refill_history, name='refill_history'),
    path('export/pdf/', export_transactions_pdf, name='export_pdf'),
    path('export/excel/', export_transactions_excel, name='export_excel'),
    path('transaction/add/', views.add_transaction, name='add_transaction'),
    path('register/', register, name='register'),
    path('', views.dashboard, name='dashboard'),
]
