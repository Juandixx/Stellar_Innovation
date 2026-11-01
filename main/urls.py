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
]