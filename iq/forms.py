# -*- coding: utf-8 -*-
from verified_email_field.forms import VerifiedEmailField

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.forms.models import inlineformset_factory

from .models import *


class TakeDemandForm(forms.Form):
    pass

class RegistrationForm(UserCreationForm):
    email = VerifiedEmailField(label='E-mail', required=True)
    class Meta:
        model = User
        fields = ['email', 'password1', 'password2']


class DemandSessionWizardForm1(forms.ModelForm):
    subject = forms.ModelChoiceField(queryset = Subject.objects.all(), label='Předmět', empty_label=None)
    level = forms.ModelChoiceField(queryset = Level.objects.all(), label='Úroveň', empty_label=None, widget=LevelSelectWidget)
    class Meta:
        model = Demand
        fields = ['towns','subject','level', 'lessons', 'subject_desript']
        widgets = {
            'towns':TownSelectWidget
        }


class DemandSessionWizardForm2(forms.ModelForm):
    class Meta:
        model = Demand
        fields = [ 'students', 'slovak', 'commute', 'sex_required' , 'time_desript']


class DemandSessionWizardForm3(forms.ModelForm):
    class Meta:
        model = Demand
        fields = ['demand_type','target']
        widgets = {
            'demand_type': forms.RadioSelect
        }


class DemandSessionWizardForm4(forms.ModelForm):
    email = VerifiedEmailField(label='email', required=True)
    agree = forms.BooleanField(required=True)
    class Meta:
        model = Demand
        fields = ['first_name', 'last_name', 'email','agree']


TeachFormSet = inlineformset_factory(Lector, Teach,
                            fields=('subject', 'level', 'price'),
                            widgets={'level': LevelSelectWidget }, extra=1)

class LectorProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Lector
        fields = ['titles_before','first_name','last_name','titles_after','photo','cv','towns']
        widgets = {
            'towns':TownSelectWidget
        }

class LectorSettingsUpdateForm(forms.ModelForm):
    class Meta:
        model = Lector
        fields = ['sex','slovak','commute','home','notice_aimed','notice_suited','notice_any','monday','tuesday','wednesday','thursday','friday','saturday','sundey',]


class DemandUpdateForm(forms.ModelForm):
    class Meta:
        model = Demand
        fields = ['subject','level', 'towns', 'lessons', 'students']
        widgets = {
            'level': LevelSelectWidget,
            'towns': TownSelectWidget
        }
