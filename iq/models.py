# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import MaxValueValidator, MinValueValidator
from django.core.mail import send_mail
from django.db import models, transaction, IntegrityError
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.forms.widgets import Select, SelectMultiple
from django.utils.crypto import get_random_string
from django.utils.functional import cached_property
from django.utils.text import slugify

from utils import send_sms, send_sms_queue


class TownSelectWidget(SelectMultiple):
    template_name = 'iq/widgets/town_select.html'

    def get_context(self, name, value, attrs):
        context = super(TownSelectWidget, self).get_context(name, value, attrs)
        towns = Town.objects.all().order_by('name')
        town_list = json.dumps([ [ t.pk, t.name, t.county, ] for t in towns ])
        context['widget']['town_list'] = town_list
        context['widget']['attrs']['id'] = 'select_towns'
        return context

    class Media:
        css = {
            'all': ('css/town_select_widget.css',)
        }


class LevelSelectWidget(Select):
    template_name = 'iq/widgets/level_select.html'

    def get_context(self, name, value, attrs):
        context = super(LevelSelectWidget, self).get_context(name, value, attrs)
        levels = Level.objects.all()
        subjects = Subject.objects.all()
        level_list = json.dumps([{ 'id': str(l.id), 'name' : l.name, 'order' : l.order, 'scheme' : str(l.scheme.id)} for l in levels ])
        subject_list = json.dumps({ str(s.id) : str(s.scheme.id) for s in subjects })
        context['widget']['level_list'] = level_list
        context['widget']['subject_list'] = subject_list
        return context


class LectorSelectWidget(SelectMultiple):
    template_name = 'iq/widgets/lector_select.html'

    def get_context(self, name, value, attrs):
        context = super(LectorSelectWidget, self).get_context(name, value, attrs)
        context['widget']['lector_list'] = Lector.objects.filter(pk__in=[option['value'] for option in [ group_choices[0] for group_name, group_choices, group_index in context['widget']['optgroups'] ]])
        return context


