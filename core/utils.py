from django.core.mail import send_mail
from django.conf import settings
import datetime

def send_low_balance_alert(wallet):
    subject = f"Low Float Alert - {wallet.network.name}"
    message = (
        f"Dear {wallet.agent.username},\n\n"
        f"Your wallet for {wallet.network.name} has a low float balance of {wallet.balance} TZS.\n"
        f"Please refill as soon as possible to avoid transaction failure.\n\n"
        f"Regards,\nWakala Management System"
    )
    recipient = [wallet.agent.email]

    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipient)

    # Optional: SMS (if integrating Twilio or SMS gateway)
    # send_sms(wallet.agent.phone, message)

# from twilio.rest import Client

# def send_sms(phone, message):
#     client = Client('TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN')
#     client.messages.create(
#         body=message,
#         from_='+1234567890',  # Twilio number
#         to=phone
#     )
