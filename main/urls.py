from django.urls import path
from django.contrib.auth import views as auth_views
from . import views


urlpatterns = [
    path('', views.home, name='home'),
    path('registro/', views.registro, name='registro'),
    path('login/', views.IniciarSesionView.as_view(), name='login'),
    path('logout/', views.cerrar_sesion, name='logout'),
    path('producto/<int:producto_id>/', views.detalle_producto, name='detalle_producto'),
    path('administrador/', views.panel_administrador, name='panel_administrador'),
    path('administracion/roles/',views.admin_gestionar_roles, name='admin_gestionar_roles'),
    path('perfil/', views.perfil, name='perfil'),
    
    # CRUD categorías
    path('administracion/categorias/', views.admin_categorias, name='admin_categorias'),
    path('administracion/categorias/nueva/', views.admin_categoria_crear, name='admin_categoria_crear'),
    path('administracion/categorias/<int:categoria_id>/editar/', views.admin_categoria_editar, name='admin_categoria_editar'),
    path('administracion/categorias/<int:categoria_id>/eliminar/', views.admin_categoria_eliminar, name='admin_categoria_eliminar'),

    # CRUD productos
    path('administracion/productos/', views.admin_productos, name='admin_productos'),
    path('administracion/productos/nuevo/', views.admin_producto_crear, name='admin_producto_crear'),
    path('administracion/productos/<int:producto_id>/editar/', views.admin_producto_editar, name='admin_producto_editar'),
    path('administracion/productos/<int:producto_id>/eliminar/', views.admin_producto_eliminar, name='admin_producto_eliminar'),
    
    # Carrito
    path('carrito/', views.ver_carrito, name='ver_carrito'),
    path('carrito/agregar/<int:producto_id>/', views.agregar_al_carrito, name='agregar_al_carrito'),
    path('carrito/item/<int:item_id>/actualizar/', views.actualizar_item_carrito, name='actualizar_item_carrito'),
    path('carrito/item/<int:item_id>/eliminar/', views.eliminar_item_carrito, name='eliminar_item_carrito'),
    path('carrito/solicitar/', views.solicitar_apartado, name='solicitar_apartado'),

    # Apartados
    path('administracion/apartados/', views.admin_apartados, name='admin_apartados'),
    path('administracion/apartados/<int:apartado_id>/estado/', views.admin_apartado_cambiar_estado, name='admin_apartado_cambiar_estado'),

    path('mis-apartados/', views.mis_apartados, name='mis_apartados'),
]