class Settings(models.Model):
    """Model for superuser's settings."""
    lectors_terms_and_conditions    = models.TextField('Obchodní podmínky pro lektory', default='Lektoři jsou povini dodržovat tyto obchodní podmínky')
    students_terms_and_conditions   = models.TextField('Obchodní podmínky pro studenty', default='Studenti jsou povini dodržovat tyto obchodní podmínky')
    default_email_address           = models.EmailField('Výchozí adresa pro odesílání emailu', default='info@'+settings.DOMAIN)
    pay_later_limit                 = models.PositiveSmallIntegerField('Limit pro uhrazení férovky', default=14)
    demand_added                    = models.TextField('Potvrzení nové poptávky', default='Vaše poptávka byla úspěšně přidána do systému.\nPotvrzení jsme Vám zaslali také na e-mail, společně s odkazem pro úpravu Vaší poptávky pro případ, že by se cokoliv změnilo.\nDěkujeme, že využíváte našich služeb' )
    demand_updated                  = models.TextField('Potvrzení úpravy poptávky', default='Vaše poptávka byla úspěšně upravena. Do E-mailu Vám byl zaslán nový odkaz pro další změny.')
    notif_new_suited_mail_subject   = models.CharField('Poptávka volná mail-předmět', default='Nová vhodná poptávka', max_length=50)
    notif_new_suited_mail_message   = models.CharField('Poptávka volná mail-zpráva', default='Do systému byla přidána nová poptávka, která by se Ti mohla líbit.', max_length=500)
    notif_new_suited_sms            = models.CharField('Poptávka volná sms', default='Do systemu byla pridana nova poptavka, ktera by se Ti mohla libit.', max_length=50)
    notif_new_aimed_mail_subject    = models.CharField('Poptávka mířená mail-předmět', default='Nová mířená poptávka', max_length=50)
    notif_new_aimed_mail_message    = models.CharField('Poptávka mířená mail-zpráva', default='Nový student si Tě vybral na doučování. Odpověz co nejdříve, jestli ho bereš, ', max_length=500)
    notif_new_aimed_sms             = models.CharField('Poptávka mířená sms', default='Pozor, vybral si Te novy student.', max_length=50)
    confi_new_mail_subject          = models.CharField('Nové poptávka mail-předmět', default='Nová poptávka', max_length=50)
    confi_new_mail_message          = models.CharField('Nové poptávka mail-zpráva', default='Vaše poptávka byla úspěšně přidána do systému. Zobrazit a upravit ji můžete tímto odkazem', max_length=500)
    confi_updated_mail_subject      = models.CharField('Upravená poptávka mail-předmět', default='Poptávka upravena', max_length=50)
    confi_updated_mail_message      = models.CharField('Upravená poptávka mail-zpráva', default='Vaše poptávka byla úspěšně upravena. Zobrazit a upravit ji můžete tímto odkazem', max_length=500)
    hour_rate1              = models.PositiveIntegerField('Cena lekce - volná poptávka: 1 student', default=200)
    hour_rate2              = models.PositiveIntegerField('Cena lekce - volná poptávka: 2 studenti', default=250)
    hour_rate3              = models.PositiveIntegerField('Cena lekce - volná poptávka: 3 studenti', default=300)
    hour_rate4              = models.PositiveIntegerField('Cena lekce - volná poptávka: 4 studenti', default=350)
    charge1x1               = models.PositiveIntegerField('Poplatek: 1 student 1 lekce', default=30)
    charge1x2               = models.PositiveIntegerField('Poplatek: 1 student 2-4 lekcí', default=60)
    charge1x5               = models.PositiveIntegerField('Poplatek: 1 student 5-9 lekcí', default=140)
    charge1x10              = models.PositiveIntegerField('Poplatek: 1 student 10 a více lekcí', default=200)
    charge2x1               = models.PositiveIntegerField('Poplatek: 2 studenti 1 lekce', default=40)
    charge2x2               = models.PositiveIntegerField('Poplatek: 2 studenti 2-4 lekcí', default=100)
    charge2x5               = models.PositiveIntegerField('Poplatek: 2 studenti 5-9 lekcí', default=200)
    charge2x10              = models.PositiveIntegerField('Poplatek: 2 studenti 10 a více lekcí', default=300)
    charge3x1               = models.PositiveIntegerField('Poplatek: 3 studenti 1 lekce', default=70)
    charge3x2               = models.PositiveIntegerField('Poplatek: 3 studenti 2-4 lekcí', default=150)
    charge3x5               = models.PositiveIntegerField('Poplatek: 3 studenti 5-9 lekcí', default=300)
    charge3x10              = models.PositiveIntegerField('Poplatek: 3 studenti 10 a více lekcí', default=400)
    charge4x1               = models.PositiveIntegerField('Poplatek: 4 studenti 1 lekce', default=80)
    charge4x2               = models.PositiveIntegerField('Poplatek: 4 studenti 2-4 lekcí', default=200)
    charge4x5               = models.PositiveIntegerField('Poplatek: 4 studenti 5-9 lekcí', default=400)
    charge4x10              = models.PositiveIntegerField('Poplatek: 4 studenti 10 a více lekcí', default=500)

    class Meta:
        verbose_name = "Nastavení"
        verbose_name_plural = "Nastavení"

    def __unicode__(self):
        return "Nastavení"

    @cached_property
    def get_charge_list(self):
        return [
            [self.charge1x1, self.charge1x2, self.charge1x5, self.charge1x10],
            [self.charge2x1, self.charge2x2, self.charge2x5, self.charge2x10],
            [self.charge3x1, self.charge3x2, self.charge3x5, self.charge3x10],
            [self.charge4x1, self.charge4x2, self.charge4x5, self.charge4x10],
        ]

    @cached_property
    def messages(self):
        return {
            'added':    self.demand_added,
            'updated':  self.demand_updated
        }

    def save(self, *args, **kwargs):
        # don't save more than one instance of Settings
        if Settings.objects.exists() and not self.pk:
            pass
        else:
            return super(Settings, self).save(*args, **kwargs)

# cereate a shortcut to Settings
try:
    sets = Settings.objects.get(pk=1)
except:
    pass


