from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.urls import reverse
from allauth.account.adapter import DefaultAccountAdapter

from .models import Usuario


class SocialAdapter(DefaultSocialAccountAdapter):

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)

        email = (data.get('email') or '').strip().lower()

        if email:
            user.email = email
            user.username = email

        return user

    def pre_social_login(self, request, sociallogin):

        if sociallogin.user.pk:
            Usuario.objects.get_or_create(
                user=sociallogin.user,
                defaults={'rol': 'cliente'}
            )

    def save_user(self, request, sociallogin, form=None):

        user = super().save_user(request, sociallogin, form)

        Usuario.objects.get_or_create(
            user=user,
            defaults={'rol': 'cliente'}
        )

        return user

    def get_login_redirect_url(self, request):

        usuario = request.user
        perfil = getattr(usuario, 'usuario', None)

        if usuario.is_superuser or (
            perfil and perfil.rol == 'administrador'
        ):
            return reverse('panel_administrador')

        return reverse('home')


class AccountAdapter(DefaultAccountAdapter):

    def get_login_redirect_url(self, request):
        usuario = request.user
        perfil = getattr(usuario, 'usuario', None)

        if usuario.is_superuser or (
            perfil and perfil.rol == 'administrador'
        ):
            return reverse('panel_administrador')

        return reverse('home')