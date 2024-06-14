from rest_framework.routers import SimpleRouter

from . import api

app_name = "data_analytics"

router = SimpleRouter()
router.register(r"administrative_division", api.AdministrativeDivisionViewSet)
router.register(r"data_source", api.DataSourceViewSet)
router.register(r"event", api.EventViewSet)
router.register(r"keyword", api.KeywordViewSet)
router.register(r"language", api.LanguageViewSet)
router.register(r"offer", api.OfferViewSet)
router.register(r"organization", api.OrganizationViewSet)
router.register(r"place", api.PlaceViewSet)
router.register(r"registration", api.RegistrationViewSet)
router.register(r"signup", api.SignUpViewSet)

urlpatterns = router.urls
