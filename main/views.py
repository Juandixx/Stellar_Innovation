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
from django.db import transaction
from django.db.models import F
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from .models import Carrito, ItemCarrito, DetalleApartado
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from .forms import PerfilForm
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


# PERFIL DE USUARIO

@login_required
def perfil(request):
    user = request.user
    perfil_usuario, _ = Usuario.objects.get_or_create(user=user)
    es_admin = user.is_superuser or perfil_usuario.rol == 'administrador'

    puede_cambiar_password = user.has_usable_password()

    form_datos = PerfilForm(user=user, perfil=perfil_usuario)
    form_password = PasswordChangeForm(user) if puede_cambiar_password else None

    if request.method == 'POST':
        accion = request.POST.get('accion')

        if accion == 'datos':
            form_datos = PerfilForm(request.POST, user=user, perfil=perfil_usuario)

            if form_datos.is_valid():
                form_datos.save()
                messages.success(request, 'La información ha sido actualizada.')
                return redirect('perfil')

        elif accion == 'password' and puede_cambiar_password:
            form_password = PasswordChangeForm(user, request.POST)

            if form_password.is_valid():
                user = form_password.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Tu contraseña ha sido actualizada.')
                return redirect('perfil')

    # Estadísticas personales de apartados
    apartados_usuario = Apartado.objects.filter(cliente=user)

    contexto = {
        'form_datos': form_datos,
        'form_password': form_password,
        'puede_cambiar_password': puede_cambiar_password,
        'perfil_usuario': perfil_usuario,
        'es_admin': es_admin,
        'total_apartados': apartados_usuario.count(),
        'pendientes': apartados_usuario.filter(estado='pendiente').count(),
    }

    return render(request, 'main/perfil.html', contexto)


# =========================
# MIS APARTADOS
# =========================

@login_required
def mis_apartados(request):
    perfil_usuario, _ = Usuario.objects.get_or_create(user=request.user)

    if request.user.is_superuser or perfil_usuario.rol == 'administrador':
        return redirect('panel_administrador')

    apartados = Apartado.objects.filter(
        cliente=request.user
    ).select_related(
        'cliente'
    ).prefetch_related(
        'detalles__producto'
    ).order_by('-fecha')

    return render(request, 'main/mis_apartados.html', {
        'apartados': apartados,
    })



def _es_administrador(user):
    perfil = getattr(user, 'usuario', None)

    return user.is_superuser or (
        perfil and perfil.rol == 'administrador'
    )

# CARRITO Y SOLICITUD DE APARTADO
class _StockCambio(Exception):
    """El stock cambió mientras se confirmaba el apartado."""


def _destino_seguro(request, defecto='home'):
    """Vuelve a la página desde donde se hizo la acción (solo rutas del propio sitio)."""
    destino = request.POST.get('next', '')
    if destino and url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
        return destino
    return defecto


def _leer_cantidad(request):
    try:
        return int(request.POST.get('cantidad', 1))
    except (TypeError, ValueError):
        return None


@require_POST
def agregar_al_carrito(request, producto_id):
    destino = _destino_seguro(request)

    if not request.user.is_authenticated:
        messages.info(request, 'Inicia sesión para agregar productos al carrito.')
        return redirect('login')

    if _es_administrador(request.user):
        messages.error(request, 'Los administradores no pueden agregar productos al carrito.')
        return redirect('home')

    producto = get_object_or_404(
        Producto, pk=producto_id, activo=True, categoria__disponible=True
    )

    cantidad = _leer_cantidad(request)

    if cantidad is None or cantidad < 1:
        messages.error(request, 'Ingresa una cantidad válida (mínimo 1).')
        return redirect(destino)

    carrito, _ = Carrito.objects.get_or_create(cliente=request.user)
    item = ItemCarrito.objects.filter(carrito=carrito, producto=producto).first()
    en_carrito = item.cantidad if item else 0

    if en_carrito + cantidad > producto.stock:
        disponibles = max(producto.stock - en_carrito, 0)

        if producto.stock == 0:
            messages.error(request, f'«{producto.nombre}» está agotado.')
        elif disponibles == 0:
            messages.error(request, f'Ya tienes en tu carrito las {producto.stock} unidades disponibles de «{producto.nombre}».')
        elif en_carrito:
            messages.error(
                request,
                f'Solo hay {producto.stock} unidades de «{producto.nombre}» y ya tienes '
                f'{en_carrito} en tu carrito. Puedes agregar {disponibles} más como máximo.'
            )
        else:
            messages.error(
                request,
                f'Solo hay {producto.stock} unidades disponibles de «{producto.nombre}». '
                f'La cantidad máxima es {producto.stock}.'
            )

        return redirect(destino)

    if item:
        item.cantidad = en_carrito + cantidad
        item.save(update_fields=['cantidad'])
    else:
        ItemCarrito.objects.create(carrito=carrito, producto=producto, cantidad=cantidad)

    messages.success(request, f'«{producto.nombre}» se agregó a tu carrito.')
    return redirect(destino)


@login_required
def ver_carrito(request):

    if _es_administrador(request.user):
        messages.error(request, 'Los administradores no tienen acceso al carrito.')
        return redirect('panel_administrador')

    carrito, _ = Carrito.objects.get_or_create(cliente=request.user)
    items = list(carrito.items.select_related('producto__categoria').order_by('id'))

    total = 0
    unidades = 0
    hay_problemas = False
    for item in items:
        p = item.producto
        item.no_disponible = (not p.activo) or (not p.categoria.disponible)
        item.excede = (not item.no_disponible) and item.cantidad > p.stock
        if item.no_disponible or item.excede:
            hay_problemas = True
        total += item.subtotal
        unidades += item.cantidad

    return render(request, 'main/carrito.html', {
        'items': items,
        'total': total,
        'unidades': unidades,
        'hay_problemas': hay_problemas,
    })


