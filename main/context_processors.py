from django.db.models import Sum

from .models import ItemCarrito, Apartado


def carrito(request):
    """Contadores del carrito y de apartados listos para entregar."""

    cantidad = 0
    apartados_listos = 0

    if request.user.is_authenticated:
        cantidad = ItemCarrito.objects.filter(
            carrito__cliente=request.user
        ).aggregate(total=Sum('cantidad'))['total'] or 0

        perfil_usuario = getattr(request.user, 'usuario', None)

        if perfil_usuario and perfil_usuario.rol == 'cliente':
            apartados_listos = Apartado.objects.filter(
                cliente=request.user,
                estado='listo_para_entregar'
            ).count()

    return {
        'carrito_cantidad': cantidad,
        'apartados_listos': apartados_listos,
    }