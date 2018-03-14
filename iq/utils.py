import json
import requests
from datetime import datetime, timedelta
from urllib import urlencode

from django.core.cache import cache
from django.db import transaction
from django.template.loader import get_template

import models, settings


def get_account_transaction_data():
    response = requests.get('{}/last/{}/transactions.json'.format(settings.FIO_API_URL, settings.FIO_API_TOKEN))
    return json.loads(response.text)

def save_account_transaction_data(data):
    with transaction.atomic():
        info = data['accountStatement']['info']
        models.AccountRequest.objects.create(
            account_id      = info['accountId'],
            opening_balance = info['openingBalance'],
            closing_balance = info['closingBalance'],
            date_start      = info['dateStart'][0:10],
            date_end        = info['dateEnd'][0:10],
            id_from         = info['idFrom'],
            id_to           = info['idTo'],
            id_last_download = info['idLastDownload'],
        )
        for t in data['accountStatement']['transactionList']['transaction']:
            models.AccountTransaction.objects.create(
                transaction_id    = t['column22']['value'] if t['column22'] else None,
                date              = t['column0']['value'][0:10] if t['column0'] else None,
                volume            = t['column1']['value'] if t['column1'] else None,
                currency          = t['column14']['value'] if t['column14'] else None,
                counterparty      = t['column2']['value'] if t['column2'] else None,
                counterparty_name = t['column10']['value'] if t['column10'] else None,
                bank_code         = t['column3']['value'] if t['column3'] else None,
                bank_name         = t['column12']['value'] if t['column12'] else None,
                constant_symbol   = t['column4']['value'] if t['column4'] else None,
                variable_symbol   = t['column5']['value'] if t['column5'] else None,
                specific_symbol   = t['column6']['value'] if t['column6'] else None,
                user_identification = t['column7']['value'] if t['column7'] else None,
                message           = t['column16']['value'] if t['column16'] else None,
                transaction_type  = t['column8']['value'] if t['column8'] else None,
                autor             = t['column9']['value'] if t['column9'] else None,
                specification     = t['column18']['value'] if t['column18'] else None,
                comment           = t['column25']['value'] if t['column25'] else None,
                bic               = t['column26']['value'] if t['column26'] else None,
                command_id        = t['column17']['value'] if t['column17'] else None,
            )
    return int(models.AccountTransaction.objects.latest().transaction_id)

def get_last_transaction_id():
    """Try to get last transaction_id from database.
    If no transaction is stored in the database return initial value.
    """
    try:
        last_id = models.AccountTransaction.objects.latest().transaction_id
    except models.AccountTransaction.DoesNotExist:
        last_id = 0
        # last_id = 14462590267
    return last_id

def set_last_id():
    if cache.get('last_account_request'):
        last_id = cache.get('last_account_request')['id']
    else:
        last_id = get_last_transaction_id()
    response = requests.get('{}/set-last-id/{}/{}/'.format( settings.FIO_API_URL,
            settings.FIO_API_TOKEN, last_id ))
    return response

def check_account():
    # first check if last_account_request is cached
    last_request = cache.get('last_account_request')
    if last_request == None:
        # if last_account_request is not cached
        last_request = {
                'time': datetime.now() - timedelta(seconds=settings.FIO_API_MIN_REQUEST_INTERVAL),
                'id': get_last_transaction_id()}

    if last_request['time'] + timedelta(seconds=settings.FIO_API_MIN_REQUEST_INTERVAL) <= datetime.now():
        data = get_account_transaction_data()
        if last_request['id'] < data['accountStatement']['info']['idTo']:
            last_id = save_account_transaction_data(data)
            cache.set('last_account_request', {'time': datetime.now(), 'id': last_id}, None)

def send_sms(number, message):
    params = {
        'login' : settings.SMS_LOGIN,
        'password' : settings.SMS_PASSWORD,
        'action' : 'send_sms',
        'number' : number,
        'message' : massage
    }
    print '{}{}'.format(settings.SMS_URL, urlencode(params) )
    # return requests.get(url=settings.SMS_URL, params=params)

def send_sms_queue(numbers, message):
    data = get_template('iq/sms_queue.xml').render({'number_list':numbers, 'message':message})
    params = {
        'login' : settings.SMS_LOGIN,
        'password' : settings.SMS_PASSWORD,
        'action' : 'xml_queue',
    }
    print '{}{}\n{}'.format(settings.SMS_URL, urlencode(params), data)
    # return requests.post(url=settings.SMS_URL, params=params, data=data)
