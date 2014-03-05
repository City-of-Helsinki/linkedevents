from django.conf.urls import patterns, include, url
from rest_framework import routers
from events import views

router = routers.DefaultRouter()
router.register(r'events', views.EventViewSet)
router.register(r'locations', views.LocationViewSet)
router.register(r'organizations', views.OrganizationViewSet)
router.register(r'categories', views.CategoryViewSet)
router.register(r'languages', views.LanguageViewSet)

#urlpatterns = router.urls
urlpatterns = patterns(
    '',
    url(r'^', include(router.urls)),
    #url(r'^api-auth/', include('rest_framework.urls', namespace='rest_framework')),
)
