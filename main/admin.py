from django.contrib import admin
from .models import (
    Usuario,
    Categoria, 
    Producto,
    Carrito, 
    ItemCarrito, 
    Apartado, 
    DetalleApartado,
)

admin.site.register(Usuario)
admin.site.register(Categoria)
admin.site.register(Carrito)
admin.site.register(ItemCarrito)
admin.site.register(DetalleApartado)


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'marca', 'categoria', 'precio', 'stock', 'activo')
    list_filter = ('categoria', 'activo')
    search_fields = ('nombre', 'marca')


@admin.register(Apartado)
class ApartadoAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'estado', 'fecha')
    list_filter = ('estado',)
