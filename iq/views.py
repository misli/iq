# -*- coding: utf-8 -*-
import base64
import cStringIO

from formtools.wizard.views import SessionWizardView

from django import views
from django.db import IntegrityError, transaction
from django.conf import settings
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.core import serializers
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.forms import ValidationError
from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.utils.decorators import method_decorator
from django.urls import reverse

import models, forms
from utils import check_account


try:
    sets = models.Settings.objects.get(pk=1)
except:
    pass


class signup(views.View):
    form_class = forms.RegistrationForm
    template_name = 'registration/signup.html'
    success_url = '/muj-profil/'

    def get(self, request):
        form = self.form_class()
        return render(request, self.template_name, {'form': form })

    def post(self, request):
        form = self.form_class(request.POST)
        if form.is_valid():
            # transaction.atomic is wraped by try
            # because HttpResponseRedirect causes __exit__
            try:
                with transaction.atomic():
                    form.save()
                    email = form.cleaned_data.get('email')
                    raw_password = form.cleaned_data.get('password1')
                    user = authenticate(email=email, password=raw_password)
                    login(request, user)
            except IntegrityError as err:
                raise IntegrityError(err.message)
            return HttpResponseRedirect(self.success_url)
        return render(request, self.template_name, {'form': form})


class CategoryListView(views.generic.list.ListView):
    model = models.Category


class SubjectListView(views.generic.list.ListView):

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

################################################################################

####    DEMAND VIEWS

################################################################################

class DemandSessionWizardView(SessionWizardView):
    template_name = 'iq/demand_create.html'
    form_list = [forms.DemandSessionWizardForm1, forms.DemandSessionWizardForm2,
                forms.DemandSessionWizardForm3, forms.DemandSessionWizardForm4]

    def get_form_kwargs(self, step=None):
        kwargs = {}
        if step == '2':
            # add data from first step to filter lectors for target field
            kwargs['towns'] = self.get_cleaned_data_for_step('0')['towns']
            kwargs['subject'] = self.get_cleaned_data_for_step('0')['subject']
            kwargs['level'] = self.get_cleaned_data_for_step('0')['level']
        return kwargs

    def done(self, form_list, **kwargs):
        form = self.get_all_cleaned_data()
        demand = models.Demand.objects.create(
            agree = form['agree'],
            email = form['email'],
            phone = form['phone'],
            prefer_phone = form['prefer_phone'],
            first_name = form['first_name'],
            last_name = form['last_name'],
            lessons = form['lessons'],
            students = form['students'],
            subject = form['subject'],
            level = form['level'],
            subject_descript = form['subject_descript'],
            time_descript = form['time_descript'],
            slovak = form['slovak'],
            commute = form['commute'],
            sex_required = form['sex_required'],
        )
        for town in form['towns']:
            demand.towns.add(town)
        for target in form['target']:
            demand.target.add(target)
        demand.notify_new()
        demand.confirm_new()
        return HttpResponseRedirect('/poptavka-pridana/')


class DemandUpdateView(views.generic.edit.UpdateView):
    model = models.Demand
    success_url = '/poptavka-zmenena/'
    form_class = forms.DemandUpdateForm
    template_name_suffix = '_update'


@method_decorator(login_required, name='dispatch')
class DemandListView(views.generic.list.ListView):
    model = models.Demand
    template_name = 'iq/demand_list.html'

    def get_queryset(self, *args, **kwargs):
        # get only active demands
        demands = super(DemandListView, self).get_queryset().filter(status=0)
        lector = self.request.user.lector
        object_list = {}
        # sort demands: 1.targeted to the lector(are allways suitable)
        # 2. suitable for the lector but not targeted to anyone
        # 3. all other - neither targeted nor suitable
        object_list['targeted'] = demands.filter(target=lector.id)
        object_list['suitable'] = lector.get_suitable_damands(demands.filter(target=None))
        object_list['other'] = demands.filter(target=None).exclude(pk__in=object_list['suitable'])
        return object_list


@method_decorator(login_required, name='dispatch')
class DemandDetailView(views.generic.edit.FormView):
    template_name = 'iq/demand_detail.html'
    model = models.Demand
    form_class = forms.TakeDemandForm

    def get_context_data(self, **kwargs):
        context = super(DemandDetailView, self).get_context_data()
        context['demand'] = get_object_or_404(self.model, pk=kwargs['pk'] )
        # only if demand is active
        if not context['demand'].status:
            context['active'] = True
            context['lector'] = self.request.user.lector
            context['not_able'] = context['lector'].take_ability_check(context['demand'])
            context['can_affort'] = context['lector'].credit_check(context['demand'])
            context['can_pay_later'] = True if not context['lector'].pay_later else False
        else:
            context['active'] = False
        return context

    def get(self, request, *args, **kwargs):
        # pass kwargs to get_context_data
        return self.render_to_response(self.get_context_data(**kwargs))

    def post(self, request, *args, **kwargs):
        self.context = self.get_context_data(**kwargs)
        if self.context['active'] and not self.context['not_able'] and (self.context['can_affort'] or self.context['can_pay_later']):
            self.success_url = '/vzit-poptavku/{}/'.format( kwargs['pk'] )
            return super(DemandDetailView, self).post(request, *args, **kwargs)
        else:
            return HttpResponseRedirect('/poptavka/{}/'.format(kwargs['pk']))


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
            context['can_affort'] = context['lector'].credit_check(context['demand'])
            context['can_pay_later'] = True if not context['lector'].pay_later else False
        else:
            context['active'] = False
        return context

    def form_valid(self, form):
        # transaction.atomic is wraped by try
        # because HttpResponseRedirect causes __exit__
        try:
            with transaction.atomic():
                self.model.objects.create(
                    transaction_type = 'd',
                    demand = self.context['demand'],
                    volume = - self.context['demand'].get_charge(),
                    lector = self.context['lector'],
                )
                self.context['demand'].status=2
                self.context['demand'].save()
        except IntegrityError as err:
            raise IntegrityError(err.message)
        return HttpResponseRedirect(self.success_url)

    def get(self, request, *args, **kwargs):
        self.context = self.get_context_data(**kwargs)
        self.object = None
        if self.context['active'] and not self.context['not_able'] and (self.context['can_affort'] or self.context['can_pay_later']):
            return self.render_to_response(self.context)
        else:
            return HttpResponseRedirect('/poptavka/{}/'.format(kwargs['pk']))

    def post(self, request, *args, **kwargs):
        self.context = self.get_context_data(**kwargs)
        if self.context['active'] and not self.context['not_able'] and (self.context['can_affort'] or self.context['can_pay_later']):
            return super(TakeDemandView, self).post(request, *args, **kwargs)
        else:
            return HttpResponseRedirect('/poptavka/{}/'.format(kwargs['pk']))


