# -*- coding: utf-8 -*-
from django import forms
from .models import *
from .widgets import TownSelectWidget


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
        fields = ['subjectLevel', 'towns', 'subject_desript']
        # widgets = {
        #     'town': TownSelectWidget,
        # }

class DemandSessionWizardForm2(forms.ModelForm):
    class Meta:
        model = Demand
        fields = ['lessons', 'students', 'time_desript']

class DemandSessionWizardForm3(forms.ModelForm):
    class Meta:
        model = Demand
        fields = ['first_name', 'last_name', 'email',]

class LectorUpdateForm(forms.ModelForm):
    class Meta:
        model = Lector
        fields = ['titles_before','first_name','last_name','titles_after','price','towns','subjectLevels']