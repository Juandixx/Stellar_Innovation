from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.urls import reverse
from django.contrib.auth.models import User
from .models import Producto, Categoria, Usuario, Apartado
from .forms import RegistroForm, LoginForm
from django.contrib.auth import logout

def home(request):
    productos = Producto.objects.filter(
        activo=True, categoria__disponible=True
    ).order_by('-creado')
    categorias = Categoria.objects.filter(disponible=True)

    categoria_id = request.GET.get('categoria', '')
    q = request.GET.get('q', '').strip()

    categoria_activa = int(categoria_id) if categoria_id.isdigit() else None
    if categoria_activa:
        productos = productos.filter(categoria_id=categoria_activa)
    if q:
        productos = productos.filter(
            Q(nombre__icontains=q) | Q(marca__icontains=q) | Q(descripcion__icontains=q)
        )

    return render(request, 'main/home.html', {
        'productos': productos,
        'categorias': categorias,
        'categoria_activa': categoria_activa,
        'q': q,
    })


def detalle_producto(request, producto_id):
    producto = get_object_or_404(
        Producto, pk=producto_id, activo=True, categoria__disponible=True
    )
    return render(request, 'main/detalle_producto.html', {'producto': producto})


def registro(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = RegistroForm(request.POST)
        if form.is_valid():
            user = form.save()
            Usuario.objects.get_or_create(user=user)
            login( request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, '¡Cuenta creada con éxito! Ya iniciaste sesión.')
            return redirect('home')
    else:
        form = RegistroForm()

    return render(request, 'main/registro.html', {'form': form})


def cerrar_sesion(request):
    logout(request)
    messages.success(request, '¡Has cerrado sesión correctamente! Esperamos verte pronto.')
    return redirect('home')


class IniciarSesionView(LoginView):
    template_name = 'main/login.html'
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        usuario = form.get_user()
        nombre = usuario.first_name or usuario.username

        messages.success(
            self.request,
            f'¡Inicio de sesión exitoso! Bienvenido, {nombre}.'
        )

        return super().form_valid(form)

    def get_success_url(self):
        usuario = self.request.user
        perfil = getattr(usuario, 'usuario', None)

        if usuario.is_superuser or (
            perfil and perfil.rol == 'administrador'
        ):
            return reverse('panel_administrador')

        return reverse('home')



@login_required
def panel_administrador(request):

    perfil = getattr(request.user, 'usuario', None)

    # Comprobar permisos
    if not request.user.is_superuser and not (
        perfil and perfil.rol == 'administrador'
    ):
        messages.error(
            request,
            'No tienes permisos para acceder a esta sección.'
        )
        return redirect('home')

    contexto = {
        'productos_total': Producto.objects.count(),
        'productos_activos': Producto.objects.filter(activo=True).count(),
        'categorias_total': Categoria.objects.filter(disponible=True).count(),
        'clientes_total': Usuario.objects.filter(rol='cliente').count(),
        'apartados_pendientes': Apartado.objects.filter(
            estado='pendiente'
        ).count(),
        'apartados_recientes': Apartado.objects.select_related(
            'cliente'
        ).order_by('-fecha')[:5],
    }

    return render(
        request,
        'main/panel_administrador.html',
        contexto
    )



@login_required
def admin_gestionar_roles(request):

    perfil = getattr(request.user, 'usuario', None)

    # Comprobar permisos
    if not request.user.is_superuser and not (
        perfil and perfil.rol == 'administrador'
    ):
        messages.error(
            request,
            'No tienes permisos para acceder a esta sección.'
        )
        return redirect('home')

    # Obtener todos los usuarios y crear perfiles si no existen
    usuarios = User.objects.all().order_by('id')

    for usuario in usuarios:
        perfil, creado = Usuario.objects.get_or_create(user=usuario)

        # Los superusuarios también deben tener rol de administrador
        if usuario.is_superuser and perfil.rol != 'administrador':
            perfil.rol = 'administrador'
            perfil.save()

    # Cambiar el rol de un usuario
    if request.method == 'POST':

        usuario_id = request.POST.get('usuario_id')
        nuevo_rol = request.POST.get('rol')

        usuario_objetivo = get_object_or_404(User, id=usuario_id)

        # Evitar modificar el propio rol
        if usuario_objetivo == request.user:
            messages.error(request, 'No puedes modificar tu propio rol.')
            return redirect('admin_gestionar_roles')

        # Proteger superusuarios
        if usuario_objetivo.is_superuser:
            messages.error(request, 'No puedes modificar el rol de un superusuario.')
            return redirect('admin_gestionar_roles')

        # Validar el nuevo rol
        if nuevo_rol not in ['cliente', 'administrador']:
            messages.error(request, 'El rol seleccionado no es válido.')
            return redirect('admin_gestionar_roles')

        perfil_objetivo = usuario_objetivo.usuario
        perfil_objetivo.rol = nuevo_rol
        perfil_objetivo.save()

        messages.success(
            request,
            'El rol del usuario se actualizó correctamente.'
        )

        return redirect('admin_gestionar_roles')

    return render(request, 'main/admin_roles.html', {
        'usuarios': usuarios,
    })