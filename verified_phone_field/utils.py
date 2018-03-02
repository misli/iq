from __future__ import unicode_literals

from datetime import timedelta
from random import randint
from urllib import urlencode

from django.core.cache import cache
from django.template.loader import get_template
from django.utils.timezone import now

from . import settings

def get_code(email, fieldsetup):
    try:
        expiration_time, code = cache.get(fieldsetup.cache_prefix + str(email))
    except:
        return None
    return code if expiration_time >= now() else None


def send_code(number, fieldsetup):
    # create code and expiration time
    context = dict(fieldsetup.sms_context)
    context['code'] = (get_code(number, fieldsetup) or
                       str(randint(10 ** (fieldsetup.code_length - 1), 10 ** fieldsetup.code_length - 1)))
    context['expiration_time'] = now() + timedelta(0, fieldsetup.code_ttl)
    # store code and expiration time in cache
    cache.set(fieldsetup.cache_prefix + str(number), (context['expiration_time'], context['code']))
    # create http GET request to sms gate server
    url = {
        'login' : settings.SMS_LOGIN,
        'password' : settings.SMS_PASSWORD,
        'action' : 'send_sms',
        'number' : number,
        'message' : get_template(fieldsetup.sms_template_txt).render(context),
    }
    print '{}{}'.format(settings.SMS_URL, urlencode(url) )
    # r = requests.get('{}{}'.format(settings.SMS_URL, urlencode(url) ))
