# -*- coding: utf-8 -*-
from verified_email_field.fieldsetup import VerifiedEmailFieldSetup, fieldsetups
from verified_email_field.forms import VerifiedEmailField, VerificationCodeField
from verified_email_field.widgets import VerifiedEmailWidget
from verified_phone_field.forms import VerifiedPhoneField

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.forms.models import inlineformset_factory
from django.utils.translation import ugettext_lazy as _


from .models import *


class ReadonlyVerifiedEmailField(VerifiedEmailField):

    def __init__(self, required=True, fieldsetup_id=None, max_length=None,
                 email_label=_('e-mail'), send_label=_('send verification code'),
                 code_label=_('verification code'), **kwargs):
        self.fieldsetup_id = fieldsetup_id or str(hash(self))
        self.fieldsetup = fieldsetups.setdefault(
            self.fieldsetup_id, VerifiedEmailFieldSetup(**kwargs))
        self.widget = VerifiedEmailWidget(
            send_label=send_label,
            fieldsetup_id=self.fieldsetup_id,
            email_attrs={'placeholder': email_label,
                        'readonly': 'readonly'},
            code_attrs={'placeholder': code_label},
        )
        super(VerifiedEmailField, self).__init__((
            forms.EmailField(label=email_label, required=required),
            VerificationCodeField(label=code_label, length=self.fieldsetup.code_length),
        ), require_all_fields=False, **kwargs)


class TakeDemandForm(forms.Form):
    pass


class RegistrationForm(UserCreationForm):
    email = VerifiedEmailField(label='E-mail', required=True)
    agree = forms.BooleanField(label='Souhlasím s obchodními podmínkami', required=True)
    class Meta:
        model = User
        fields = ['email', 'password1', 'password2', 'agree']


class DemandSessionWizardForm1(forms.ModelForm):
    subject = forms.ModelChoiceField(queryset = Subject.objects.all(),
            label='Předmět', empty_label=None)
    level = forms.ModelChoiceField(queryset = Level.objects.all(), label='Úroveň',
            empty_label=None, widget=LevelSelectWidget)
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

    def __init__(self, *args, **kwargs):
        self.towns = kwargs.pop('towns')
        self.subject = kwargs.pop('subject')
        self.level = kwargs.pop('level')
        super(DemandSessionWizardForm3, self).__init__(*args, **kwargs)
        self.fields['target'].queryset = Lector.objects.filter(
                teach__in=Teach.objects.filter(subject=self.subject, level=self.level),
                towns__in=self.towns
        )

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
    cropped = forms.CharField(widget=forms.HiddenInput, required=False)

    class Meta:
        model = Lector
        fields = ['titles_before','first_name','last_name','titles_after','photo','cv','towns']
        widgets = {
            'towns':TownSelectWidget
        }


class LectorSettingsUpdateForm(forms.ModelForm):
    phone = VerifiedPhoneField(label='Telefoní číslo', required=True)

    def __init__(self, pop_phone, *args, **kwargs):
        super(LectorSettingsUpdateForm, self).__init__(*args, **kwargs)
        if pop_phone:
            self.fields.pop('phone')

    class Meta:
        model = Lector
        fields = ['phone', 'sex', 'slovak', 'commute', 'home', 'notice_aimed',
                'notice_suited', 'notice_any', 'monday', 'tuesday', 'wednesday',
                'thursday','friday','saturday','sundey',]


class UserEmailUpdateForm(forms.ModelForm):
    def __init__(self, original_email, *args, **kwargs):
        self.original_email = original_email
        return super(UserEmailUpdateForm, self).__init__(*args, **kwargs)

    email = ReadonlyVerifiedEmailField(label='Součacný e-mail', required=True)
    new_email = VerifiedEmailField(label='Nový e-mail', required=True)

    def clean(self):
        # check the original_email to prevent tamper
        cleaned_data = super(UserEmailUpdateForm, self).clean()
        if self.original_email != self.cleaned_data['email']:
            raise forms.ValidationError("Původní e-mail nesouhlasí.")
        return cleaned_data

    class Meta:
        model = User
        fields = ['email', 'new_email']


class LectorPhoneUpdateForm(forms.ModelForm):
    phone = VerifiedPhoneField(label='Telefoní číslo', required=True)

    class Meta:
        model = Lector
        fields = ['phone']


class DemandUpdateForm(forms.ModelForm):
    class Meta:
        model = Demand
        fields = ['subject','level', 'towns', 'lessons', 'students']
        widgets = {
            'level': LevelSelectWidget,
            'towns': TownSelectWidget
        }
