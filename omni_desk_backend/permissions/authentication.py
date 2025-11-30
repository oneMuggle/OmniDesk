from rest_framework.authentication import SessionAuthentication

class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    A custom session authentication class that bypasses CSRF checks.
    WARNING: This should only be used in development environments where CSRF
    token handling is problematic. Do not use in production.
    """
    def enforce_csrf(self, request):
        return  # Skips the CSRF check.