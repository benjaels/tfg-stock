from django.shortcuts import redirect
from django.urls import reverse
from .models import UsuarioPerfil


class PasswordChangeRequiredMiddleware:
    """
    Si el usuario tiene must_change_password, se fuerza a ir a password_change.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            perfil, _ = UsuarioPerfil.objects.get_or_create(user=request.user, defaults={"must_change_password": False})

            allowed_paths = {
                reverse("forzar_cambio_clave"),
                reverse("logout"),
            }
            if perfil.must_change_password and request.path not in allowed_paths:
                return redirect("forzar_cambio_clave")

        response = self.get_response(request)
        return response