@login_required
@require_POST
def actualizar_item_carrito(request, item_id):

    if _es_administrador(request.user):
        messages.error(request, 'Los administradores no pueden modificar el carrito.')
        return redirect('panel_administrador')
    
    item = get_object_or_404(
        ItemCarrito.objects.select_related('producto'),
        pk=item_id, carrito__cliente=request.user
    )
    producto = item.producto
    cantidad = _leer_cantidad(request)

    if cantidad is None or cantidad < 1:
        messages.error(request, 'La cantidad mínima es 1. Si ya no lo quieres, usa «Quitar».')
    elif producto.stock == 0:
        messages.error(request, f'«{producto.nombre}» está agotado. Quítalo del carrito.')
    elif cantidad > producto.stock:
        messages.error(
            request,
            f'Solo hay {producto.stock} unidades disponibles de «{producto.nombre}». '
            f'La cantidad máxima es {producto.stock}.'
        )
    else:
        item.cantidad = cantidad
        item.save(update_fields=['cantidad'])
        messages.success(request, f'Cantidad de «{producto.nombre}» actualizada a {cantidad}.')

    return redirect('ver_carrito')


@login_required
@require_POST
def eliminar_item_carrito(request, item_id):

    if _es_administrador(request.user):
        messages.error(request, 'Los administradores no pueden modificar el carrito.')
        return redirect('panel_administrador')
    
    item = get_object_or_404(
        ItemCarrito.objects.select_related('producto'),
        pk=item_id, carrito__cliente=request.user
    )
    nombre = item.producto.nombre
    item.delete()
    messages.success(request, f'«{nombre}» se quitó del carrito.')
    return redirect('ver_carrito')


@login_required
@require_POST
def solicitar_apartado(request):

    if _es_administrador(request.user):
        messages.error(request, 'Los administradores no pueden solicitar apartados.')
        return redirect('panel_administrador')
    
    """CU7: verifica el stock de nuevo, registra el apartado y reserva las unidades."""
    carrito = Carrito.objects.filter(cliente=request.user).first()
    items = list(carrito.items.all()) if carrito else []

    if not items:
        messages.error(request, 'Tu carrito está vacío. Agrega productos antes de solicitar el apartado.')
        return redirect('ver_carrito')

    try:
        with transaction.atomic():
            ids = [i.producto_id for i in items]
            productos = {
                p.pk: p for p in Producto.objects.select_for_update().filter(pk__in=ids)
            }

            problemas = []
            for item in items:
                p = productos[item.producto_id]
                if not p.activo or not p.categoria.disponible:
                    problemas.append(f'«{p.nombre}» ya no está disponible. Quítalo del carrito.')
                elif p.stock == 0:
                    problemas.append(f'«{p.nombre}» se agotó. Quítalo del carrito.')
                elif item.cantidad > p.stock:
                    problemas.append(
                        f'«{p.nombre}»: solo quedan {p.stock} unidades y pediste {item.cantidad}. '
                        f'Ajusta la cantidad.'
                    )

            if problemas:
                for texto in problemas:
                    messages.error(request, texto)
                return redirect('ver_carrito')

            apartado = Apartado.objects.create(cliente=request.user)
            for item in items:
                p = productos[item.producto_id]
                # Descuenta el stock (queda reservado para el cliente)
                actualizado = Producto.objects.filter(
                    pk=p.pk, stock__gte=item.cantidad
                ).update(stock=F('stock') - item.cantidad)
                if actualizado != 1:
                    raise _StockCambio(p.nombre)
                DetalleApartado.objects.create(
                    apartado=apartado,
                    producto=p,
                    cantidad=item.cantidad,
                    precio_unitario=p.precio,   # precio al momento de apartar
                )

            carrito.items.all().delete()

    except _StockCambio as error:
        messages.error(
            request,
            f'El stock de «{error}» cambió mientras confirmabas. Revisa tu carrito e inténtalo de nuevo.'
        )
        return redirect('ver_carrito')

    messages.success(
        request,
        f'Tu solicitud de apartado #{apartado.pk} quedó registrada. '
        f'Las unidades están reservadas para que las recojas en la tienda.'
    )
    return redirect(reverse('mis_apartados'))


# =========================
# GESTIÓN DE APARTADOS
# =========================

@admin_required
def admin_apartados(request):
    apartados = Apartado.objects.select_related(
        'cliente'
    ).prefetch_related(
        'detalles__producto'
    ).order_by('-fecha')

    paginator = Paginator(apartados, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    contexto = {
        'apartados': page_obj,
        'page_obj': page_obj,
    }

    return render(request, 'main/admin_apartados.html', contexto)


@admin_required
@require_POST
def admin_apartado_cambiar_estado(request, apartado_id):
    apartado = get_object_or_404(Apartado, id=apartado_id)

    nuevo_estado = request.POST.get('estado')

    if apartado.estado != 'pendiente':
        messages.error(
            request,
            'Solo se pueden modificar apartados pendientes.'
        )
        return redirect('admin_apartados')

    if nuevo_estado == 'cancelada':
        apartado.cancelar()

        messages.success(
            request,
            f'El apartado #{apartado.id} fue cancelado y el stock fue devuelto.'
        )

    elif nuevo_estado == 'entregada':
        apartado.estado = 'entregada'
        apartado.save(update_fields=['estado'])

        messages.success(
            request,
            f'El apartado #{apartado.id} fue marcado como entregado.'
        )

    else:
        messages.error(request, 'El estado seleccionado no es válido.')

    return redirect('admin_apartados')