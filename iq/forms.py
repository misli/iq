# -*- coding: utf-8 -*-
from django import forms
from django.forms.models import inlineformset_factory
from .models import *
from verified_email_field.forms import VerifiedEmailField
from django.contrib.auth.forms import UserCreationForm


class RegistrationForm(UserCreationForm):
    email = VerifiedEmailField(label='email', required=True)
    class Meta:
        model = User
        fields = ['email', 'password1', 'password2']


class DemandSessionWizardForm1(forms.ModelForm):
    class Meta:
        model = Demand
        fields = ['subject','level', 'towns', 'subject_desript']
        widgets = {
            'towns':TownSelectWidget
        }


class DemandSessionWizardForm2(forms.ModelForm):
    class Meta:
        model = Demand
        fields = ['lessons', 'students', 'time_desript']


class DemandSessionWizardForm3(forms.ModelForm):
    email = VerifiedEmailField(label='email', required=True)
    class Meta:
        model = Demand
        fields = ['first_name', 'last_name', 'email',]


TeachFormSet = inlineformset_factory(Lector, Teach, fields=('subject', 'level', 'price'), extra=1)


class LectorUpdateForm(forms.ModelForm):
    class Meta:
        model = Lector
        fields = ['titles_before','first_name','last_name','titles_after','price','towns']
        widgets = {
            'towns':TownSelectWidget
        }


class DemandUpdateForm(forms.ModelForm):
    class Meta:
        model = Demand
        fields = ['subject','level', 'towns', 'lessons', 'students']
        widgets = {
            'towns':TownSelectWidget
        }
