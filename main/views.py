from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.urls import reverse
from django.contrib.auth.models import User
from .models import Producto, Categoria, Usuario, Apartado, DetalleApartado
from .forms import RegistroForm, LoginForm, CategoriaForm, ProductoForm
from .decorators import admin_required
from django.contrib.auth import logout
from django.core.files.storage import default_storage
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST

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

#CRUD DE CATEGORIAS
@admin_required
def admin_categorias(request):
    categorias = Categoria.objects.annotate(num_productos=Count('productos'))

    q = request.GET.get('q', '').strip()
    if q:
        categorias = categorias.filter(Q(nombre__icontains=q) | Q(descripcion__icontains=q))

    return render(request, 'main/admin_categorias.html', {
        'categorias': categorias,
        'q': q,
    })

@admin_required
def admin_categoria_crear(request):
    if request.method == 'POST':
        form = CategoriaForm(request.POST)
        if form.is_valid():
            categoria = form.save()
            messages.success(request, f'La categoría «{categoria.nombre}» se creó correctamente.')
            return redirect('admin_categorias')
    else:
        form = CategoriaForm(initial={'disponible': True})

    return render(request, 'main/admin_categoria_form.html', {
        'form': form,
        'titulo': 'Nueva categoría',
        'categoria': None,
    })

@admin_required
def admin_categoria_editar(request, categoria_id):
    categoria = get_object_or_404(Categoria, pk=categoria_id)

    if request.method == 'POST':
        form = CategoriaForm(request.POST, instance=categoria)
        if form.is_valid():
            categoria = form.save()
            messages.success(request, f'La categoría «{categoria.nombre}» se actualizó correctamente.')
            return redirect('admin_categorias')
    else:
        form = CategoriaForm(instance=categoria)

    return render(request, 'main/admin_categoria_form.html', {
        'form': form,
        'titulo': 'Editar categoría',
        'categoria': categoria,
    })


@admin_required
@require_POST
def admin_categoria_eliminar(request, categoria_id):
    """Una categoría con productos NO se elimina, se marca como no disponible."""
    categoria = get_object_or_404(Categoria, pk=categoria_id)

    if categoria.productos.exists():
        categoria.disponible = False
        categoria.save(update_fields=['disponible'])
        messages.warning(
            request,
            f'La categoría «{categoria.nombre}» tiene productos asociados, por eso no se '
            f'eliminó: se marcó como no disponible y ya no aparece en el catálogo.'
        )
    else:
        nombre = categoria.nombre
        categoria.delete()
        messages.success(request, f'La categoría «{nombre}» se eliminó correctamente.')

    return redirect('admin_categorias')

#CRUD DE PRODUCTOS
def _borrar_archivo(nombre_archivo):
    """Borra una imagen del disco sin romper si ya no existe."""
    if nombre_archivo:
        try:
            default_storage.delete(nombre_archivo)
        except Exception:
            pass

@admin_required
def admin_productos(request):
    productos = Producto.objects.select_related('categoria')

    q = request.GET.get('q', '').strip()
    categoria_id = request.GET.get('categoria', '')
    estado = request.GET.get('estado', '')

    if q:
        productos = productos.filter(Q(nombre__icontains=q) | Q(marca__icontains=q))

    categoria_activa = int(categoria_id) if categoria_id.isdigit() else None
    if categoria_activa:
        productos = productos.filter(categoria_id=categoria_activa)

    if estado == 'activos':
        productos = productos.filter(activo=True)
    elif estado == 'inactivos':
        productos = productos.filter(activo=False)
    elif estado == 'agotados':
        productos = productos.filter(stock=0)

    page_obj = Paginator(productos, 10).get_page(request.GET.get('page'))

    # Para que la paginación conserve los filtros
    params = request.GET.copy()
    params.pop('page', None)

    return render(request, 'main/admin_productos.html', {
        'page_obj': page_obj,
        'categorias': Categoria.objects.all(),
        'categoria_activa': categoria_activa,
        'estado': estado,
        'q': q,
        'querystring': params.urlencode(),
    })

@admin_required
def admin_producto_crear(request):
    if not Categoria.objects.filter(disponible=True).exists():
        messages.error(request, 'Primero debes crear al menos una categoría disponible.')
        return redirect('admin_categoria_crear')

    if request.method == 'POST':
        form = ProductoForm(request.POST, request.FILES)
        if form.is_valid():
            producto = form.save()
            messages.success(request, f'El producto «{producto.nombre}» se creó correctamente.')
            return redirect('admin_productos')
    else:
        form = ProductoForm(initial={'activo': True, 'stock': 0})

    return render(request, 'main/admin_producto_form.html', {
        'form': form,
        'titulo': 'Nuevo producto',
        'producto': None,
    })

@admin_required
def admin_producto_editar(request, producto_id):
    producto = get_object_or_404(Producto, pk=producto_id)
    imagen_anterior = producto.imagen.name if producto.imagen else None

    if request.method == 'POST':
        form = ProductoForm(request.POST, request.FILES, instance=producto)
        if form.is_valid():
            producto = form.save()

            # Si cambió o se quitó la imagen, borrar la vieja del disco
            imagen_nueva = producto.imagen.name if producto.imagen else None
            if imagen_anterior and imagen_anterior != imagen_nueva:
                _borrar_archivo(imagen_anterior)

            messages.success(request, f'El producto «{producto.nombre}» se actualizó correctamente.')
            return redirect('admin_productos')
    else:
        form = ProductoForm(instance=producto)

    return render(request, 'main/admin_producto_form.html', {
        'form': form,
        'titulo': 'Editar producto',
        'producto': producto,
    })

@admin_required
@require_POST
def admin_producto_eliminar(request, producto_id):
    """Un producto con apartados asociados NO se elimina, se marca como inactivo.

    - Con apartados pendientes -> inactivo.
    - Con apartados históricos -> inactivo (se conserva el historial del cliente).
    - Sin ningún apartado      -> se elimina de verdad.
    """
    producto = get_object_or_404(Producto, pk=producto_id)
    detalles = DetalleApartado.objects.filter(producto=producto)

    if detalles.filter(apartado__estado='pendiente').exists():
        producto.activo = False
        producto.save(update_fields=['activo'])
        messages.warning(
            request,
            f'«{producto.nombre}» tiene apartados pendientes, por eso no se eliminó: '
            f'se marcó como inactivo y ya no aparece en el catálogo.'
        )
    elif detalles.exists():
        producto.activo = False
        producto.save(update_fields=['activo'])
        messages.warning(
            request,
            f'«{producto.nombre}» aparece en el historial de apartados de los clientes, '
            f'por eso no se eliminó: se marcó como inactivo.'
        )
    else:
        nombre = producto.nombre
        imagen = producto.imagen.name if producto.imagen else None
        producto.delete()
        _borrar_archivo(imagen)
        messages.success(request, f'El producto «{nombre}» se eliminó correctamente.')

    return redirect('admin_productos')