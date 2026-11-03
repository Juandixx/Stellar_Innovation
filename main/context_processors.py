from django.db.models import Sum

from .models import ItemCarrito


def carrito(request):
    """Cantidad de unidades en el carrito, para el contador del header."""
    cantidad = 0
    if request.user.is_authenticated:
        cantidad = ItemCarrito.objects.filter(
            carrito__cliente=request.user
        ).aggregate(total=Sum('cantidad'))['total'] or 0
    return {'carrito_cantidad': cantidad}