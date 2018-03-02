from __future__ import unicode_literals

from collections import namedtuple

from . import settings


class VerifiedPhoneFieldSetup(namedtuple('VerifiedPhoneFieldSetup', (
        'cache_prefix', 'code_length', 'code_ttl',
        'sms_template_txt', 'sms_context', 'mail_mailer'))):
    def __new__(
            cls, cache_prefix=settings.CACHE_PREFIX,
            code_length=settings.CODE_LENGTH, code_ttl=settings.CODE_TTL,
            sms_template_txt=settings.SMS_TEMPLATE_TXT,
            sms_context=None, mail_mailer=settings.MAIL_MAILER, **kwargs):
        return super(VerifiedPhoneFieldSetup, cls).__new__(
            cls, cache_prefix=cache_prefix,
            code_length=code_length, code_ttl=code_ttl,
            sms_template_txt=sms_template_txt,
            sms_context=sms_context or {}, mail_mailer=mail_mailer,
        )


fieldsetups = {}