class UserManager(BaseUserManager):
    """Define a model manager for User model with no username field."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        """Create and save a User with the given email and password."""
        if not email:
            raise ValueError('The given email must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular User with the given email and password."""
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        """Create and save a SuperUser with the given email and password."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None
    first_name = None
    last_name = None
    email = models.EmailField('E-mail', unique=True)
    agree = models.BooleanField('Souhlasím s obchodními podmínkami', default=False)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    objects = UserManager()


class Town(models.Model):
    COUNTY_CHOICES =(
        ('A', 'Hlavní město Praha'),
        ('S', 'Středočeský kraj'),
        ('C', 'Jihočeský kraj'),
        ('P', 'Plzeňský kraj'),
        ('K', 'Karlovarský kraj'),
        ('U', 'Ústecký kraj'),
        ('L', 'Liberecký kraj'),
        ('H', 'Královéhradecký kraj'),
        ('E', 'Pardubický kraj'),
        ('M', 'Olomoucký kraj'),
        ('T', 'Moravskoslezský kraj'),
        ('B', 'Jihomoravský kraj'),
        ('Z', 'Zlínský kraj'),
        ('J', 'Kraj Vysočina'),
    )
    name        = models.CharField('Název', max_length=33, unique=True)
    slug        = models.SlugField('Slug', max_length=33, unique=True, editable=False)
    county      = models.CharField('Kraj', max_length=1, choices=COUNTY_CHOICES)
    countyCapital = models.BooleanField()

    class Meta:
        verbose_name = "Město"
        verbose_name_plural = "Města"

    def __unicode__(self):
        return self.name

    def number_of_lectors(self):
        return Lector.objects.filter(towns__in=[self.id]).count()

    def number_of_demands(self):
        return Demand.objects.filter(towns__in=[self.id]).count()

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        return super(Town, self).save(*args, **kwargs)


class Category(models.Model):
    name        = models.CharField('Název', max_length=50, unique=True)
    slug        = models.SlugField('Slug', max_length=50, unique=True, editable=False)
    description  = models.TextField('Popis', max_length=500)

    class Meta:
        verbose_name = "Kategorie předmětů"
        verbose_name_plural = "Kartegorie předmětů"

    def __unicode__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        return super(Category, self).save(*args, **kwargs)


class Scheme(models.Model):
    """Scheme of Subject's Levels.

    Different Subjects can have different set of Levels.
    """
    name = models.CharField('název', max_length=50, unique=True)

    class Meta:
        verbose_name = 'Systém úrovní'
        verbose_name_plural = 'Systémy úrovní'

    def __unicode__(self):
        return self.name


class Subject(models.Model):
    name        = models.CharField('Název', max_length=50, unique=True)
    slug        = models.SlugField('Slug', max_length=50, unique=True, editable=False)
    description = models.TextField('Popis', max_length=800)
    category    = models.ForeignKey(Category, on_delete=models.PROTECT, verbose_name = 'Kategorie')
    scheme      = models.ForeignKey(Scheme, verbose_name = 'Systém úrovní')

    class Meta:
        verbose_name = 'Předmět'
        verbose_name_plural = 'Předměty'

    def __unicode__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        return super(Subject, self).save(*args, **kwargs)


class Level(models.Model):
    name    = models.CharField('Název úrovně', max_length=50)
    order   = models.PositiveSmallIntegerField('Pořadí')
    scheme  = models.ForeignKey(Scheme, on_delete=models.PROTECT, verbose_name='Systém úrovní')

    class Meta:
        verbose_name = "Úroveň"
        verbose_name_plural = "Úroveně"

    def __unicode__(self):
        return self.name


class LectorManager(models.Manager):
    def get_queryset(self):
        return super(LectorManager, self).get_queryset().filter(user__is_active=True)


def user_directory_path(instance, filename):
    return 'lector_{0}/{1}'.format(instance.user.lector.variable_symbol, filename)

class Lector(models.Model):
    SEX_CHOICES = (
        ('', 'vyberte prosím'),
        ('f', 'Žena'),
        ('m', 'Muž'),
    )
    NOTIFY_DISCOUNTED_CHOICES  = (
        ('n','vůbec ne'),
        ('m','e-mail'),
        ('s','sms'),
        ('b','e-mail i sms'),
    )
    NOTIFY_AIMED_CHOICES  = (
        ('m','e-mail'),
        ('b','e-mail i sms'),
    )
    NOTIFY_SUITED_CHOICES  = (
        ('n','vůbec ne'),
        ('d','e-mail denní přehled'),
        ('m','e-mail ihned'),
        ('s','sms ihned'),
        ('a','e-mail denní přehled + sms ihned'),
        ('b','e-mail ihned + sms ihned'),
    )
    user            = models.OneToOneField(settings.AUTH_USER_MODEL, related_name='lector', on_delete=models.PROTECT, unique=True)
    titles_before   = models.CharField('Tituly před jménem', max_length=20, blank=True, null=True)
    first_name      = models.CharField('Křestní jméno', max_length=20)
    last_name       = models.CharField('Příjmení', max_length=20)
    titles_after    = models.CharField('Tituly za jménem', max_length=20, blank=True, null=True)
    intro           = models.CharField('O mně', max_length=200, default="Umím toho hodně a rád Vás to naučím.", blank=True, null=True)
    cv              = models.FileField(verbose_name='Životopis',upload_to=user_directory_path, blank=True, null=True)
    photo           = models.ImageField(verbose_name='Fotka',upload_to=user_directory_path, blank=True, null=True)
    towns           = models.ManyToManyField(Town, blank=True, verbose_name='Města')
    credit          = models.DecimalField('Kredit', max_digits=12, decimal_places=2, default=0.00, editable=False)
    subjects        = models.ManyToManyField(Subject, through='Teach', verbose_name='Doučuji')
    phone           = models.DecimalField('Telefoní číslo', max_digits=9, decimal_places=0, null=True, unique=True)
    sex             = models.CharField('Jsem', max_length=1, choices=SEX_CHOICES, default=None, null=True)
    slovak          = models.BooleanField('Mluvím slovensky', default=False)
    home            = models.BooleanField('Doučuji u sebe doma', default=False)
    commute         = models.BooleanField('Můžu dojíždět', default=True)
    monday          = models.BooleanField('Pondělí', default=True)
    tuesday         = models.BooleanField('Úterý', default=True)
    wednesday       = models.BooleanField('Středa', default=True)
    thursday        = models.BooleanField('Čtvrtek', default=True)
    friday          = models.BooleanField('Pátek', default=True)
    saturday        = models.BooleanField('Soboa', default=True)
    sundey          = models.BooleanField('Neděle', default=True)
    notify_aimed    = models.CharField('Poptávka mířená na mě', max_length=1, choices=NOTIFY_AIMED_CHOICES, default='b')
    notify_suited   = models.CharField('Poptávka vhodná pro mě', max_length=1, choices=NOTIFY_SUITED_CHOICES, default='d')
    notify_discounted = models.CharField('Zlevněná poptávka', max_length=1, choices=NOTIFY_DISCOUNTED_CHOICES, default='m')
    is_active       = models.BooleanField(default=True)
    variable_symbol = models.DecimalField("Variabilní symbol", max_digits=10, decimal_places=0, editable=False)
    pay_later       = models.OneToOneField('Demand', null=True, blank=True, related_name='pay_later')
    objects         = LectorManager()

    class Meta:
        verbose_name = 'Lektor'
        verbose_name_plural = 'Lektoři'

    def __unicode__(self):
        return self.full_name() or self.user.email

    def teach_list(self):
        return Teach.objects.filter(lector=self.id)

    def teach_list_as_str(self):
        return ['{} - {}'.format(teach.subject.name, teach.level.name) for teach in self.teach_list()]

    def rating(self):
        demands = Demand.objects.filter(taken_by=self.id).exclude(rating=None)
        s = 0
        for demand in demands:
            s += demand.rating
        return s / len(demands)

    def deactivate(self):
        self.is_active = False

    def activate(self):
        self.is_active = True

    def has_complete_profile(self):
        if self.first_name and self.last_name and self.towns and self.subjects:
            return True
        else:
            return False

    def take_ability_check(self, demand):
        """Return False if "able to take", otherwise the reason why not able."""
        ABLE_CHOICES=[
            False,
            "nemáš aktivní účet",
            "na téhle úrovni to zatím nedáváš",
            "tenhle předmět neumíš",
            "v tomhle městě nedoučuješ",
            "nemáš ověřené telefoní číslo",
            "nemáš vyplněný profil",
        ]
        if self.has_complete_profile():
            if self.phone:
                compare = list(demand.towns.all()) + list(self.towns.all())
                if len( set( compare ) ) < len( compare ):
                    if demand.subject in self.subjects.all():
                        if demand.level in [teach.level for teach in Teach.objects.filter(lector=self.id, subject=demand.subject)]:
                            if self.is_active :
                                return ABLE_CHOICES[0]
                            else:
                                return ABLE_CHOICES[1]
                        else:
                            return ABLE_CHOICES[2]
                    else:
                        return ABLE_CHOICES[3]
                else:
                    return ABLE_CHOICES[4]
            else:
                return ABLE_CHOICES[5]
        else:
            return ABLE_CHOICES[6]

    def get_suitable_damands(self, demands):
        """Filter given queryset of demands and return those which are suitable for lector."""
        suitable = demands.none()
        for teach in self.teach_list():
            suitable = suitable | demands.filter(subject=teach.subject, level=teach.level, towns__in=self.towns.all()).distinct()
        return suitable

    def credit_check(self, demand):
        return demand.get_charge() <= self.credit

    @cached_property
    def email(self):
        return self.user.email

    def date_registred(self):
        return self.user.date_joined

    def full_name(self):
        return '{} {} {} {}'.format(self.titles_before or "", self.first_name, self.last_name, self.titles_after or "").strip()


class Teach(models.Model):
    """Intermediary model between Lector and Subject.

    It describe what Level of Subject can Lector teach and at what price.
    """
    lector      = models.ForeignKey(Lector, verbose_name="Lektor")
    subject     = models.ForeignKey(Subject, verbose_name="Předmět")
    level       = models.ForeignKey(Level, verbose_name="Úroveň")
    price       = models.IntegerField("Cena při mířené poptávce")

    def __unicode__(self):
        return '{} na úrovni {}'.format(self.subject.name, self.level.name)

    def save(self, *args, **kwargs):
        if self.subject.scheme == self.level.scheme:
            return super(Teach, self).save(*args, **kwargs)
        else:
            raise IntegrityError("schemes didn't match")

    class Meta:
        unique_together = (('lector', 'subject', 'level'),)


class Holyday(models.Model):
    lector   = models.ForeignKey(Lector)
    start    = models.DateField(auto_now=True)
    end      = models.DateField(auto_now=True)


class Demand(models.Model):
    """Model of Demand.

    Demand can be 'free' or 'aimed':
    'free' means that any Lector can take it.
    'aimed' means only those Lectors who are selected in target can see and take it.
    """
    SEX_REQUIRED_CHOICES = (
        ('n', 'Ne'),
        ('f', 'Chci lektorku'),
        ('m', 'Chci lektora'),
    )
    STATUS_CHOICES =(
        (0, 'Je aktivní'),
        (1, 'Je neaktivní'),
        (2, 'Je převzata'),
        (3, 'Je ukončena'),
    )
    LESSONS_CHOICES =(
        (0, '1 lekce'),
        (1, '2-4 lekce'),
        (2, '5-9 lekcí'),
        (3, '10 a vice'),
    )
    STUDENTS_CHOICES =(
        (0, '1 student'),
        (1, '2 studenti'),
        (2, '3 studenti'),
        (3, '4 a více studentů'),
    )
    agree           = models.BooleanField('Souhlasím s obchodními podmínkami',default=False )
    status          = models.PositiveSmallIntegerField('Status', default=0, choices=STATUS_CHOICES)
    first_name      = models.CharField('Jméno', max_length=100)
    last_name       = models.CharField('Príjmení', max_length=100)
    email           = models.EmailField('E-mail')
    towns           = models.ManyToManyField(Town, verbose_name='Město')
    subject         = models.ForeignKey(Subject, on_delete=models.PROTECT, verbose_name='Předmět')
    level           = models.ForeignKey(Level, on_delete=models.PROTECT, verbose_name='Úroveň')
    date_posted     = models.DateTimeField('Vloženo', auto_now_add=True)
    date_updated    = models.DateTimeField('Aktualizováno', auto_now=True)
    date_taken      = models.DateTimeField('Převzato', null=True, editable=False)
    lessons         = models.PositiveSmallIntegerField('Počet lekcí', default=1, choices=LESSONS_CHOICES)
    students        = models.PositiveSmallIntegerField('Počet studentů', default=0, choices=STUDENTS_CHOICES)
    subject_descript= models.CharField('Popis doučované láky', max_length=300)
    time_descript    = models.CharField('Kdy se můžem sejít', max_length=300)
    commute         = models.BooleanField('Můžu dojíždět', default=True)
    sex_required    = models.CharField('Požaduji pohlaví lektora', max_length=1, default='n', choices=SEX_REQUIRED_CHOICES)
    slovak          = models.BooleanField('Výuka ve slovenštině', default=True)
    slug            = models.CharField('Klíč', max_length=32, unique=True, editable=False)
    discount        = models.SmallIntegerField('Sleva v %', default=0, validators=[ MaxValueValidator(100), MinValueValidator(0) ])
    target          = models.ManyToManyField(Lector, verbose_name='Výběr lektora', blank=True, related_name='demand_aimed')
    taken_by        = models.ForeignKey(Lector, verbose_name='Doučuje lektor', editable=False, null=True, related_name='demand_taken')

    class Meta:
        verbose_name = "Poptávka"
        verbose_name_plural = "Poptávky"

    def __unicode__(self):
        return '{} na úrovnni {}'.format( self.subject, self.level).strip()

    def is_taken(self):
        return True if self.taken_by else False

    @cached_property
    def is_free(self):
        return False if self.target.all() else True

    def deactivate(self):
        self.status = 1

    def activate(self):
        self.status = 0

    def do_discount(self, rate):
        self.discount = rate

    def is_discounted(self):
        return True if self.discount!=0 else False

    def pay_later_befor(self):
        return self.date_taken + timedelta(days=sets.pay_later_limit())

    def towns_as_str(self):
        return ', '.join([town.name for town in self.towns.all()])

    def get_charge(self):
        charge = sets.get_charge_list[self.students][self.lessons]
        charge -= self.discount * charge / 100
        return  charge

    def full_name(self):
        return '{} {}'.format(self.first_name, self.last_name)

    def get_suitable_lectors(self):
        return Lector.objects.filter(
                teach__in=Teach.objects.filter(subject=self.subject, level=self.level),
                towns__in=self.towns.all()
        ).distinct()

    def get_lectors_to_notify_by_email(self):
        if self.is_free:
            return [ str(lector.email) for lector in self.get_suitable_lectors().filter(notify_suited__in=['m','b']) ]
        else:
            return [ str(lector.email) for lector in Lector.objects.filter(pk__in=self.target.all()) ]

    def get_lectors_to_notify_by_sms(self):
        if self.is_free:
            return [ str(lector.phone) for lector in self.get_suitable_lectors().filter(notify_suited__in=['s','a','b']) ]
        else:
            return [ str(lector.phone) for lector in Lector.objects.filter(pk__in=self.target.all(), notify_aimed='b') ]

    def notify_new(self):
        send_mail(
            sets.notif_new_suited_mail_subject if self.is_free else sets.notif_new_aimed_mail_subject,
            '{}\n\nwww.{}/poptavka/{}/'.format(sets.notif_new_suited_mail_message if self.is_free else sets.notif_new_aimed_mail_message, settings.DOMAIN, self.pk ).strip(),
            sets.default_email_address,
            self.get_lectors_to_notify_by_email(),
            fail_silently=False,
        )
        send_sms_queue(
            self.get_lectors_to_notify_by_sms(),
            '{} www.{}/poptavka/{}/'.format(sets.notif_new_suited_sms if self.is_free else sets.notif_new_aimed_sms, settings.DOMAIN, self.pk)
        )

    def confirm_new(self):
        send_mail(
            sets.confi_new_mail_subject,
            '{}\n\nwww.{}/moje-doucovani/{}/'.format( sets.confi_new_mail_message, settings.DOMAIN, self.slug ).strip(),
            sets.default_email_address,
            [self.email],
            fail_silently=False,
        )

    def confirm_updated(self):
        send_mail(
            sets.confi_updated_mail_subject,
            '{}\n\nwww.{}/moje-doucovani/{}/'.format( sets.confi_updated_mail_message, settings.DOMAIN, self.slug ).strip(),
            sets.default_email_address,
            [self.email],
            fail_silently=False,
        )

    def save(self, *args, **kwargs):
        # add random unique slug key
        try:
            self.slug = get_random_string(length=32)
            with transaction.atomic():
                super(Demand, self).save(*args, **kwargs)
        except IntegrityError as e:
            # if slug already exists, try it 32times, then give it up
            for i in range(32):
                self.slug = get_random_string(length=32)
                try:
                    with transaction.atomic():
                        super(Demand, self).save(*args, **kwargs)
                        break
                except IntegrityError:
                    continue
            else:
                raise IntegrityError(e.message)


class AccountRequest(models.Model):
    """Record of each request sent to bank API."""
    account_id      = models.DecimalField("Číslo účtu", max_digits=10, decimal_places=0, editable=False)
    # bank_id         = models.CharField("Číslo banky", max_length=4)
    # currency        = models.CharField("Měna", max_length=3)
    # iban            = models.CharField("IBAN", max_length=34)
    # bic             = models.CharField("BIC", max_length=11)
    opening_balance = models.DecimalField("Počáteční satv", max_digits=18, decimal_places=2, editable=False)
    closing_balance = models.DecimalField("Konečný satv", max_digits=18, decimal_places=2, editable=False)
    date_start      = models.DateField("Datum od", editable=False)
    date_end        = models.DateField("Datum do", editable=False)
    id_to           = models.DecimalField("Do id pohybu", max_digits=12, decimal_places=0, null=True, editable=False)
    id_from         = models.DecimalField("Od id pohybu", max_digits=12, decimal_places=0, null=True, editable=False)
    id_last_download = models.DecimalField("Id posledního úspěšně staženého pohybu", max_digits=12, decimal_places=0, null=True, editable=False)

    class Meta:
        verbose_name = 'Požadavek na výpis'
        verbose_name_plural = 'Požadavky na výpis'

    def __unicode__(self):
        return str(self.date_end)



class AccountTransaction(models.Model):
    """Record of each change on bank account."""
    transaction_id  = models.DecimalField('ID pohybu', max_digits=12, decimal_places=0, unique=True, editable=False)
    date            = models.DateField('Datum', editable=False)
    volume          = models.DecimalField('Objem', max_digits=18, decimal_places=2)# editable=False
    currency        = models.CharField('Měna', max_length=3, editable=False)
    counterparty    = models.CharField('Protiúčet', max_length=255, null=True, editable=False)
    counterparty_name = models.CharField('Název protiúčetu', max_length=255, null=True, editable=False)
    bank_code       = models.CharField('Kód banky protiúčtu', max_length=10, null=True, editable=False)
    bank_name       = models.CharField('Název banky protiúčtu', max_length=255, null=True, editable=False)
    constant_symbol = models.DecimalField('Konstantní symbol', max_digits=4, decimal_places=0, null=True, editable=False)
    variable_symbol = models.DecimalField('Variabilní symbol', max_digits=10, decimal_places=0, null=True)# editable=False
    specific_symbol = models.DecimalField('Specifický symbol', max_digits=10, decimal_places=0, null=True, editable=False)
    user_identification = models.CharField('Uživaletská identifikace', max_length=255, null=True, editable=False)
    message         = models.CharField('Zpráva pro příjemce', max_length=140, null=True, editable=False)
    transaction_type = models.CharField('Typ pohybu', max_length=255, null=True, editable=False)
    autor           = models.CharField('Provedl', max_length=50, null=True, editable=False)
    specification   = models.CharField('Upřesnění', max_length=255, null=True, editable=False)
    comment         = models.CharField('Komentář', max_length=255, null=True, editable=False)
    bic             = models.CharField('BIC', max_length=11, null=True, editable=False)
    command_id      = models.DecimalField('ID pokynu', max_digits=12, decimal_places=0, null=True, editable=False)

    class Meta:
        verbose_name = 'Pohyb na účtě'
        verbose_name_plural = 'Pohyby na účtě'

    def __unicode__(self):
        return str(self.transaction_id)
    #
    # def save(self, *args, **kwargs):
    #     if self._state.adding:
    #         try:
    #             return super(AccountTransaction, self).save(*args, **kwargs)
    #         except:
    #             pass
    #     else:
    #         pass


class CreditTransaction(models.Model):
    """Record of change of credit.

    When credit have to be changed, CreditTransaction must be successfully saved
    first. CreditTransaction can be only created by these actions:

    1. A new AccountTransaction with valid variable_symbol is just added.
    2. Lector just took a Demand.
    3. A new SuperuserCreditReturn is just added.
    4. A new AccountTransaction match SuperuserCreditBlock with valid variable_symbol
    and specific_symbol, and thus new MoneyReturn is just added.

    No Superuser have permission to add or modify CreditTransaction directly.
    Superuser only can add SuperuserCreditReturn or add SuperuserCreditBlock and
    make a payment with appropriate specific_symbol based on SuperuserCreditBlock id.
    """
    # SuperuserCreditReturn, SuperuserCreditBlock and MoneyReturn are not implemented yet.
    TRANSACTION_TYPE_CHOICES =(
        ('d', 'Poplatek za převzetí poptávky'),
        ('c', 'Dobytí kreditu'),
        ('r', 'Vrácení kreditu '),
    )
    transaction_type= models.CharField('Typ transakce', max_length=1, default='n', choices=TRANSACTION_TYPE_CHOICES, editable=False)
    datetime        = models.DateTimeField('Zaúčtováno', auto_now_add=True, editable=False)
    volume          = models.DecimalField('Částka', default=0, editable=False, max_digits=12, decimal_places=2)
    lector          = models.ForeignKey(Lector, verbose_name='Lektor', editable=False, null=False)
    open_balance    = models.DecimalField('Počáteční stav', default=0, editable=False, max_digits=12, decimal_places=2, null=False)
    close_balance   = models.DecimalField('Konečný stav', default=0, editable=False, max_digits=12, decimal_places=2, null=False)
    account_transaction = models.OneToOneField(AccountTransaction, editable=False, null=True)
    demand          = models.OneToOneField(Demand, editable=False, null=True)
    reason          = models.CharField('Důvod vrácení', max_length=100, default='')
    comment         = models.CharField('Poznámka', max_length=100, default='')

    class Meta:
        verbose_name = 'Pohyb kreditu'
        verbose_name_plural = 'Pohyby kreditu'

    def __unicode__(self):
        return self.transaction_type

    def set_balance(self):
        if self.lector_id:
            self.open_balance = self.lector.credit
            self.close_balance = self.lector.credit + self.volume
            # if self.transaction_type == 'd' and self.close_balance < 0:
            #     raise CreditError

    def transaction_type_is_valid(self, *args, **kwargs):
        if self.transaction_type == 'd':
            if self.demand_id and not self.account_transaction_id:
                return True
            else:
                return False
        elif self.transaction_type == 'c':
            if self.account_transaction_id and not self.demand_id:
                return True
            else:
                return False
        elif self.transaction_type == 'r':
            if self.reason and not self.account_transaction_id and not self.demand_id:
                return True
            else:
                return False
        else:
            return False

    def save(self, *args, **kwargs):
        if self._state.adding and self.transaction_type_is_valid():
            self.set_balance()
            try:
                return super(CreditTransaction, self).save(*args, **kwargs)
            except:
                pass


def generate_symbol(id):
    """Generate unique symbol based on given id."""
    symbol = str(id)
    balance = [4,8,5,10,9,7,3,6]
    complement = ['00','50','09','40','07','30','05','20','03','10','01']
    s = 0
    x = symbol[::-1]
    for i in range(len(x)):
        s += int(x[i]) * balance[i]
    return int( symbol + complement[ s % 11 ] )

@receiver(post_save, sender=User)
def lector_add(sender, **kwargs):
    """Create a Lector for every new User with unique variable_symbol."""
    if kwargs['created']:
        l = Lector.objects.create( user=kwargs['instance'], variable_symbol=generate_symbol( kwargs['instance'].pk ))

@receiver(post_save, sender=Demand)
def notification_demand_added(sender, **kwargs):
    if not kwargs['created']:
        kwargs['instance'].confirm_updated()

@receiver(post_save, sender=AccountTransaction)
def account_transaction_added(sender, **kwargs):
    """Create new CreditTransaction

    Check if new 'just created' AccountTransaction has a valid variable_symbol.
    If so, create new CreditTransaction related to appropriate Lector.
    """
    # if kwargs['created']:
    # only take place if AccountTransaction is just created
    lector = None
    try:
        lector = Lector.objects.get( variable_symbol=kwargs['instance'].variable_symbol )
    except:
        pass
    if lector:
        # if there is a Lector with variable_symbol == variable_symbol
        with transaction.atomic():
            # create appropriate CreditTransaction
            CreditTransaction.objects.create(
                transaction_type = 'c',
                volume = kwargs['instance'].volume,
                lector = lector,
                account_transaction = kwargs['instance'],
                comment = kwargs['instance'].message,
            )
    else:
        # check wrong variable_symbol here!
        pass
    # else:
    #     pass

@receiver(post_save, sender=CreditTransaction)
def credit_transaction_added(sender, **kwargs):
    """ The only one function that can change lector's credit.

    The only time it's being called is when a new CreditTransaction
    object is just created.
    """"
    if kwargs['created']:
        # only take place if CreditTransaction is just created
        self = kwargs['instance']
        if self.transaction_type == 'd':
            # if charge for demand
            self.lector.credit = self.close_balance
            if self.lector.credit <= 0:
                # check if pay_later is being used
                self.lector.pay_later = self.demand
            self.lector.save()
            self.demand.status = 2
            self.demand.date_taken = datetime.now()
            self.demand.taken_by = self.lector
            self.demand.save()
        elif self.transaction_type == 'c':
            # if credit top-up
            self.lector.credit = self.close_balance
            if self.lector.pay_later and self.close_balance >= 0:
                # check if pay_later is being paid
                self.lector.pay_later = None
            self.lector.save()
        elif self.transaction_type == 'r':
            # if return credit
            self.lector.credit = self.close_balance
            self.lector.save()
        else:
            pass
    else:
        pass
