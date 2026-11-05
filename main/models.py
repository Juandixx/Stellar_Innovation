from django.db import models, transaction
from django.db.models import F
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator


# =========================
# PERFIL / ROLES (RF1, RF2)
# =========================
class Usuario(models.Model):
    ROLES = (
        ('cliente', 'Cliente'),
        ('administrador', 'Administrador'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='usuario')
    rol = models.CharField(max_length=20, choices=ROLES, default='cliente')
    telefono = models.CharField(max_length=20, blank=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    @property
    def es_administrador(self):
        return self.rol == 'administrador'

    def __str__(self):
        return self.user.email or self.user.username

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"


# =========================
# CATEGORIA (RF5)
# =========================
class Categoria(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)
    disponible = models.BooleanField(default=True)   # en vez de borrar

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"
        ordering = ['nombre']


# =========================
# PRODUCTO (RF3, RF5, RF6)
# =========================
class Producto(models.Model):
    nombre = models.CharField(max_length=150)
    marca = models.CharField(max_length=80, blank=True)
    descripcion = models.TextField()
    caracteristicas = models.TextField(blank=True)
    precio = models.DecimalField(max_digits=12, decimal_places=2,
                                 validators=[MinValueValidator(0)])
    stock = models.PositiveIntegerField(default=0)       # nunca negativo
    imagen = models.ImageField(upload_to='productos/', blank=True, null=True)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT,
                                  related_name='productos')
    activo = models.BooleanField(default=True)           # en vez de borrar
    creado = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ['nombre']


# =========================
# CARRITO (RF4)
# =========================
class Carrito(models.Model):
    cliente = models.OneToOneField(User, on_delete=models.CASCADE, related_name='carrito')
    creado = models.DateTimeField(auto_now_add=True)

    @property
    def total(self):
        return sum(item.subtotal for item in self.items.all())

    def __str__(self):
        return f"Carrito de {self.cliente}"


class ItemCarrito(models.Model):
    carrito = models.ForeignKey(Carrito, on_delete=models.CASCADE, related_name='items')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    @property
    def subtotal(self):
        return self.producto.precio * self.cantidad

    def __str__(self):
        return f"{self.cantidad} x {self.producto}"

    class Meta:
        unique_together = ('carrito', 'producto')


# =========================
# APARTADO (RF4, RF7, RF2)
# =========================
class Apartado(models.Model):
    ESTADOS = (
        ('pendiente', 'Pendiente'),
        ('listo_para_entregar', 'Listo para entregar'),
        ('entregada', 'Entregada'),
        ('cancelada', 'Cancelada'),
    )

    cliente = models.ForeignKey(User, on_delete=models.CASCADE, related_name='apartados')
    fecha = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')

    @property
    def total(self):
        return sum(d.subtotal for d in self.detalles.all())

    @transaction.atomic
    def cancelar(self):
        """Cancela el apartado y devuelve las unidades al stock."""

        if self.estado not in ['pendiente', 'listo_para_entregar']:
            return False

        for detalle in self.detalles.all():
            Producto.objects.filter(
                pk=detalle.producto_id
            ).update(
                stock=F('stock') + detalle.cantidad
            )

        self.estado = 'cancelada'
        self.save(update_fields=['estado'])

        return True

    def __str__(self):
        return f"Apartado #{self.id} - {self.cliente}"

    class Meta:
        ordering = ['-fecha']


class DetalleApartado(models.Model):
    apartado = models.ForeignKey(Apartado, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2)  # precio al apartar

    @property
    def subtotal(self):
        return self.precio_unitario * self.cantidad

    def __str__(self):
        return f"{self.cantidad} x {self.producto}"