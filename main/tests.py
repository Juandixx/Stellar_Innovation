"""Pruebas unitarias y funcionales de Stellar Innovation.
Ejecutar con:  python manage.py test main -v 2
"""
import time
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from .decorators import es_administrador
from .forms import CategoriaForm, PerfilForm, ProductoForm, RegistroForm
from .models import (Apartado, Carrito, Categoria, DetalleApartado,
                     ItemCarrito, Producto, Usuario)
from .views import cancelar_apartados_vencidos


def crear_usuario(correo, rol='cliente', password='Clave-Segura-123', **extra):
    user = User.objects.create_user(username=correo, email=correo, password=password,
                                    first_name='Test', **extra)
    Usuario.objects.create(user=user, rol=rol)
    return user


def crear_producto(nombre='Portátil X', stock=5, precio='2500000', cat=None, **extra):
    cat = cat or Categoria.objects.get_or_create(nombre='Portátiles')[0]
    return Producto.objects.create(nombre=nombre, descripcion='Descripción', precio=Decimal(precio),
                                   stock=stock, categoria=cat, **extra)


# ---------------------------------------------------------------- UNITARIAS: MODELOS
class ProductoModeloTests(TestCase):
    def test_PU01_stock_negativo_no_se_guarda(self):
        p = crear_producto(stock=2)
        p.stock = -1
        with self.assertRaises(IntegrityError), transaction.atomic():
            p.save()

    def test_PU02_precio_negativo_es_invalido(self):
        p = Producto(nombre='X', descripcion='d', precio=Decimal('-1'), stock=1,
                     categoria=Categoria.objects.create(nombre='C'))
        with self.assertRaises(ValidationError):
            p.full_clean()

    def test_PU03_categoria_con_productos_esta_protegida(self):
        p = crear_producto()
        from django.db.models import ProtectedError
        with self.assertRaises(ProtectedError):
            p.categoria.delete()


