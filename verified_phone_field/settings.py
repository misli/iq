from __future__ import unicode_literals

from django.conf import settings
from django.utils.translation import ugettext_lazy as _

CACHE_PREFIX = getattr(settings, 'VERIFIED_PHONE_CACHE_PREFIX', 'verified_phone_field_')
CODE_LENGTH = int(getattr(settings, 'VERIFIED_EMAIL_CODE_LENGTH', 6))
CODE_TTL = int(getattr(settings, 'VERIFIED_EMAIL_CODE_TTL', 300))
SMS_TEMPLATE_TXT = getattr(settings, 'VERIFIED_POHNE_SMS_TEMPLATE_TXT', 'verified_phone_field/sms.txt')
MAIL_MAILER = getattr(settings, 'VERIFIED_EMAIL_MAIL_MAILER',
                      'Django Verified Email Field (https://github.com/misli/django-verified-email-field)')
SMS_LOGIN = getattr(settings, 'SMS_LOGIN', 'sms_login')
SMS_PASSWORD = getattr(settings, 'SMS_PASSWORD', 'sms_raw_password')
SMS_URL = getattr(settings, 'SMS_PASSWORD', 'http://api.smsbrana.cz/smsconnect/http.php?')
