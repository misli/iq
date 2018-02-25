# -*- coding: utf-8 -*-
from django.shortcuts import render, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django import views
from django.db import transaction
from django.urls import reverse
from django.conf import settings
from django.core import serializers
from formtools.wizard.views import SessionWizardView
import requests
import json

from . import models, forms
from django.http import HttpResponseRedirect, HttpResponse
from datetime import datetime, timedelta

last_account_request = datetime.now() - timedelta(seconds=settings.FIO_API_MIN_REQUEST_INTERVAL)

def do_account_request():
    r = requests.get('https://www.fio.cz/ib_api/rest/last/{}/transactions.json'.format(settings.FIO_API_TOKEN))
    data = json.loads(r.text)
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

def check_account():
    global last_account_request
    if last_account_request + timedelta(seconds=settings.FIO_API_MIN_REQUEST_INTERVAL) <= datetime.now():
        do_account_request()
        last_account_request = datetime.now()
    else:
        pass


class signup(views.View):
    form_class = forms.RegistrationForm
    template_name = 'registration/signup.html'

    def get(self, request):
        form = self.form_class()
        return render(request, self.template_name, {'form': form })

    def post(self, request):
        form = self.form_class(request.POST)
        if form.is_valid():
            form.save()
            email = form.cleaned_data.get('email')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(email=email, password=raw_password)
            login(request, user)
            return HttpResponseRedirect('/')

        return render(request, self.template_name, {'form': form})


class CategoryListView(views.generic.list.ListView):
    model = models.Category


class SubjectListView(views.generic.list.ListView):
    template_name = 'iq/subject_list.html'
    # celé get zkopírované ze zdroje jen jsem upravil volání get_queryset, aby se předaly argumenty *args, **kwargs
    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset(self, *args, **kwargs)
        allow_empty = self.get_allow_empty()

        if not allow_empty:
            # When pagination is enabled and object_list is a queryset,
            # it's better to do a cheap query than to load the unpaginated
            # queryset in memory.
            if self.get_paginate_by(self.object_list) is not None and hasattr(self.object_list, 'exists'):
                is_empty = not self.object_list.exists()
            else:
                is_empty = not self.object_list
            if is_empty:
                raise Http404(_("Empty list and '%(class_name)s.allow_empty' is False.") % {
                    'class_name': self.__class__.__name__,
                })
        context = self.get_context_data()
        return self.render_to_response(context)

    def get_queryset(self, *args, **kwargs):# filtrace podle zvolené kategorie
        category = models.Category.objects.get(slug=kwargs['slug']).pk
        return  models.Subject.objects.filter(category=category)


class SubjectDetailView(views.generic.detail.DetailView):
    model = models.Subject

    def get_context_data(self, **kwargs):
        # přidá informace o tom kdo a na jaké úrovni daný předmět doučuje
        context = super(SubjectDetailView, self).get_context_data(**kwargs)
        teaches = models.Teach.objects.filter(subject=context['object'])
        context['level_list'] = {}
        for teach in teaches:
            if teach.level in context['level_list']:
                context['level_list'][teach.level].append(teach.lector)
            else:
                context['level_list'][teach.level] = [teach.lector]
        return context


class DemandSessionWizardView(SessionWizardView):
    template_name = 'iq/demand_create.html'
    form_list = [forms.DemandSessionWizardForm1, forms.DemandSessionWizardForm2,
                forms.DemandSessionWizardForm3, forms.DemandSessionWizardForm4]

    def done(self, form_list, **kwargs):
        form = self.get_all_cleaned_data()
        demand = models.Demand.objects.create(
            demand_type = form['demand_type'],
            email = form['email'],
            first_name = form['first_name'],
            last_name = form['last_name'],
            lessons = form['lessons'],
            students = form['students'],
            subject = form['subject'],
            level = form['level'],
            subject_desript = form['subject_desript'],
            time_desript = form['time_desript'],
        )
        for town in form['towns']:
            demand.towns.add(town)
        return render(self.request, 'iq/demand_review.html', {
            'form_list': form_list,
        })


@method_decorator(login_required, name='dispatch')
class DemandListView(views.generic.list.ListView):
    model = models.Demand

    def get_queryset(self, *args, **kwargs):
        # get only active demands
        return  self.model.objects.filter(status=0)


@method_decorator(login_required, name='dispatch')
class MyDemandListView(views.generic.list.ListView):
    model = models.Demand
    template_name = 'iq/my_demand_list.html'

    def get_queryset(self, *args, **kwargs):
        # get only demands taken by the user
        return  self.model.objects.filter( taken_by=self.request.user.lector )