class CarritoModeloTests(TestCase):
    def setUp(self):
        self.user = crear_usuario('c@test.com')
        self.carrito = Carrito.objects.create(cliente=self.user)

    def test_PU04_subtotal_y_total(self):
        a = crear_producto('A', precio='1000'); b = crear_producto('B', precio='500')
        ItemCarrito.objects.create(carrito=self.carrito, producto=a, cantidad=3)
        ItemCarrito.objects.create(carrito=self.carrito, producto=b, cantidad=2)
        self.assertEqual(self.carrito.total, Decimal('4000'))

    def test_PU05_item_repetido_en_carrito_no_se_permite(self):
        a = crear_producto('A')
        ItemCarrito.objects.create(carrito=self.carrito, producto=a, cantidad=1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ItemCarrito.objects.create(carrito=self.carrito, producto=a, cantidad=1)

    def test_PU06_cantidad_cero_es_invalida(self):
        item = ItemCarrito(carrito=self.carrito, producto=crear_producto(), cantidad=0)
        with self.assertRaises(ValidationError):
            item.full_clean()


class ApartadoModeloTests(TestCase):
    def setUp(self):
        self.user = crear_usuario('c@test.com')
        self.p = crear_producto(stock=5)
        self.apartado = Apartado.objects.create(cliente=self.user)
        DetalleApartado.objects.create(apartado=self.apartado, producto=self.p, cantidad=2,
                                       precio_unitario=self.p.precio)
        Producto.objects.filter(pk=self.p.pk).update(stock=3)   # 2 unidades reservadas

    def test_PU07_cancelar_pendiente_repone_stock(self):
        self.assertTrue(self.apartado.cancelar())
        self.p.refresh_from_db(); self.apartado.refresh_from_db()
        self.assertEqual(self.p.stock, 5)
        self.assertEqual(self.apartado.estado, 'cancelada')

    def test_PU08_cancelar_entregado_no_se_permite(self):
        self.apartado.estado = 'entregada'; self.apartado.save()
        self.assertFalse(self.apartado.cancelar())
        self.p.refresh_from_db()
        self.assertEqual(self.p.stock, 3)

    def test_PU09_cancelar_dos_veces_no_repone_dos_veces(self):
        self.apartado.cancelar(); self.apartado.cancelar()
        self.p.refresh_from_db()
        self.assertEqual(self.p.stock, 5)

    def test_PU10_total_usa_precio_al_apartar(self):
        self.p.precio = Decimal('9999999'); self.p.save()
        self.assertEqual(self.apartado.total, Decimal('5000000'))

    def test_PU11_vencidos_se_cancelan_y_reponen(self):
        self.apartado.estado = 'listo_para_entregar'
        self.apartado.fecha_limite_recogida = timezone.now() - timedelta(hours=1)
        self.apartado.save()
        cancelar_apartados_vencidos()
        self.apartado.refresh_from_db(); self.p.refresh_from_db()
        self.assertEqual(self.apartado.estado, 'cancelada')
        self.assertEqual(self.p.stock, 5)


class RolesTests(TestCase):
    def test_PU12_es_administrador(self):
        self.assertTrue(es_administrador(crear_usuario('a@test.com', 'administrador')))
        self.assertFalse(es_administrador(crear_usuario('c@test.com', 'cliente')))
        su = User.objects.create_superuser('root', 'root@test.com', 'x')
        self.assertTrue(es_administrador(su))


# ---------------------------------------------------------------- UNITARIAS: FORMULARIOS
class FormulariosTests(TestCase):
    DATOS = dict(first_name='Ana', last_name='Pérez', email='Ana@Test.com',
                 password1='Clave-Segura-123', password2='Clave-Segura-123')

    def test_PU13_registro_valido_normaliza_correo(self):
        f = RegistroForm(self.DATOS); self.assertTrue(f.is_valid())
        self.assertEqual(f.save().email, 'ana@test.com')

    def test_PU14_registro_correo_duplicado(self):
        crear_usuario('ana@test.com')
        self.assertIn('email', RegistroForm(self.DATOS).errors)

    def test_PU15_registro_contrasenas_distintas(self):
        d = dict(self.DATOS, password2='otra-clave-123')
        self.assertIn('password2', RegistroForm(d).errors)

    def test_PU16_registro_campos_obligatorios(self):
        self.assertFalse(RegistroForm({}).is_valid())

    def test_PU17_categoria_duplicada_sin_importar_mayusculas(self):
        Categoria.objects.create(nombre='Portatiles')
        self.assertIn('nombre', CategoriaForm({'nombre': 'PORTATILES', 'disponible': True}).errors)

    def test_PU18_producto_stock_y_precio_negativos(self):
        c = Categoria.objects.create(nombre='C')
        f = ProductoForm({'nombre': 'P', 'categoria': c.pk, 'precio': '-5', 'stock': '-1',
                          'descripcion': 'd'})
        self.assertFalse(f.is_valid())
        self.assertIn('stock', f.errors); self.assertIn('precio', f.errors)

    def test_PU19_producto_no_permite_categoria_no_disponible(self):
        c = Categoria.objects.create(nombre='Oculta', disponible=False)
        f = ProductoForm({'nombre': 'P', 'categoria': c.pk, 'precio': '1', 'stock': '1',
                          'descripcion': 'd'})
        self.assertIn('categoria', f.errors)

    def test_PU20_perfil_correo_en_uso(self):
        crear_usuario('otro@test.com'); u = crear_usuario('yo@test.com')
        f = PerfilForm({'first_name': 'Yo', 'email': 'otro@test.com'}, user=u, perfil=u.usuario)
        self.assertIn('email', f.errors)

    def test_PU21_perfil_telefono_invalido(self):
        u = crear_usuario('yo@test.com')
        f = PerfilForm({'first_name': 'Yo', 'email': 'yo@test.com', 'telefono': 'abc'},
                       user=u, perfil=u.usuario)
        self.assertIn('telefono', f.errors)


# ---------------------------------------------------------------- FUNCIONALES (caja negra)
class AutenticacionFuncionalTests(TestCase):
    def test_PF01_registro_exitoso_crea_cuenta_y_sesion(self):
        r = self.client.post(reverse('registro'), dict(
            first_name='Ana', last_name='P', email='ana@test.com',
            password1='Clave-Segura-123', password2='Clave-Segura-123'), follow=True)
        self.assertTrue(User.objects.filter(email='ana@test.com').exists())
        self.assertTrue(r.context['user'].is_authenticated)
        self.assertEqual(User.objects.get(email='ana@test.com').usuario.rol, 'cliente')

    def test_PF02_registro_correo_repetido_muestra_error(self):
        crear_usuario('ana@test.com')
        r = self.client.post(reverse('registro'), dict(first_name='A', last_name='B', email='ana@test.com',
                             password1='Clave-Segura-123', password2='Clave-Segura-123'))
        self.assertContains(r, 'Ya existe una cuenta con este correo.')

    def test_PF03_login_cliente_va_al_catalogo(self):
        crear_usuario('c@test.com')
        r = self.client.post(reverse('login'), {'username': 'c@test.com', 'password': 'Clave-Segura-123'})
        self.assertRedirects(r, reverse('home'))

    def test_PF04_login_administrador_va_al_panel(self):
        crear_usuario('a@test.com', 'administrador')
        r = self.client.post(reverse('login'), {'username': 'a@test.com', 'password': 'Clave-Segura-123'})
        self.assertRedirects(r, reverse('panel_administrador'))

    def test_PF05_login_incorrecto_mensaje_generico(self):
        crear_usuario('c@test.com')
        r = self.client.post(reverse('login'), {'username': 'c@test.com', 'password': 'mala'})
        self.assertContains(r, 'Correo o contraseña incorrectos.')

    def test_PF06_contrasena_guardada_con_hash(self):
        u = crear_usuario('c@test.com')
        self.assertNotEqual(u.password, 'Clave-Segura-123')
        self.assertTrue(u.password.startswith('pbkdf2_sha256$'))

    def test_PF07_logout(self):
        crear_usuario('c@test.com'); self.client.login(username='c@test.com', password='Clave-Segura-123')
        r = self.client.get(reverse('logout'), follow=True)
        self.assertFalse(r.context['user'].is_authenticated)


class ControlAccesoTests(TestCase):
    RUTAS_ADMIN = ['panel_administrador', 'admin_categorias', 'admin_productos', 'admin_apartados',
                   'admin_gestionar_roles', 'admin_producto_crear', 'admin_categoria_crear']

    def test_PF08_cliente_no_entra_a_rutas_de_administracion(self):
        u = crear_usuario('c@test.com'); self.client.force_login(u)
        for nombre in self.RUTAS_ADMIN:
            r = self.client.get(reverse(nombre))
            self.assertRedirects(r, reverse('home'), msg_prefix=nombre, fetch_redirect_response=False)

    def test_PF09_visitante_es_enviado_a_iniciar_sesion(self):
        for nombre in self.RUTAS_ADMIN + ['ver_carrito', 'perfil', 'mis_apartados']:
            r = self.client.get(reverse(nombre))
            self.assertEqual(r.status_code, 302, nombre)
            self.assertIn('login', r['Location'], nombre)

    def test_PF10_administrador_accede_al_panel(self):
        self.client.force_login(crear_usuario('a@test.com', 'administrador'))
        self.assertEqual(self.client.get(reverse('panel_administrador')).status_code, 200)

    def test_PF11_cliente_no_puede_eliminar_producto_por_post(self):
        p = crear_producto(); self.client.force_login(crear_usuario('c@test.com'))
        self.client.post(reverse('admin_producto_eliminar', args=[p.pk]))
        self.assertTrue(Producto.objects.filter(pk=p.pk).exists())

    def test_PF12_admin_no_cambia_su_propio_rol(self):
        a = crear_usuario('a@test.com', 'administrador'); self.client.force_login(a)
        self.client.post(reverse('admin_gestionar_roles'), {'usuario_id': a.pk, 'rol': 'cliente'})
        a.usuario.refresh_from_db(); self.assertEqual(a.usuario.rol, 'administrador')

    def test_PF13_admin_cambia_rol_de_otro_usuario(self):
        self.client.force_login(crear_usuario('a@test.com', 'administrador'))
        c = crear_usuario('c@test.com')
        self.client.post(reverse('admin_gestionar_roles'), {'usuario_id': c.pk, 'rol': 'administrador'})
        c.usuario.refresh_from_db(); self.assertEqual(c.usuario.rol, 'administrador')


class CatalogoFuncionalTests(TestCase):
    def setUp(self):
        self.lap = Categoria.objects.create(nombre='Portátiles'); self.cel = Categoria.objects.create(nombre='Celulares')
        crear_producto('Lenovo IdeaPad', cat=self.lap, marca='Lenovo')
        crear_producto('Galaxy A15', cat=self.cel, marca='Samsung')
        crear_producto('Oculto', cat=self.lap, activo=False)

    def test_PF14_catalogo_muestra_solo_productos_activos(self):
        r = self.client.get(reverse('home'))
        nombres = [p.nombre for p in r.context['productos']]
        self.assertEqual(sorted(nombres), ['Galaxy A15', 'Lenovo IdeaPad'])

    def test_PF15_filtro_por_categoria(self):
        r = self.client.get(reverse('home'), {'categoria': self.cel.pk})
        self.assertEqual([p.nombre for p in r.context['productos']], ['Galaxy A15'])

    def test_PF16_busqueda_por_texto_y_marca(self):
        r = self.client.get(reverse('home'), {'q': 'samsung'})
        self.assertEqual([p.nombre for p in r.context['productos']], ['Galaxy A15'])

    def test_PF17_sin_resultados(self):
        r = self.client.get(reverse('home'), {'q': 'zzzz'})
        self.assertEqual(len(r.context['productos']), 0)

    def test_PF18_categoria_no_disponible_oculta_productos(self):
        self.cel.disponible = False; self.cel.save()
        r = self.client.get(reverse('home'))
        self.assertEqual([p.nombre for p in r.context['productos']], ['Lenovo IdeaPad'])

    def test_PF19_detalle_de_producto(self):
        p = Producto.objects.get(nombre='Galaxy A15')
        r = self.client.get(reverse('detalle_producto', args=[p.pk]))
        self.assertContains(r, 'Galaxy A15')

    def test_PF20_detalle_de_producto_inactivo_da_404(self):
        p = Producto.objects.get(nombre='Oculto')
        self.assertEqual(self.client.get(reverse('detalle_producto', args=[p.pk])).status_code, 404)


class CarritoYApartadoFuncionalTests(TestCase):
    def setUp(self):
        self.user = crear_usuario('c@test.com'); self.client.force_login(self.user)
        self.p = crear_producto(stock=3, precio='1000')

    def agregar(self, cantidad, producto=None):
        p = producto or self.p
        return self.client.post(reverse('agregar_al_carrito', args=[p.pk]), {'cantidad': cantidad})

    def test_PF21_agregar_al_carrito(self):
        self.agregar(2)
        self.assertEqual(ItemCarrito.objects.get().cantidad, 2)

    def test_PF22_agregar_mismo_producto_acumula(self):
        self.agregar(1); self.agregar(1)
        self.assertEqual(ItemCarrito.objects.get().cantidad, 2)

    def test_PF23_no_permite_superar_stock(self):
        self.agregar(4)
        self.assertFalse(ItemCarrito.objects.exists())

    def test_PF24_no_permite_superar_stock_acumulado(self):
        self.agregar(2); self.agregar(2)
        self.assertEqual(ItemCarrito.objects.get().cantidad, 2)

    def test_PF25_cantidad_invalida(self):
        self.agregar(0); self.agregar('abc')
        self.assertFalse(ItemCarrito.objects.exists())

    def test_PF26_visitante_debe_iniciar_sesion_para_agregar(self):
        self.client.logout()
        r = self.agregar(1)
        self.assertRedirects(r, reverse('login'), fetch_redirect_response=False)

    def test_PF27_modificar_y_eliminar_item(self):
        self.agregar(1); item = ItemCarrito.objects.get()
        self.client.post(reverse('actualizar_item_carrito', args=[item.pk]), {'cantidad': 3})
        item.refresh_from_db(); self.assertEqual(item.cantidad, 3)
        self.client.post(reverse('actualizar_item_carrito', args=[item.pk]), {'cantidad': 9})
        item.refresh_from_db(); self.assertEqual(item.cantidad, 3)
        self.client.post(reverse('eliminar_item_carrito', args=[item.pk]))
        self.assertFalse(ItemCarrito.objects.exists())

    def test_PF28_no_puede_tocar_el_carrito_de_otro(self):
        otro = crear_usuario('o@test.com'); c = Carrito.objects.create(cliente=otro)
        item = ItemCarrito.objects.create(carrito=c, producto=self.p, cantidad=1)
        r = self.client.post(reverse('eliminar_item_carrito', args=[item.pk]))
        self.assertEqual(r.status_code, 404); self.assertTrue(ItemCarrito.objects.filter(pk=item.pk).exists())

    def test_PF29_administrador_no_usa_carrito(self):
        self.client.force_login(crear_usuario('a@test.com', 'administrador'))
        self.agregar(1); self.assertFalse(ItemCarrito.objects.exists())

    def test_PF30_solicitar_apartado_descuenta_stock_y_vacia_carrito(self):
        self.agregar(2)
        r = self.client.post(reverse('solicitar_apartado'))
        self.assertRedirects(r, reverse('mis_apartados'))
        self.p.refresh_from_db(); ap = Apartado.objects.get()
        self.assertEqual(self.p.stock, 1); self.assertEqual(ap.estado, 'pendiente')
        self.assertEqual(ap.total, Decimal('2000')); self.assertFalse(ItemCarrito.objects.exists())

    def test_PF31_carrito_vacio_no_genera_apartado(self):
        self.client.post(reverse('solicitar_apartado'))
        self.assertFalse(Apartado.objects.exists())

    def test_PF32_stock_agotado_antes_de_confirmar(self):
        self.agregar(3)
        Producto.objects.filter(pk=self.p.pk).update(stock=1)   # otro cliente apartó
        self.client.post(reverse('solicitar_apartado'))
        self.assertFalse(Apartado.objects.exists())
        self.p.refresh_from_db(); self.assertEqual(self.p.stock, 1)

    def test_PF33_apartado_multiple_es_atomico(self):
        q = crear_producto('Otro', stock=5)
        self.agregar(1); self.agregar(2, q)
        Producto.objects.filter(pk=q.pk).update(stock=0)
        self.client.post(reverse('solicitar_apartado'))
        self.assertFalse(Apartado.objects.exists())
        self.p.refresh_from_db(); self.assertEqual(self.p.stock, 3)

    def test_PF34_producto_desactivado_bloquea_apartado(self):
        self.agregar(1); Producto.objects.filter(pk=self.p.pk).update(activo=False)
        self.client.post(reverse('solicitar_apartado'))
        self.assertFalse(Apartado.objects.exists())

    def test_PF35_historial_muestra_solo_mis_apartados(self):
        otro = crear_usuario('o@test.com'); Apartado.objects.create(cliente=otro)
        Apartado.objects.create(cliente=self.user)
        r = self.client.get(reverse('mis_apartados'))
        self.assertEqual(len(r.context['apartados']), 1)

    def test_PF36_cliente_cancela_su_apartado_y_repone_stock(self):
        self.agregar(2); self.client.post(reverse('solicitar_apartado'))
        ap = Apartado.objects.get()
        self.client.post(reverse('cancelar_mi_apartado', args=[ap.pk]))
        self.p.refresh_from_db(); ap.refresh_from_db()
        self.assertEqual(ap.estado, 'cancelada'); self.assertEqual(self.p.stock, 3)

    def test_PF37_cliente_no_cancela_apartado_ajeno(self):
        otro = crear_usuario('o@test.com'); ap = Apartado.objects.create(cliente=otro)
        r = self.client.post(reverse('cancelar_mi_apartado', args=[ap.pk]))
        self.assertEqual(r.status_code, 404)


class AdministracionFuncionalTests(TestCase):
    def setUp(self):
        self.admin = crear_usuario('a@test.com', 'administrador'); self.client.force_login(self.admin)
        self.cat = Categoria.objects.create(nombre='Portátiles')

    def test_PF38_crear_categoria(self):
        self.client.post(reverse('admin_categoria_crear'), {'nombre': 'Celulares', 'disponible': 'on'})
        self.assertTrue(Categoria.objects.filter(nombre='Celulares').exists())

    def test_PF39_categoria_duplicada_se_rechaza(self):
        r = self.client.post(reverse('admin_categoria_crear'), {'nombre': 'portátiles', 'disponible': 'on'})
        self.assertContains(r, 'Ya existe una categoría con ese nombre.')

    def test_PF40_categoria_con_productos_se_marca_no_disponible(self):
        crear_producto(cat=self.cat)
        self.client.post(reverse('admin_categoria_eliminar', args=[self.cat.pk]))
        self.cat.refresh_from_db(); self.assertFalse(self.cat.disponible)

    def test_PF41_categoria_sin_productos_se_elimina(self):
        self.client.post(reverse('admin_categoria_eliminar', args=[self.cat.pk]))
        self.assertFalse(Categoria.objects.filter(pk=self.cat.pk).exists())

    def test_PF42_crear_producto(self):
        r = self.client.post(reverse('admin_producto_crear'), {
            'nombre': 'Lenovo', 'marca': 'Lenovo', 'categoria': self.cat.pk, 'precio': '2500000',
            'stock': '4', 'descripcion': 'Portátil', 'activo': 'on'})
        self.assertRedirects(r, reverse('admin_productos'))
        self.assertEqual(Producto.objects.get().stock, 4)

    def test_PF43_producto_con_stock_negativo_se_rechaza(self):
        self.client.post(reverse('admin_producto_crear'), {
            'nombre': 'X', 'categoria': self.cat.pk, 'precio': '1', 'stock': '-3', 'descripcion': 'd'})
        self.assertFalse(Producto.objects.exists())

    def test_PF44_actualizar_stock_y_precio(self):
        p = crear_producto(cat=self.cat, stock=1)
        self.client.post(reverse('admin_producto_editar', args=[p.pk]), {
            'nombre': p.nombre, 'categoria': self.cat.pk, 'precio': '1800000', 'stock': '9',
            'descripcion': 'd', 'activo': 'on'})
        p.refresh_from_db(); self.assertEqual((p.stock, p.precio), (9, Decimal('1800000')))

    def test_PF45_eliminar_producto_con_apartado_lo_inactiva(self):
        p = crear_producto(cat=self.cat); c = crear_usuario('c@test.com')
        ap = Apartado.objects.create(cliente=c)
        DetalleApartado.objects.create(apartado=ap, producto=p, cantidad=1, precio_unitario=p.precio)
        self.client.post(reverse('admin_producto_eliminar', args=[p.pk]))
        p.refresh_from_db(); self.assertFalse(p.activo)

    def test_PF46_eliminar_producto_sin_apartados_lo_borra(self):
        p = crear_producto(cat=self.cat)
        self.client.post(reverse('admin_producto_eliminar', args=[p.pk]))
        self.assertFalse(Producto.objects.filter(pk=p.pk).exists())

    def test_PF47_flujo_de_estados_del_apartado(self):
        p = crear_producto(cat=self.cat, stock=3); c = crear_usuario('c@test.com')
        ap = Apartado.objects.create(cliente=c)
        DetalleApartado.objects.create(apartado=ap, producto=p, cantidad=1, precio_unitario=p.precio)
        url = reverse('admin_apartado_cambiar_estado', args=[ap.pk])
        self.client.post(url, {'estado': 'entregada'})            # salto no permitido
        ap.refresh_from_db(); self.assertEqual(ap.estado, 'pendiente')
        self.client.post(url, {'estado': 'listo_para_entregar'})
        ap.refresh_from_db(); self.assertEqual(ap.estado, 'listo_para_entregar')
        self.assertIsNotNone(ap.fecha_limite_recogida)
        self.client.post(url, {'estado': 'entregada'})
        ap.refresh_from_db(); self.assertEqual(ap.estado, 'entregada')
        self.client.post(url, {'estado': 'cancelada'})            # ya entregado
        ap.refresh_from_db(); self.assertEqual(ap.estado, 'entregada')

    def test_PF48_admin_cancela_y_el_stock_se_repone(self):
        p = crear_producto(cat=self.cat, stock=1); c = crear_usuario('c@test.com')
        ap = Apartado.objects.create(cliente=c)
        DetalleApartado.objects.create(apartado=ap, producto=p, cantidad=2, precio_unitario=p.precio)
        self.client.post(reverse('admin_apartado_cambiar_estado', args=[ap.pk]), {'estado': 'cancelada'})
        p.refresh_from_db(); self.assertEqual(p.stock, 3)


class PerfilFuncionalTests(TestCase):
    def setUp(self):
        self.u = crear_usuario('c@test.com'); self.client.force_login(self.u)

    def test_PF49_actualizar_datos_personales(self):
        r = self.client.post(reverse('perfil'), {'accion': 'datos', 'first_name': 'Nuevo', 'last_name': 'Nombre',
                             'email': 'c@test.com', 'telefono': '3001234567'}, follow=True)
        self.u.refresh_from_db(); self.assertEqual(self.u.first_name, 'Nuevo')
        self.assertContains(r, 'La información ha sido actualizada.')

    def test_PF50_cambiar_correo_tambien_cambia_usuario(self):
        self.client.post(reverse('perfil'), {'accion': 'datos', 'first_name': 'T', 'email': 'nuevo@test.com'})
        self.u.refresh_from_db(); self.assertEqual(self.u.username, 'nuevo@test.com')

    def test_PF51_cambiar_contrasena(self):
        self.client.post(reverse('perfil'), {'accion': 'password', 'old_password': 'Clave-Segura-123',
                         'new_password1': 'Otra-Clave-456', 'new_password2': 'Otra-Clave-456'})
        self.u.refresh_from_db(); self.assertTrue(self.u.check_password('Otra-Clave-456'))


# ---------------------------------------------------------------- NO FUNCIONALES
class RendimientoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cat = Categoria.objects.create(nombre='Portátiles')
        Producto.objects.bulk_create([Producto(nombre=f'Producto {i}', descripcion='d', precio=Decimal('1000'),
                                      stock=5, categoria=cat) for i in range(500)])

    def test_PN01_catalogo_con_500_productos_carga_en_menos_de_3s(self):
        tiempos = []
        for _ in range(20):
            t = time.perf_counter(); r = self.client.get(reverse('home')); tiempos.append(time.perf_counter() - t)
            self.assertEqual(r.status_code, 200)
        tiempos.sort()
        print(f'\n[PN01] 500 productos, 20 cargas: p50={tiempos[9]*1000:.0f} ms, p95={tiempos[18]*1000:.0f} ms, max={tiempos[-1]*1000:.0f} ms')
        self.assertLess(tiempos[18], 3)

    def test_PN02_detalle_de_producto_en_menos_de_3s(self):
        p = Producto.objects.first(); t = time.perf_counter()
        self.assertEqual(self.client.get(reverse('detalle_producto', args=[p.pk])).status_code, 200)
        print(f'\n[PN02] detalle: {(time.perf_counter()-t)*1000:.0f} ms')
        self.assertLess(time.perf_counter() - t, 3)


class ConcurrenciaTests(TransactionTestCase):
    def test_PN03_dos_clientes_apartan_la_ultima_unidad(self):
        import threading
        from django.db import connection
        from django.test import Client
        p = crear_producto(stock=1)
        clientes = []
        for i in range(2):                       # la sesión se crea antes, en el hilo principal
            u = crear_usuario(f'c{i}@test.com')
            c = Carrito.objects.create(cliente=u)
            ItemCarrito.objects.create(carrito=c, producto=p, cantidad=1)
            cl = Client(); cl.force_login(u)
            clientes.append(cl)
        resultados = []

        def apartar(cl):
            try:
                cl.post(reverse('solicitar_apartado')); resultados.append('ok')
            except Exception as e:               # SQLite puede bloquear una escritura simultánea
                resultados.append(type(e).__name__)
            finally:
                connection.close()

        hilos = [threading.Thread(target=apartar, args=(cl,)) for cl in clientes]
        [h.start() for h in hilos]; [h.join() for h in hilos]
        p.refresh_from_db()
        print(f'\n[PN03] resultados={resultados} apartados={Apartado.objects.count()} stock_final={p.stock}')
        self.assertGreaterEqual(p.stock, 0)
        self.assertLessEqual(Apartado.objects.count(), 1)