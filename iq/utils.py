import json
import requests
from datetime import datetime, timedelta

from django.core.cache import cache

import models, settings

cache.set('last_account_request', {
        'time': datetime.now() - timedelta(seconds=settings.FIO_API_MIN_REQUEST_INTERVAL),
        'id': 14462590267}, None)

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
        return data['accountStatement']['info']['id_last_download']

def set_last_id():
    response = requests.get('{}/set-last-id/{}/{}/'.format( settings.FIO_API_URL,
            settings.FIO_API_TOKEN, cache.get('last_account_request')['id'] ))
    return response

def check_account():
    if cache.get('last_account_request')['time'] + timedelta(seconds=settings.FIO_API_MIN_REQUEST_INTERVAL) <= datetime.now():
        data = get_account_transaction_data()
        last_id = save_account_transaction_data(data)
        cache.set('last_account_request', {'time': datetime.now(), 'id': last_id}, None)
