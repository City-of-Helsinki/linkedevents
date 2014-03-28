from django.conf.urls import patterns, include, url
from rest_framework import routers
from events import views

router = routers.DefaultRouter()
router.register(r'events', views.EventViewSet)
router.register(r'places', views.PlaceViewSet)
router.register(r'organizations', views.OrganizationViewSet)
router.register(r'categories', views.CategoryViewSet)
router.register(r'languages', views.LanguageViewSet)
router.register(r'persons', views.PersonViewSet)

urlpatterns = patterns(
    '',
    url(r'^', include(router.urls)),
)
