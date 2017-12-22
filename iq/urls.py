# -*- coding: utf-8 -*-
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.conf.urls import url, include
from . import views

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^registrace/$', views.signup.as_view(), name='signup'),
    url(r'^relog/$', views.relog, name='relog'),
    url(r'^prihlaseni/$', auth_views.login, name='login'),
    url(r'^odhlaseni/$', auth_views.logout, name='logout'),
    url(r'^verified-email-field/', include('verified_email_field.urls')),
    url(r'^acc/$', views.AccounManager.as_view()),
    url(r'^lektori/$', views.LectorListView.as_view()),
    url(r'^lektor/(?P<pk>[0-9]+)/$', views.LectorDetailView.as_view()),
    url(r'^lektor/uprava-profilu/$', views.LectorUpdateView.as_view()),
    url(r'^predmety/$', views.CategoryListView.as_view()),
    url(r'^predmety/(?P<slug>[-\w]+)/$', views.SubjectListView.as_view()),
    url(r'^predmet/(?P<slug>[-\w]+)/$', views.SubjectDetailView.as_view()),
    url(r'^poptavky', views.DemandListView.as_view()),
    url(r'^poptavka/(?P<pk>[0-9]+)/', views.DemandDetailView.as_view()),
    url(r'^moje-poptavka/(?P<slug>[a-zA-Z0-9]{32})/$', views.DemandUpdateView.as_view()),
    url(r'^nova-poptavka/', views.DemandSessionWizardView.as_view()),
    url(r'^poptavka-zmenena/', views.demand_updated_view),
    url(r'^$', views.home),
]