@method_decorator(login_required, name='dispatch')
class MyDemandListView(views.generic.list.ListView):
    model = models.Demand
    template_name = 'iq/my_demand_list.html'

    def get_queryset(self, *args, **kwargs):
        # get only demands taken by the user
        return  self.model.objects.filter( taken_by=self.request.user.lector )


@method_decorator(login_required, name='dispatch')
class MyDemandDetailView(views.generic.detail.DetailView):
    model = models.Demand
    template_name = 'iq/my_demand_detail.html'

    def get_queryset(self, *args, **kwargs):
        # get only demands taken by the user
        return  self.model.objects.filter( taken_by=self.request.user.lector )

################################################################################

####    LECTOR VIEWS

################################################################################

class LectorListView(views.generic.list.ListView):
    model = models.Lector


class LectorDetailView(views.generic.detail.DetailView):
    model = models.Lector

    def get_context_data(self, **kwargs):
        # add list of taught subjects
        context = super(LectorDetailView, self).get_context_data(**kwargs)
        context['teach_list'] = models.Teach.objects.filter(lector=context['object'].id)
        return context

    def get(self, request, *args, **kwargs):
        # filter only lectors with completed profile
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
        if self.object.phone:
            self.success_url = '/lektor/{}/'.format(self.object.pk)
        else:
            self.success_url = '/moje-nastaveni/'
        self.teach_formset = forms.TeachFormSet(self.request.POST, instance=self.object)
        self.teach_formset.full_clean()
        if request.POST.get('cropped'):
            format, imgstr = request.POST['cropped'].split(';base64,')
            ext = format.split('/')[-1]
            file = cStringIO.StringIO(base64.b64decode(imgstr ))
            image = InMemoryUploadedFile(file,
               field_name='photo',
               name='profilovka.' + ext,
               content_type="image/jpeg",
               size=len(file.getvalue()),
               charset=None)
            request.FILES[u'photo'] = image
        return super(LectorProfileUpdateView, self).post(request, *args, **kwargs)

    def form_valid(self, form):
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

    def get_form(self, form_class=None):
        # get form with phone field only if phone is not provided yet
        return self.form_class(bool(self.object.phone), **self.get_form_kwargs())

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.has_complete_profile():
            self.success_url = '/lektor/{}/'.format(self.object.pk)
        else:
            self.success_url = '/muj-profil/'
        return super(LectorSettingsUpdateView, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save()
        if 'change_email' in form.data:
            return HttpResponseRedirect('/zmena-emailu/')
        elif 'change_phone' in form.data:
            return HttpResponseRedirect('/zmena-telefonu/')
        else:
            return HttpResponseRedirect(self.success_url)


@method_decorator(login_required, name='dispatch')
class UserEmailUpdateView(views.generic.edit.UpdateView):
    model = models.User
    form_class = forms.UserEmailUpdateForm
    template_name_suffix = '_email_update'
    success_url = '/moje-nastaveni/'

    def get_object(self, queryset=None):
        return self.request.user

    def get_form(self, form_class=None):
        # send original_email to form class for security reasons
        if form_class is None:
            form_class = self.get_form_class()
        return form_class(self.original_email, **self.get_form_kwargs())

    def form_valid(self, form):
        self.object.email = form.cleaned_data['new_email']
        self.object.save()
        return HttpResponseRedirect(self.get_success_url())

    def dispatch(self, request, *args, **kwargs):
        self.original_email = request.user.email
        return super(UserEmailUpdateView, self).dispatch(request, *args, **kwargs)


@method_decorator(login_required, name='dispatch')
class LectorPhoneUpdateView(views.generic.edit.UpdateView):
    model = models.User.lector
    form_class = forms.LectorPhoneUpdateForm
    template_name_suffix = '_phone_update'

    def get_object(self, queryset=None):
        return self.request.user.lector

    def form_valid(self, form):
        self.object.phone = form.cleaned_data['phone']
        self.object.save()
        return super(LectorPhoneUpdateView, self).form_valid(form)


def home(request):
    return render(request, 'iq/home.html', {})

def message_view(request, *args, **kwargs):
    msg = sets.messages[kwargs['msg']]
    return render(request, 'iq/massage.html', {'msg':msg})

def relog(request, *args, **kwargs):
    logout(request)
    return HttpResponseRedirect( '/{}/'.format(kwargs['next']) )

@login_required
def credit_topup_view(request):
    return render(request, 'iq/credit_topup.html', {'account_number':settings.FIO_ACCOUNT_NUMBER})
