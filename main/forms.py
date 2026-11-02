from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.db.models import Q
from .models import Categoria, Producto

MAX_IMAGEN_MB = 5


class RegistroForm(UserCreationForm):
    first_name = forms.CharField(label='Nombre', max_length=150)
    last_name = forms.CharField(label='Apellido', max_length=150)
    email = forms.EmailField(label='Correo electrónico')

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Ya existe una cuenta con este correo.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.username = self.cleaned_data['email']   # el correo hace de usuario
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    username = forms.CharField(label='Correo electrónico')

    error_messages = {
        'invalid_login': 'Correo o contraseña incorrectos.',
        'inactive': 'Esta cuenta está inactiva.',
    }

class _EstiloAdminMixin:
    """Agrega las clases CSS del panel a todos los campos."""
    def _aplicar_estilos(self):
        for campo in self.fields.values():
            widget = campo.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs['class'] = 'check-input'
            elif isinstance(widget, forms.FileInput):
                widget.attrs['class'] = 'file-input'
            else:
                widget.attrs['class'] = 'campo-input'

class CategoriaForm(_EstiloAdminMixin, forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ['nombre', 'descripcion', 'disponible']
        labels = {
            'nombre': 'Nombre',
            'descripcion' : 'Descripción',
            'disponible': 'Categoría Disponible',
        }
        help_texts = {
            'disponible': 'Si la desmarcas, la categoría y sus productos dejan de verse en el catálogo.',
        }
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Ej: Portátiles'}),
            'descripcion': forms.Textarea(attrs={'rows':3})
        }
        error_messages = {
            'nombre': {
                'required': 'El nombre es obligatorio.',
                'unique': 'Ya existe una categoría con ese nombre.',
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._aplicar_estilos()

    def clean_nombre(self):
        nombre = ''.join(self.cleaned_data['nombre'].split())
        repetidas = Categoria.objects.filter(nombre__iexact=nombre)
        if self.instance.pk:
            repetidas = repetidas.exclude(pk=self.instance.pk)
        if repetidas.exists():
            raise forms.ValidationError('Ya existe una categoría con ese nombre.')
        return nombre

class ProductoForm(_EstiloAdminMixin, forms.ModelForm):
    quitar_imagen = forms.BooleanField(required=False, label='Quitar la imagen actual')

    class Meta:
        model = Producto
        fields = [
            'nombre', 'marca', 'categoria', 'precio', 'stock',
            'descripcion', 'caracteristicas', 'imagen', 'activo',
        ]
        labels = {
            'nombre': 'Nombre del producto',
            'marca': 'Marca',
            'categoria': 'Categoría',
            'precio': 'Precio (COP)',
            'stock': 'Unidades en stock',
            'descripcion': 'Descripción',
            'caracteristicas': 'Características',
            'imagen': 'Imagen',
            'activo': 'Producto activo (visible en el catálogo)',
        }
        help_texts = {
            'caracteristicas': 'Una por línea. Ej: Procesador: Intel i5',
            'imagen': f'JPG, PNG o WEBP. Máximo {MAX_IMAGEN_MB} MB',
        }
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Ej: Portátil Lenovo IdeaPad 3'}),
            'marca': forms.TextInput(attrs={'placeholder': 'Ej: Lenovo'}),
            'precio': forms.NumberInput(attrs={'min': '0', 'step': '0.01'}),
            'stock': forms.NumberInput(attrs={'min': '0', 'step': '1'}),
            'descripcion': forms.Textarea(attrs={'rows': 4}),
            'caracteristicas': forms.Textarea(attrs={'rows': 4}),
            'imagen': forms.FileInput(attrs={'accept': 'image/*'}),
        }
        error_messages = {
            'nombre': {'required': 'El nombre es obligatorio.'},
            'descripcion': {'required': 'La descripción es obligatoria.'},
            'precio': {
                'required': 'El precio es obligatorio.',
                'invalid': 'Ingresa un precio válido.',
            },
            'stock': {
                'required': 'El stock es obligatorio.',
                'invalid': 'Ingresa un número entero.',
            },
            'categoria': {'required': 'Selecciona una categoría.'},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Solo categorías disponibles (más la actual del producto, si se edita)
        filtro = Q(disponible=True)
        if self.instance.pk and self.instance.categoria_id:
            filtro |= Q(pk=self.instance.categoria_id)
        self.fields['categoria'].queryset = Categoria.objects.filter(filtro)
        self.fields['categoria'].empty_label = 'Selecciona una categoría'

        self._aplicar_estilos()
        self.fields['quitar_imagen'].widget.attrs['class'] = 'check-input'

    def clean_nombre(self):
        return ' '.join(self.cleaned_data['nombre'].split())

    def clean_stock(self):
        stock = self.cleaned_data['stock']
        if stock is not None and stock < 0:
            raise forms.ValidationError('El stock no puede ser negativo.')
        return stock

    def clean_precio(self):
        precio = self.cleaned_data['precio']
        if precio is not None and precio < 0:
            raise forms.ValidationError('El precio no puede ser negativo.')
        return precio

    def clean_imagen(self):
        imagen = self.cleaned_data.get('imagen')
        subida = self.files.get('imagen')   # solo valida si se subió un archivo nuevo
        if subida and subida.size > MAX_IMAGEN_MB * 1024 * 1024:
            raise forms.ValidationError(f'La imagen no puede pesar más de {MAX_IMAGEN_MB} MB.')
        return imagen

    def save(self, commit=True):
        producto = super().save(commit=False)
        if self.cleaned_data.get('quitar_imagen') and not self.files.get('imagen'):
            producto.imagen = None
        if commit:
            producto.save()
        return producto