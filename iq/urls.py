# -*- coding: utf-8 -*-
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls import url, include, static
from django.conf.urls.static import static

from . import views

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^registrace/$', views.signup.as_view(), name='signup'),
    url(r'^relog/(?P<next>[-\w]+)/$', views.relog, name='relog'),
    url(r'^prihlaseni/$', auth_views.login, name='login'),
    url(r'^odhlaseni/$', auth_views.logout, name='logout'),
    url(r'^verified-email-field/', include('verified_email_field.urls')),
    url(r'^verified-phone-field/', include('verified_phone_field.urls')),
    url(r'^lektori/$', views.LectorListView.as_view()),
    url(r'^lektor/(?P<pk>[0-9]+)/$', views.LectorDetailView.as_view()),
    url(r'^muj-profil/$', views.LectorProfileUpdateView.as_view()),
    url(r'^moje-nastaveni/$', views.LectorSettingsUpdateView.as_view()),
    url(r'^zmena-emailu/$', views.UserEmailUpdateView.as_view()),
    url(r'^zmena-telefonu/$', views.LectorPhoneUpdateView.as_view()),
    url(r'^dobit-kredit/$', views.credit_topup_view),
    url(r'^predmety/$', views.CategoryListView.as_view()),
    url(r'^predmety/(?P<slug>[-\w]+)/$', views.SubjectListView.as_view()),
    url(r'^predmet/(?P<slug>[-\w]+)/$', views.SubjectDetailView.as_view()),
    url(r'^poptavky/$', views.DemandListView.as_view()),
    url(r'^vzit-poptavku/(?P<pk>[0-9]+)/$', views.TakeDemandView.as_view()),
    url(r'^poptavka/(?P<pk>[0-9]+)/$', views.DemandDetailView.as_view()),
    url(r'^moje-doucovani/$', views.MyDemandListView.as_view()),
    url(r'^moje-doucovani/(?P<pk>[0-9]+)/$', views.MyDemandDetailView.as_view()),
    url(r'^moje-doucovani/(?P<slug>[a-zA-Z0-9]{32})/$', views.DemandUpdateView.as_view()),
    url(r'^nova-poptavka/', views.DemandSessionWizardView.as_view()),
    url(r'^poptavka-pridana/', views.message_view, {'msg':'added'}),
    url(r'^poptavka-zmenena/', views.message_view, {'msg':'updated'}),
    url(r'^obchodni-podminky/lektor/', views.message_view, {'msg':'lector_tac'}),
    url(r'^obchodni-podminky/student/', views.message_view, {'msg':'student_tac'}),
    url(r'^o-nas/', views.message_view, {'msg':'about_us'}),
    url(r'^kontakt/', views.message_view, {'msg':'contact'}),
    url(r'^$', views.home),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
