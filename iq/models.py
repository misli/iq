# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json

from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import MaxValueValidator, MinValueValidator
from django.core.mail import send_mail
from django.db import models, transaction, IntegrityError
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.forms.widgets import Select, SelectMultiple
from django.utils.crypto import get_random_string
from django.utils.text import slugify


class TownSelectWidget(SelectMultiple):
    template_name = 'iq/widgets/town_select.html'

    def get_context(self, name, value, attrs):
        context = super(TownSelectWidget, self).get_context(name, value, attrs)
        towns = Town.objects.all().order_by('name')
        town_list = json.dumps([ [ t.pk, t.name, t.county, ] for t in towns ])
        context['widget']['town_list'] = town_list
        context['widget']['attrs']['id'] = 'select_towns'
        if self.allow_multiple_selected:
            context['widget']['attrs']['multiple'] = 'multiple'
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


class Settings(models.Model):
    default_email_address               = models.EmailField('výchozí adresa pro odesílání emailu', default='info@'+settings.DOMAIN)
    notif_email_new_demand_subject      = models.CharField('Upozornění na novou poptávku: předmět', default='Nová poptávka', max_length=50)
    notif_email_new_demand_message      = models.CharField('Upozornění na novou poptávku: zpráva', default='Do systému byla přidána nová poptávka', max_length=500)
    confi_email_new_demand_subject      = models.CharField('Potvrzení nové poptávky: předmět', default='Nová poptávka', max_length=50)
    confi_email_new_demand_message      = models.CharField('Potvrzení nové poptávky: zpráva', default='Vaše poptávka byla úspěšně přidána do systému. Zobrazit a upravit ji můžete tímto odkazem', max_length=500)
    confi_email_demand_updated_subject  = models.CharField('Potvrzení úpravy poptávky: předmět', default='Poptávka upravena', max_length=50)
    confi_email_demand_updated_message  = models.CharField('Potvrzení úpravy poptávky: zpráva', default='Vaše poptávka byla úspěšně upravena. Zobrazit a upravit ji můžete tímto odkazem', max_length=500)
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

    def get_charge_list(self):
        return [
            [self.charge1x1, self.charge1x2, self.charge1x5, self.charge1x10],
            [self.charge2x1, self.charge2x2, self.charge2x5, self.charge2x10],
            [self.charge3x1, self.charge3x2, self.charge3x5, self.charge3x10],
            [self.charge4x1, self.charge4x2, self.charge4x5, self.charge4x10],
        ]

    def notify_new_demand(self, demand):
        lectors = Lector.objects.filter(is_active=True)
        to_all = []
        for l in lectors:
            to_all.append(l.email())
        send_mail(
            self.notif_email_new_demand_subject,
            '{}\n\nwww.{}/poptavka/{}/'.format( self.notif_email_new_demand_message, settings.DOMAIN, demand.pk ).strip(),
            self.default_email_address,
            to_all,
            fail_silently=False,
        )

    def confirm_new_demand(self, demand):
        send_mail(
            self.confi_email_new_demand_subject,
            '{}\n\nwww.{}/moje-doucovani/{}/'.format( self.confi_email_new_demand_message, settings.DOMAIN, demand.slug ).strip(),
            self.default_email_address,
            [demand.email],
            fail_silently=False,
        )

    def confirm_demand_updated(self, demand):
        send_mail(
            self.confi_email_demand_updated_subject,
            '{}\n\nwww.{}/moje-doucovani/{}/'.format( self.confi_email_demand_updated_message, settings.DOMAIN, demand.slug ).strip(),
            self.default_email_address,
            [demand.email],
            fail_silently=False,
        )

    def save(self, *args, **kwargs):
        # neuloží víc než jedno nastavení
        if Settings.objects.exists() and not self.pk:
            pass
        else:
            return super(Settings, self).save(*args, **kwargs)



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

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super(Town, self).save(*args, **kwargs)


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
        super(Category, self).save(*args, **kwargs)


class Scheme(models.Model):
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
        super(Subject, self).save(*args, **kwargs)


class Level(models.Model):
    name    = models.CharField('Název úrovně', max_length=50)
    order   = models.PositiveSmallIntegerField('Pořadí')
    scheme  = models.ForeignKey(Scheme, on_delete=models.PROTECT, verbose_name = 'Systém úrovní')

    class Meta:
        verbose_name = "Úroveň"
        verbose_name_plural = "Úroveně"

    def __unicode__(self):
        return self.name


class LectorManager(models.Manager):
    def get_queryset(self):
        return super(LectorManager, self).get_queryset().filter(user__is_active=True)


def user_directory_path(instance, filename):
    return 'lector_{0}/{1}'.format(instance.user.id, filename)

