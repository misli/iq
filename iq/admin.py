# -*- coding: utf-8 -*-
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import *


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Define admin model for custom User model with no email field."""

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Oprávnění', {'fields': ('is_active', 'is_staff', 'is_superuser',
                                       'groups', 'user_permissions')}),
        ('Důležitá data', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
    )
    list_display = ('email', 'is_staff', 'is_superuser')
    search_fields = ('email',)
    ordering = ('email',)


class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'id', 'slug')


class LevelInline(admin.TabularInline):
    model = Level


class CategoryAdmin(admin.ModelAdmin):
    list_display = ('__unicode__','slug')


class TownAdmin(admin.ModelAdmin):
    list_display = ('__unicode__','number_of_lectors','number_of_demands','slug','county')


class TeachInline(admin.TabularInline):
    model = Teach
    extra = 1


class LectorAdmin(admin.ModelAdmin):
    list_display = ('user','__unicode__','credit')
    inlines = (TeachInline, )
    filter_horizontal = ('towns',)
    readonly_fields = ('user','date_registred', 'credit')


class SchemeAdmin(admin.ModelAdmin):
    inlines = [ LevelInline, ]


class PaymentAdmin(admin.ModelAdmin):
    list_display = ('__unicode__','credit')


class AccountTransactionAdmin(admin.ModelAdmin):
    readonly_fields = ('transaction_id', 'date', 'currency', 'counterparty', 'counterparty_name', 'bank_code', 'bank_name', 'constant_symbol', 'specific_symbol', 'user_identification', 'message', 'transaction_type', 'autor', 'specification', 'comment', 'bic', 'command_id', )
    list_display = ('transaction_id','volume','autor','date')
    # readonly_fields += ('volume','variable_symbol')

class CreditTransactionAdmin(admin.ModelAdmin):
    readonly_fields = (
        'transaction_type',
        'account_transaction',
        'datetime',
        'volume',
        'lector',
        'open_balance',
        'close_balance',
        'datetime',
        'demand',
        'reason',
        'comment',
    )

class DemandAdmin(admin.ModelAdmin):
    readonly_fields = ('date_posted','date_updated')
    list_display = ('subject','level','towns_as_str','status','date_posted','date_updated')
    filter_horizontal = ('towns',)


admin.site.register(Town, TownAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(Subject, SubjectAdmin)
admin.site.register(Scheme, SchemeAdmin)
admin.site.register(Settings)
admin.site.register(AccountRequest)
admin.site.register(Demand, DemandAdmin)
admin.site.register(Holyday)
admin.site.register(Lector, LectorAdmin)
admin.site.register(AccountTransaction, AccountTransactionAdmin)
admin.site.register(CreditTransaction, CreditTransactionAdmin)
