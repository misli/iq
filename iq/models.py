# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.utils.crypto import get_random_string
from django.db import models, transaction, IntegrityError
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db.models.signals import post_save
from django.core.validators import MaxValueValidator, MinValueValidator
from django.dispatch import receiver
from autoslug import AutoSlugField
from django.conf import settings
from django.core.mail import send_mail
import datetime
import json
from django.forms.widgets import SelectMultiple

class TownSelectWidget(SelectMultiple):
    template_name = 'iq/widgets/town_select.html'

    def get_context(self, name, value, attrs):
        context = super(TownSelectWidget, self).get_context(name, value, attrs)
        towns = Town.objects.all().order_by('name')
        town_list = json.dumps([ [  t.pk, t.name, t.county, ] for t in towns ])
        context['widget']['town_list'] = town_list
        context['widget']['attrs']['id'] = 'select_towns'
        if self.allow_multiple_selected:
            context['widget']['attrs']['multiple'] = 'multiple'
        return context

    class Media:
        css = {
            'all': ('css/town_select_widget.css',)
        }
        # js = ('js/town_select_widget.js',)


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
    charge_list = [
        [charge1x1, charge1x2, charge1x5, charge1x10],
        [charge2x1, charge2x2, charge2x5, charge2x10],
        [charge3x1, charge3x2, charge3x5, charge3x10],
        [charge4x1, charge4x2, charge4x5, charge4x10],
    ]
    def notify_new_demand(self, demand):
        lectors = Lector.objects.all()
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
            '{}\n\nwww.{}/moje-poptavka/{}/'.format( self.confi_email_new_demand_message, settings.DOMAIN, demand.slug ).strip(),
            self.default_email_address,
            [demand.email],
            fail_silently=False,
        )

    def confirm_demand_updated(self, demand):
        send_mail(
            self.confi_email_demand_updated_subject,
            '{}\n\nwww.{}/moje-poptavka/{}/'.format( self.confi_email_demand_updated_message, settings.DOMAIN, demand.slug ).strip(),
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

    def __unicode__(self):
        return "Nastavení"

    class Meta:
        verbose_name = "Nastavení"
        verbose_name_plural = "Nastavení"

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
    # email = VerifiedEmailField('e-mail', unique=True)
    email = models.EmailField('e-mail', unique=True)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    objects = UserManager()


class Town(models.Model):
    county_choices =(
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
    name        = models.CharField(max_length=33)
    slug        = AutoSlugField(populate_from='name')
    county      = models.CharField(max_length=1, choices=county_choices)
    countyCapital = models.BooleanField()

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name = "Město"
        verbose_name_plural = "Města"


class Category(models.Model):
    name        = models.CharField('název', max_length=50)
    slug        = AutoSlugField(null=False, populate_from='name')
    description  = models.TextField('popis', max_length=500)

    class Meta:
        verbose_name = "Kategorie předmětů"
        verbose_name_plural = "Kartegorie předmětů"

    def __unicode__(self):
        return self.name


class Scheme(models.Model):
    name = models.CharField('název', max_length=50)

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name = 'Systém úrovní'
        verbose_name_plural = 'Systémy úrovní'


class Subject(models.Model):
    name        = models.CharField('název', max_length=50)
    slug        = AutoSlugField(null=False, populate_from='name')
    description  = models.TextField('popis', max_length=500)
    category    = models.ForeignKey(Category, on_delete=models.PROTECT, verbose_name = 'Kategorie')
    scheme      = models.ForeignKey(Scheme, verbose_name = 'systém úrovní')

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name = 'Předmět'
        verbose_name_plural = 'Předměty'


class Level(models.Model):
    name    = models.CharField('název úrovně', max_length=50)
    order   = models.PositiveSmallIntegerField('pořadí')
    scheme  = models.ForeignKey(Scheme, on_delete=models.PROTECT, verbose_name = 'systém úrovní')

    def __unicode__(self):
            return self.name

    class Meta:
        verbose_name = "Úroveň"
        verbose_name_plural = "Úroveně"


# title_before = ("as.","odb. as.","doc.","prof.","Bc.","BcA.","Ing.","Ing. arch.","JUDr.","MDDr.","MgA.","Mgr.","MSDr.","MUDr.","MVDr.","PaedDr.","PharmDr.","PhDr.","PhMr.","RCDr.","RNDr.","RSDr.","RTDr.","ThDr.","ThLic.","ThMgr.")
# title_after = ("CSc.","Dr.","DrSc.","DSc.","Ph.D.","Th.D.","DiS.")

class Lector(models.Model):
    user            = models.OneToOneField(settings.AUTH_USER_MODEL, related_name='lector', on_delete=models.PROTECT, unique=True)
    titles_before   = models.CharField('Tituly před jménem', max_length=20, blank=True, null=True)
    first_name      = models.CharField('Křestní jméno', max_length=20)
    last_name       = models.CharField('Příjmení', max_length=20)
    titles_after    = models.CharField('Tituly za jménem', max_length=20, blank=True, null=True)
    intro           = models.CharField('O mně', max_length=200, blank=True, null=True)
    towns           = models.ManyToManyField(Town, blank=True, verbose_name='Města')
    credit          = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, editable=False)
    subjects        = models.ManyToManyField(Subject, through='Teach', verbose_name='Doučuji')
    is_active       = models.BooleanField(default=True, editable=False)

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
        if self.has_complete_profile():
            if demand.subject in self.subjects.all():
                for town in demand.towns.all():
                    if town in self.towns.all():
                        return True
                else:
                    return False
            else:
                return False
        else:
            return False

    def take_demand(self, demand):
        price = demand.get_price()
        if self.take_ability_check(demand) and self.credit >= price :
            with transaction.atomic:
                TakenDemand(
                    demand=demand,
                    volume=price,
                    lector=self,
                    open_balance=self.credit,
                    close_balance=self.credit-price,
                ).save()
                self.credit-=price
                demand.is_taken = True

    def email(self):
        return self.user.email

    def date_registred(self):
        return self.user.date_joined

    def full_name(self):
        return '{} {} {} {}'.format(self.titles_before or "", self.first_name, self.last_name, self.titles_after or "").strip()

    def __unicode__(self):
        return self.full_name() or self.user.email

    class Meta:
        verbose_name = 'Lektor'
        verbose_name_plural = 'Lektoři'



class Teach(models.Model):
    lector      = models.ForeignKey(Lector, verbose_name="Lektor")
    subject     = models.ForeignKey(Subject, verbose_name="Předmět")
    level       = models.ForeignKey(Level, verbose_name="Úroveň")
    price       = models.IntegerField("Cena")

    class Meta:
        unique_together = (('lector', 'subject', 'level'),)

class Holyday(models.Model):
    lector   = models.ForeignKey(Lector)
    start    = models.DateField(default=datetime.date.today)
    end      = models.DateField(default=datetime.date.today)


class Demand(models.Model):
    lessons_chices =(
        (0, '1 lekce'),
        (1, '2-4 lekce'),
        (2, '5-9 lekcí'),
        (3, '10 a vice'),
    )
    students_chices =(
        (0, '1 student'),
        (1, '2 studenti'),
        (2, '3 studenti'),
        (3, '4 a více studentů'),
    )
    first_name      = models.CharField('Jméno', max_length=100)
    last_name       = models.CharField('Príjmení', max_length=100)
    email           = models.EmailField('E-mail')
    towns           = models.ManyToManyField(Town, verbose_name='Město')
    subject         = models.ForeignKey(Subject, on_delete=models.PROTECT, verbose_name='Předmět')
    level           = models.ForeignKey(Level, on_delete=models.PROTECT, verbose_name='Úroveň')
    date_posted     = models.DateTimeField('Datum Vložení', auto_now_add=True)
    date_updated    = models.DateTimeField('Datum poslední úpravy', auto_now=True)
    lessons         = models.PositiveSmallIntegerField('Počet lekcí', default=1, choices=lessons_chices)
    students        = models.PositiveSmallIntegerField('Počet studentů', default=0, choices=students_chices)
    subject_desript = models.CharField('Popis doučované láky', max_length=300)
    time_desript    = models.CharField('Kdy se můžem sejít', max_length=300)
    is_taken        = models.BooleanField(default=False)
    slug            = models.CharField('Klíč', max_length=32, unique=True, editable=False)
    discount        = models.SmallIntegerField('Sleva v %', default=0, validators=[ MaxValueValidator(100), MinValueValidator(0) ])
    is_active       = models.BooleanField('Je aktivní', default=True)
    visible_for_all = models.BooleanField('Zobratit všem', default=True)
    visible_for     = models.ManyToManyField(Lector, verbose_name='Zobrazit těmto lektorům', blank=True)

    def deactivate(self):
        self.is_active = False

    def activate(self):
        self.is_active = True

    def is_discounted(self):
        return True if self.discount!=0 else False

    def get_charge(self):
        charge = sets.charge_list[self.students][self.lessons]
        charge -= self.discount * charge
        return  charge

    def save(self, *args, **kwargs):
        try:
            self.slug = get_random_string(length=32)
            with transaction.atomic():
                super(Demand, self).save(*args, **kwargs)
        except IntegrityError as e:
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
        return '{} - {}'.format( self.subject, self.level).strip()

    class Meta:
        verbose_name = "Poptávka"
        verbose_name_plural = "Poptávky"


class AccountRequest(models.Model):
    account_id      = models.CharField("Číslo účtu", max_length=10)
    # bank_id         = models.CharField("Číslo banky", max_length=4)
    # currency        = models.CharField("Měna", max_length=3)
    # iban            = models.CharField("IBAN", max_length=34)
    # bic             = models.CharField("BIC", max_length=11)
    opening_balance = models.DecimalField("Počáteční satv", max_digits=12, decimal_places=2)
    closing_balance = models.DecimalField("Konečný satv", max_digits=12, decimal_places=2)
    date_start      = models.DateField("Datum od")
    date_end        = models.DateField("Datum do")
    id_to           = models.BigIntegerField("Do id pohybu", null=True)
    id_from         = models.BigIntegerField("Od id pohybu", null=True)
    id_last_download = models.BigIntegerField("Id posledního úspěšně staženého pohybu")
    date_time       = models.DateTimeField("Datum a čas poselního updatu", auto_now_add=True)

    def __unicode__(self):
        return str(self.date_time)

    class Meta:
        verbose_name = 'Požadavek na výpis'
        verbose_name_plural = 'Požadavky na výpis'


class AccountTransaction(models.Model):
    transaction_id  = models.BigIntegerField('ID pohybu', unique=True, editable=False)
    date            = models.DateField('Datum', editable=False)
    volume          = models.DecimalField('Objem', max_digits=12, decimal_places=2)# editable=False
    currency        = models.CharField('Měna', max_length=3, editable=False)
    counterparty    = models.CharField('Protiúčet', max_length=17, null=True, editable=False)
    counterparty_name = models.CharField('Název protiúčetu', max_length=50, null=True, editable=False)
    bank_code       = models.CharField('Kód banky protiúčtu', max_length=4, null=True, editable=False)
    bank_name       = models.CharField('Název banky protiúčtu', max_length=50, null=True, editable=False)
    constant_symbol = models.CharField('Konstantní symbol', max_length=4, null=True, editable=False)
    variable_symbol = models.BigIntegerField('Variabilní symbol', null=True)# editable=False
    specific_symbol = models.BigIntegerField('Specifický symbol', null=True, editable=False)
    user_identification = models.CharField('Uživaletská identifikace', max_length=100, null=True, editable=False)
    message         = models.CharField('Zpráva pro příjemce', max_length=100, null=True, editable=False)
    transaction_type = models.CharField('Typ pohybu', max_length=100, null=True, editable=False)
    autor           = models.CharField('Provedl', max_length=50, null=True, editable=False)
    specification   = models.CharField('Upřesnění', max_length=100, null=True, editable=False)
    comment         = models.CharField('Komentář', max_length=100, null=True, editable=False)
    bic             = models.CharField('BIC', max_length=11, null=True, editable=False)
    command_id      = models.BigIntegerField('ID pokynu', null=True, editable=False)

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
    transaction_types =(
        ('n', 'neurčeno'),
        ('c', 'dobytí kreditu'),
        ('d', 'Poplatek za převzetí poptávky'),
        ('r', 'Vrácení kreditu'),
    )
    transaction_type= models.CharField('Typ transakce', max_length=1, default='n', choices=transaction_types, editable=False)
    datetime        = models.DateTimeField('Datum a čas zaúčtování', default=datetime.datetime.now, editable=False)
    volume          = models.DecimalField('Částka', default=0, editable=False, max_digits=12, decimal_places=2)
    lector          = models.ForeignKey(Lector, verbose_name='Lektor', editable=False, null=False)
    open_balance    = models.DecimalField('Počáteční stav', default=0, editable=False, max_digits=12, decimal_places=2)
    close_balance   = models.DecimalField('Konečný stav', default=0, editable=False, max_digits=12, decimal_places=2)

    def __unicode__(self):
        return self.transaction_type

    class Meta:
        verbose_name = 'Pohyb kreditu'
        verbose_name_plural = 'Pohyby kreditu'


class CreditTopUp(CreditTransaction):
    def __init__(self, *args, **kwargs):
        super(CreditTopUp, self).__init__(*args, **kwargs)
        self.transaction_type = 'c'

    account_transaction = models.ForeignKey(AccountTransaction, editable=False)


class TakenDemand(CreditTransaction):
    def __init__(self, *args, **kwargs):
        super(TakenDemand, self).__init__(*args, **kwargs)
        self.transaction_type = 'd'

    demand = models.ForeignKey(Demand, editable=False, null=True)


class CreditReturn(CreditTransaction):
    def __init__(self, *args, **kwargs):
        super(TakenDemand, self).__init__(*args, **kwargs)
        self.transaction_type = 'r'

    reasen  = models.CharField('Důvod vrácení', max_length=100, default='Doučování proběhlo v menším, než předpokládaném rozsahu')
    comment = models.CharField('Poznámka', max_length=100, default="")


@receiver(post_save, sender=User)
def lector_add(sender, **kwargs):
    if kwargs['created']:
        l = Lector(user=kwargs['instance'])
        l.save()

@receiver(post_save, sender=Demand)
def notification_demand_added(sender, **kwargs):
    if kwargs['created']:
        sets.notify_new_demand(kwargs['instance'])
        sets.confirm_new_demand(kwargs['instance'])
    else:
        sets.confirm_demand_updated(kwargs['instance'])



@receiver(post_save, sender=AccountTransaction)
def account_transaction_added(sender, **kwargs):
    # if kwargs['created']:
    lector = ""
    try:
        lector = Lector.objects.get( pk=kwargs['instance'].variable_symbol )
    except:
        pass
    if lector:
        with transaction.atomic():
            CreditTopUp(
                account_transaction=kwargs['instance'],
                volume=kwargs['instance'].volume,
                lector=lector,
                open_balance=lector.credit,
                close_balance=lector.credit + kwargs['instance'].volume,).save()
            lector.credit+=kwargs['instance'].volume
            lector.save()
    else:
        pass