@method_decorator(login_required, name='dispatch')
class DemandDetailView(views.generic.edit.FormView):
    template_name = 'iq/demand_detail.html'
    model = models.Demand
    form_class = forms.TakeDemandForm

    def get_context_data(self, **kwargs):
        context = super(DemandDetailView, self).get_context_data()
        context['demand'] = get_object_or_404(self.model, pk=kwargs['pk'] )
        if not context['demand'].status:
            # only if demand is active
            context['active'] = True
            context['not_able'] = self.request.user.lector.take_ability_check( context['demand'] )
        else:
            context['active'] = False
        return context

    def get(self, request, *args, **kwargs):
        check_account()
        return self.render_to_response(self.get_context_data(**kwargs))

    def post(self, request, *args, **kwargs):
        self.context = self.get_context_data(**kwargs)
        if self.context['active']:
            if self.context['not_able']:
                return HttpResponseRedirect('/poptavka/{}/'.format(kwargs['pk']))
            else:
                self.success_url = '/vzit-poptavku/{}/'.format( kwargs['pk'] )
                return super(DemandDetailView, self).post(request, *args, **kwargs)
        else:
            return HttpResponseRedirect('/poptavka/{}/'.format(kwargs['pk']))


class DemandUpdateView(views.generic.edit.UpdateView):
    model = models.Demand
    success_url = '/poptavka-zmenena/'
    form_class = forms.DemandUpdateForm
    template_name_suffix = '_edit'

def demand_updated_view(request):
    return render(request, 'iq/demand_updated.html')


class TakeDemandView(views.generic.edit.CreateView):
    template_name = 'iq/take_demand_form.html'
    success_url = '/moje-doucovani/'
    model = models.CreditTransaction
    object = None
    fields = []

    def get_context_data(self, *args, **kwargs):
        context = super(TakeDemandView, self).get_context_data()
        context['demand'] = get_object_or_404(models.Demand, pk=kwargs['pk'] )
        if not context['demand'].status:
            # only if demand is active
            context['active'] = True
            context['lector'] = self.request.user.lector
            context['not_able'] = context['lector'].take_ability_check( context['demand'] )
        else:
            context['active'] = False
        return context

    def form_valid(self, form):
        # transaction.atomic is wraped by try
        # HttpResponseRedirect causes __exit__
        try:
            with transaction.atomic():
                self.model.objects.create(
                    transaction_type = 'd',
                    demand = self.context['demand'],
                    volume = - self.context['demand'].get_charge(),
                    lector = self.context['lector'],
                )
        except IntegrityError as err:
            raise IntegrityError(err.message)
        return HttpResponseRedirect(self.success_url)

    def get(self, request, *args, **kwargs):
        self.context = self.get_context_data(**kwargs)
        self.object = None
        if self.context['active']:
            if self.context['not_able']:
                return HttpResponseRedirect('/poptavka/{}/'.format(kwargs['pk']))
            else:
                return self.render_to_response(self.context)
        else:
            return HttpResponseRedirect('/poptavka/{}/'.format(kwargs['pk']))

    def post(self, request, *args, **kwargs):
        self.context = self.get_context_data(**kwargs)
        if self.context['active']:
            if self.context['not_able']:
                return HttpResponseRedirect('/poptavka/{}/'.format(kwargs['pk']))
            else:
                self.success_url = '/moje-doucovani/'
                return super(TakeDemandView, self).post(request, *args, **kwargs)
        else:
            return HttpResponseRedirect('/poptavka/{}/'.format(kwargs['pk']))


class LectorListView(views.generic.list.ListView):
    model = models.Lector


class LectorDetailView(views.generic.detail.DetailView):
    model = models.Lector

    def get_context_data(self, **kwargs):
        context = super(LectorDetailView, self).get_context_data(**kwargs)
        context['teach_list'] = models.Teach.objects.filter(lector=context['object'].id)
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.has_complete_profile():
            return super(LectorDetailView, self).get(request, *args, **kwargs)
        else:
            raise Http404()

@method_decorator(login_required, name='dispatch')
class LectorProfileUpdateView(views.generic.edit.UpdateView):
    model = models.Lector
    form_class = forms.LectorProfileUpdateForm
    template_name_suffix = '_profile_update'

    def get_object(self, queryset=None):
        return self.request.user.lector

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.teach_formset = forms.TeachFormSet(instance=self.object)
        return super(LectorProfileUpdateView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.success_url = '/lektor/{}/'.format(self.object.pk)
        self.teach_formset = forms.TeachFormSet(self.request.POST, instance=self.object)
        self.teach_formset.full_clean()
        return super(LectorProfileUpdateView, self).post(request, *args, **kwargs)

    def form_valid(self, form):
          # context = self.get_context_data()
          formset = self.teach_formset
          if formset.is_valid():
              self.object = form.save()
              formset.instance = self.object
              formset.save()
              return HttpResponseRedirect(self.success_url)
          else:
              return self.render_to_response(self.get_context_data(form=form))


@method_decorator(login_required, name='dispatch')
class LectorSettingsUpdateView(views.generic.edit.UpdateView):
    model = models.Lector
    form_class = forms.LectorSettingsUpdateForm
    template_name_suffix = '_settings_update'

    def get_object(self, queryset=None):
        return self.request.user.lector

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super(LectorSettingsUpdateView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.success_url = '/lektor/{}/'.format(self.object.pk)
        return super(LectorSettingsUpdateView, self).post(request, *args, **kwargs)


def home(request):
    return render(request, 'iq/home.html', {})

def relog(request):
    logout(request)
    return HttpResponseRedirect('/prihlaseni/')

@login_required
def credit_topup_view(request):
    return render(request, 'iq/credit_topup.html', {'account_number':settings.ACCOUNT_NUMBER})