class Lector(models.Model):
    SEX_CHOICES = (
        ('n', 'Neřeknu'),
        ('f', 'Žena'),
        ('m', 'Muž'),
    )
    NOTICE_CHOICES  = (
        (0,'vůbec ne'),
        (1,'e-mail denní přehled'),
        (2,'e-mail ihned'),
        (3,'e-mail ihned + denní přehled'),
        (4,'sms ihned'),
        (5,'sms ihned + e-mail ihned'),
        (6,'sms ihned + e-mail denní přehled'),
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
    sex             = models.CharField('Jsem', max_length=1, choices=SEX_CHOICES, default='n')
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
    notice_any      = models.PositiveSmallIntegerField('Všechny nové poptávky', choices=NOTICE_CHOICES, default=0)
    notice_suited   = models.PositiveSmallIntegerField('Poptávky pro mě', choices=NOTICE_CHOICES, default=1)
    notice_aimed    = models.PositiveSmallIntegerField('Poptávky cílené na mě', choices=NOTICE_CHOICES, default=2)
    is_active       = models.BooleanField(default=True)
    variable_symbol = models.DecimalField("Variabilní symbol", max_digits=10, decimal_places=0, editable=False)
    objects         = LectorManager()

    class Meta:
        verbose_name = 'Lektor'
        verbose_name_plural = 'Lektoři'

    def __unicode__(self):
        return self.full_name() or self.user.email

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
        """ return False if "able to take", otherwise the reason why not able """
        ABLE_CHOICES=[
            False,
            "nemáš aktivní účet",
            "tenhle předmět neumíš",
            "v tomhle městě nedoučuješ",
            "nemáš dostatečný kredit",
            "nemáš vyplněný profil",
        ]
        if self.has_complete_profile():
            if demand.get_charge() <= self.credit:
                compare = list(demand.towns.all()) + list(self.towns.all())
                if len( set( compare ) ) < len( compare ):
                    if demand.subject in self.subjects.all():
                        if self.is_active:
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

    def email(self):
        return self.user.email

    def date_registred(self):
        return self.user.date_joined

    def full_name(self):
        return '{} {} {} {}'.format(self.titles_before or "", self.first_name, self.last_name, self.titles_after or "").strip()



class Teach(models.Model):
    lector      = models.ForeignKey(Lector, verbose_name="Lektor")
    subject     = models.ForeignKey(Subject, verbose_name="Předmět")
    level       = models.ForeignKey(Level, verbose_name="Úroveň")
    price       = models.IntegerField("Cena při cílené poptávce")

    def __unicode__(self):
        return '{} na úrovni {}'.format(self.subject.name, self.level.name)

    def save(self, *args, **kwargs):
        if self.subject.scheme == self.level.scheme:
            super(Teach, self).save(*args, **kwargs)
        else:
            raise IntegrityError("schemes didn't match")

    class Meta:
        unique_together = (('lector', 'subject', 'level'),)


class Holyday(models.Model):
    lector   = models.ForeignKey(Lector)
    start    = models.DateField(auto_now=True)
    end      = models.DateField(auto_now=True)


class Demand(models.Model):
    SEX_REQUIRED_CHOICES = (
        ('n', 'Ne'),
        ('f', 'Chci lektorku'),
        ('m', 'Chci lektora'),
    )
    DEMAND_TYPE_CHOICES =(
        ('f', 'Poptávna volná'),
        ('t', 'Poptávka cílená')
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
    agree           = models.BooleanField('Souhlasím s obchodními podmínkami',default=False, )
    demand_type     = models.CharField('Typ poptávky', max_length=1, default='f', choices=DEMAND_TYPE_CHOICES)
    status          = models.PositiveSmallIntegerField('Status', default=0, choices=STATUS_CHOICES)
    first_name      = models.CharField('Jméno', max_length=100)
    last_name       = models.CharField('Príjmení', max_length=100)
    email           = models.EmailField('E-mail')
    towns           = models.ManyToManyField(Town, verbose_name='Město')
    subject         = models.ForeignKey(Subject, on_delete=models.PROTECT, verbose_name='Předmět')
    level           = models.ForeignKey(Level, on_delete=models.PROTECT, verbose_name='Úroveň')
    date_posted     = models.DateTimeField('Vloženo', auto_now_add=True)
    date_updated    = models.DateTimeField('Aktualizováno', auto_now=True)
    lessons         = models.PositiveSmallIntegerField('Počet lekcí', default=1, choices=LESSONS_CHOICES)
    students        = models.PositiveSmallIntegerField('Počet studentů', default=0, choices=STUDENTS_CHOICES)
    subject_desript = models.CharField('Popis doučované láky', max_length=300)
    time_desript    = models.CharField('Kdy se můžem sejít', max_length=300)
    commute         = models.BooleanField('Můžu dojíždět', default=True)
    sex_required    = models.CharField('Požaduji pohlaví lektora', max_length=1, default='n', choices=SEX_REQUIRED_CHOICES)
    slovak          = models.BooleanField('Výuka ve slovenštině', default=True)
    slug            = models.CharField('Klíč', max_length=32, unique=True, editable=False)
    discount        = models.SmallIntegerField('Sleva v %', default=0, validators=[ MaxValueValidator(100), MinValueValidator(0) ])
    target          = models.ManyToManyField(Lector, verbose_name='Zobrazit těmto lektorům', blank=True, related_name='demand_requiring')
    taken_by        = models.ForeignKey(Lector, verbose_name='Doučuje lektor', editable=False, null=True, related_name='demand_taken')

    def is_taken(self):
        if self.taken_by != None:
            return True
        else:
            return False

    def deactivate(self):
        self.status = 1

    def activate(self):
        self.status = 0

    def do_discount(self, rate):
        self.discount = rate

    def is_discounted(self):
        return True if self.discount!=0 else False

    def get_charge(self):
        charge = sets.get_charge_list()[self.students][self.lessons]
        charge -= self.discount * charge / 100
        return  charge

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

    def __unicode__(self):
        return '{} na úrovnni {}'.format( self.subject, self.level).strip()

    class Meta:
        verbose_name = "Poptávka"
        verbose_name_plural = "Poptávky"


class AccountRequest(models.Model):
    account_id      = models.DecimalField("Číslo účtu", max_digits=10, decimal_places=0)
    # bank_id         = models.CharField("Číslo banky", max_length=4)
    # currency        = models.CharField("Měna", max_length=3)
    # iban            = models.CharField("IBAN", max_length=34)
    # bic             = models.CharField("BIC", max_length=11)
    opening_balance = models.DecimalField("Počáteční satv", max_digits=18, decimal_places=2)
    closing_balance = models.DecimalField("Konečný satv", max_digits=18, decimal_places=2)
    date_start      = models.DateField("Datum od")
    date_end        = models.DateField("Datum do")
    id_to           = models.DecimalField("Do id pohybu", max_digits=12, decimal_places=0, null=True)
    id_from         = models.DecimalField("Od id pohybu", max_digits=12, decimal_places=0, null=True)
    id_last_download = models.DecimalField("Id posledního úspěšně staženého pohybu", max_digits=12, decimal_places=0, null=True)

    def __unicode__(self):
        return str(self.date_end)

    class Meta:
        verbose_name = 'Požadavek na výpis'
        verbose_name_plural = 'Požadavky na výpis'


class AccountTransaction(models.Model):
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
    #
    # def save(self, *args, **kwargs):
    #     if self._state.adding:
    #         try:
    #             return super(AccountTransaction, self).save(*args, **kwargs)
    #         except:
    #             pass
    #     else:
    #         pass

    def __unicode__(self):
        return str(self.transaction_id)

    class Meta:
        verbose_name = 'Pohyb na účtě'
        verbose_name_plural = 'Pohyby na účtě'


class CreditTransaction(models.Model):
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
        else:
            pass

    def __unicode__(self):
        return self.transaction_type

    class Meta:
        verbose_name = 'Pohyb kreditu'
        verbose_name_plural = 'Pohyby kreditu'



def generate_varsym(userid):
    # generate unique variable symbol
    varsym = str(userid)
    balance = [4,8,5,10,9,7,3,6]
    complement = ['00','50','09','40','07','30','05','20','03','10','01']
    s = 0
    x = varsym[::-1]
    for i in range(len(x)):
        s += int(x[i]) * balance[i]
    return int( varsym + complement[ s % 11 ] )

@receiver(post_save, sender=User)
def lector_add(sender, **kwargs):
    # create a Lector for every new User with unique variable_symbol
    if kwargs['created']:
        l = Lector.objects.create( user=kwargs['instance'], variable_symbol=generate_varsym( kwargs['instance'].pk ))

@receiver(post_save, sender=Demand)
def notification_demand_added(sender, **kwargs):
    if kwargs['created']:
        sets.notify_new_demand(kwargs['instance'])
        sets.confirm_new_demand(kwargs['instance'])
    else:
        sets.confirm_demand_updated(kwargs['instance'])

@receiver(post_save, sender=AccountTransaction)
def account_transaction_added(sender, **kwargs):
    # only take place if AccountTransaction is just created
    # if kwargs['created']:
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
    # only take place if CreditTransaction is just created
    if kwargs['created']:
        self = kwargs['instance']
        if self.transaction_type == 'd':
            # if charge for demand
            self.lector.credit = self.close_balance
            self.lector.save()
            self.demand.status = 2
            self.demand.taken_by = self.lector
            self.demand.save()
        elif self.transaction_type == 'c':
            # if credit top-up
            self.lector.credit = self.close_balance
            self.lector.save()
        elif self.transaction_type == 'r':
            # if return credit
            self.lector.credit = self.close_balance
            self.lector.save()
        else:
            pass
    else:
        pass
