from django.utils.cache import add_never_cache_headers


class AuthenticationCacheDisableMiddleware:
    """
    Middleware to disable client side caching for authenticated requests.
    Adds a "Cache-Control: max-age=0, no-cache, no-store, must-revalidate, private"
    header to a response to indicate that a response should never be cached.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated:
            add_never_cache_headers(response)
        return response
