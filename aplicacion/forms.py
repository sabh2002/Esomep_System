from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from .models import (
    Bienes, Departamentos,  RolDelUsuario, Descripcion, Grupo, SeccionSubgrupo, Subgrupo, ConceptoDeMovimiento,
    Solicitudes, Usuario,  TiposDeSolicitud, Stock, Especificacion, TipoBien, Usuario, UnidadOrganizacional
    
)
from django.forms import modelformset_factory, inlineformset_factory
from django.db.models import Sum, Exists, OuterRef
import logging
from .models import Solicitudes, Bienes, AsignacionDeBienes
from django.db.models import Value, CharField
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _
import re 
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from django.utils.formats import number_format

logger = logging.getLogger(__name__)


class BienForm(forms.ModelForm):
    numero_de_identificacion_original = forms.CharField(widget=forms.HiddenInput(), required=False)
    fecha_de_registro = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',
            'max': date.today().strftime('%Y-%m-%d'),
            'class': 'form-control'
        }),
        required=True
    )

    incorporacion = forms.CharField(
        required=True,
        initial='0',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ingrese el monto'
        })
    )

    desincorporacion = forms.CharField(
        required=False,
        initial='0',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ingrese el monto'
        })
    )
    
    class Meta:
        model = Bienes
        fields = [
            'tipo_bien',
            'id_grupo', 
            'id_subgrupo', 
            'id_seccion_subgrupo',
            'nombre',
            'numero_de_identificacion',
            'id_concepto_de_movimiento',
            'incorporacion',
            'condicion',
            'observacion',
            'archivo_multimedia',
            'fecha_de_registro'
        ]
        widgets = {
            'tipo_bien': forms.Select(attrs={
                'class': 'form-control select2',
                'style': 'width: 100%'
            }),
            'id_grupo': forms.Select(attrs={
                'class': 'form-control'
            }),
            'id_subgrupo': forms.Select(attrs={
                'class': 'form-control'
            }),
            'id_seccion_subgrupo': forms.Select(attrs={
                'class': 'form-control',
                'data-required': 'false'
            }),
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'maxlength': '255'
            }),
            'numero_de_identificacion': forms.TextInput(attrs={
                'class': 'form-control',
                'pattern': r'[0-9]*',
                'placeholder': 'Ingrese el número de identificación'
            }),
            'id_concepto_de_movimiento': forms.Select(attrs={
                'class': 'form-control select2',
                'style': 'width: 100%'
            }),
            'condicion': forms.Select(attrs={
                'class': 'form-control'
            }),
            'observacion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),
            'archivo_multimedia': forms.FileInput(attrs={
                'class': 'form-control'
            })
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Configurar los campos select inicialmente vacíos
        self.fields['id_subgrupo'].queryset = Subgrupo.objects.none()
        self.fields['id_seccion_subgrupo'].queryset = SeccionSubgrupo.objects.none()
        
        # Si hay datos POST, obtener los valores y configurar querysets
        if 'data' in kwargs:
            try:
                grupo_id = kwargs['data'].get('id_grupo')
                if grupo_id:
                    self.fields['id_subgrupo'].queryset = Subgrupo.objects.filter(
                        id_grupo=grupo_id
                    ).order_by('nombre')
                    self.fields['id_subgrupo'].label_from_instance = lambda obj: f"{obj.codigo} - {obj.nombre}"
                        
                subgrupo_id = kwargs['data'].get('id_subgrupo')
                if subgrupo_id:
                    self.fields['id_seccion_subgrupo'].queryset = SeccionSubgrupo.objects.filter(
                        id_subgrupo=subgrupo_id
                    ).order_by('nombre')
                    self.fields['id_seccion_subgrupo'].label_from_instance = lambda obj: f"{obj.codigo} - {obj.nombre}"
            except (ValueError, TypeError):
                pass

    # Si estamos editando un bien existente
        elif self.instance.pk:
            if self.instance.id_grupo:
                self.fields['id_subgrupo'].queryset = Subgrupo.objects.filter(
                    id_grupo=self.instance.id_grupo
                ).order_by('nombre')
                self.fields['id_subgrupo'].label_from_instance = lambda obj: f"{obj.codigo} - {obj.nombre}"
                
                # Preseleccionar el subgrupo
                if self.instance.id_subgrupo:
                    self.initial['id_subgrupo'] = self.instance.id_subgrupo.pk
        
        if self.instance.id_subgrupo:
            self.fields['id_seccion_subgrupo'].queryset = SeccionSubgrupo.objects.filter(
                id_subgrupo=self.instance.id_subgrupo
            ).order_by('nombre')
            self.fields['id_seccion_subgrupo'].label_from_instance = lambda obj: f"{obj.codigo} - {obj.nombre}"
            
            # Preseleccionar la sección
            if self.instance.id_seccion_subgrupo:
                self.initial['id_seccion_subgrupo'] = self.instance.id_seccion_subgrupo.pk


        # Guardar el número original si existe
        if self.instance.pk:
            self.fields['numero_de_identificacion_original'].initial = self.instance.numero_de_identificacion
            self._numero_original = self.instance.numero_de_identificacion
        else:
            self._numero_original = None

        # Campos requeridos
        required_fields = [
            'tipo_bien',
            'id_grupo',
            'id_subgrupo',
            'id_concepto_de_movimiento',
            'numero_de_identificacion',
            'nombre',
            'incorporacion',
            'fecha_de_registro'
        ]
        
        # Establecer campos requeridos
        for field in required_fields:
            self.fields[field].required = True
        
        # Campos explícitamente no requeridos
        non_required_fields = [
            'id_seccion_subgrupo',
            'condicion',
            'observacion',
            'archivo_multimedia'
        ]
        
        for field in non_required_fields:
            self.fields[field].required = False
        
        # Ayuda para campos específicos
        self.fields['numero_de_identificacion'].help_text = 'Ingrese un número de identificación único. No se permiten duplicados.'
        self.fields['incorporacion'].help_text = 'Ingrese el valor en bolívares.'

        # Si hay un valor de incorporación al editar, mostrarlo formateado
        if self.instance.pk and self.instance.incorporacion:
            self.initial['incorporacion'] = self.instance.incorporacion
    def clean_fecha_de_registro(self):
        fecha = self.cleaned_data.get('fecha_de_registro')
        if fecha and fecha > date.today():
            raise ValidationError('No se pueden registrar bienes con fechas futuras.')
        return fecha

    def clean_incorporacion(self):
        valor = self.cleaned_data.get('incorporacion', '')
        if not valor:
            return ''
        
        # Limpiar y validar el valor
        try:
            # Remover espacios
            valor = valor.strip()
            
            # Reemplazar coma por punto si existe
            valor = valor.replace('.', '')  # Primero quitamos los puntos
            valor = valor.replace(',', '.')  # Luego reemplazamos la coma por punto
            
            # Convertir a float para validar
            valor_float = float(valor)
            
            # Formatear el valor con dos decimales
            valor_formateado = '{:,.2f}'.format(valor_float)
            
            return valor_formateado
            
        except ValueError:
            raise ValidationError('Por favor ingrese un valor numérico válido')
        
        return valor
    
    def clean_desincorporacion(self):
        valor = self.cleaned_data.get('desincorporacion', '')
        if not valor:
            return ''
        
        try:
            # Remover espacios
            valor = valor.strip()
            
            # Convertir el formato de moneda a un número que Python pueda procesar
            # Primero eliminamos los puntos de los miles
            valor_procesado = valor.replace('.', '')
            # Luego reemplazamos la coma decimal por punto
            valor_procesado = valor_procesado.replace(',', '.')
            
            # Convertir a float
            valor_float = float(valor_procesado)
            
            # Validar que no sea negativo
            if valor_float < 0:
                raise ValidationError('El valor no puede ser negativo')
            
            # Formatear el valor con separadores de miles y decimales
            if valor_float == 0:
                return '0'
            elif valor_float.is_integer():
                # Si es un número entero, no mostrar decimales
                valor_formateado = '{:,.0f}'.format(valor_float)
            else:
                # Si tiene decimales, mostrar dos decimales
                valor_formateado = '{:,.2f}'.format(valor_float)
            
            # Convertir al formato venezolano (cambiar , por . y . por ,)
            valor_formateado = valor_formateado.replace(',', 'T').replace('.', ',').replace('T', '.')
            
            return valor_formateado
            
        except ValueError:
            raise ValidationError('Por favor ingrese un valor numérico válido')
        
        return valor


    def clean_numero_de_identificacion(self):
        numero = self.cleaned_data.get('numero_de_identificacion')
        
        if not numero:
            raise ValidationError('Este campo es requerido.')
        
        if not numero.isdigit():
            raise ValidationError('El número de identificación debe contener solo dígitos.')
        
        # Si estamos en modo edición y existe un número original
        if hasattr(self, '_numero_original'):
            # Solo validar si el número ha cambiado
            if numero != self._numero_original:
                qs = Bienes.objects.filter(numero_de_identificacion=numero)
                if self.instance.pk:
                    qs = qs.exclude(pk=self.instance.pk)
                
                if qs.exists():
                    bien_existente = qs.first()
                    raise ValidationError(
                        f'Ya existe un bien con este número de identificación. '
                        f'Pertenece a: {bien_existente.nombre}'
                    )
                
                self.numero_cambiado = True
                self.numero_anterior = self._numero_original
            else:
                self.numero_cambiado = False
        else:
            if Bienes.objects.filter(numero_de_identificacion=numero).exists():
                raise ValidationError('Ya existe un bien con este número de identificación.')
            
        return numero

    def clean_nombre(self):
        nombre = self.cleaned_data.get('nombre')
        if nombre and any(char.isdigit() for char in nombre):
            raise ValidationError('El nombre no debe contener números.')
        return nombre

    def clean(self):
        cleaned_data = super().clean()
        
        # Validación de grupo y subgrupo
        grupo = cleaned_data.get('id_grupo')
        subgrupo = cleaned_data.get('id_subgrupo')
        
        if grupo and not subgrupo:
            self.fields['id_subgrupo'].queryset = Subgrupo.objects.filter(id_grupo=grupo)
            if not self.fields['id_subgrupo'].queryset.exists():
                self.add_error('id_subgrupo', 'No hay subgrupos disponibles para el grupo seleccionado.')
        
        if subgrupo and grupo and subgrupo.id_grupo != grupo:
            self.add_error('id_subgrupo', 'El subgrupo seleccionado no pertenece al grupo elegido.')
            
        # Validación de sección
        seccion = cleaned_data.get('id_seccion_subgrupo')
        if seccion and subgrupo and seccion.id_subgrupo != subgrupo:
            self.add_error('id_seccion_subgrupo', 'La sección seleccionada no pertenece al subgrupo elegido.')
            
        # Verificar que la sección no sea requerida incluso en validación general
        if 'id_seccion_subgrupo' in self._errors:
            del self._errors['id_seccion_subgrupo']
            
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Configurar cambio de número si aplica
        if hasattr(self, 'numero_cambiado') and self.numero_cambiado:
            instance._numero_cambiado = True
            instance._numero_anterior = self.numero_anterior
        else:
            instance._numero_cambiado = False
            
        if commit:
            instance.save()
        return instance

from django import forms
from django.forms import inlineformset_factory
from .models import Descripcion, Especificacion, Bienes

class DescripcionForm(forms.ModelForm):
    class Meta:
        model = Descripcion
        fields = ['descripcion', 'estado']
        widgets = {
            'descripcion': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingrese la descripción'
            }),
            'estado': forms.Select(attrs={
                'class': 'form-control'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hacemos los campos opcionales
        self.fields['descripcion'].required = False
        self.fields['estado'].required = False

class EspecificacionForm(forms.ModelForm):
    class Meta:
        model = Especificacion
        fields = ['especificacion', 'descripcion_especificacion']
        widgets = {
            'especificacion': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingrese la especificación'
            }),
            'descripcion_especificacion': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingrese la descripción de la especificación'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hacemos los campos opcionales
        self.fields['especificacion'].required = False
        self.fields['descripcion_especificacion'].required = False

# Formsets modificados para ser opcionales
DescripcionFormSet = inlineformset_factory(
    Bienes,
    Descripcion,
    form=DescripcionForm,
    extra=1,
    can_delete=True,
    fields=['descripcion', 'estado'],
    min_num=0,  # Permitir que no haya descripciones
    validate_min=False  # No validar el mínimo
)

EspecificacionFormSet = inlineformset_factory(
    Bienes,
    Especificacion,
    form=EspecificacionForm,
    extra=1,
    can_delete=True,
    fields=['especificacion', 'descripcion_especificacion'],
    min_num=0,  # Permitir que no haya especificaciones
    validate_min=False  # No validar el mínimo
)
from django import forms


class DepartamentoForm(forms.ModelForm):
    UnidadOrganizacional = forms.ModelChoiceField(  # Changed from unidadOrganizacional
        queryset=UnidadOrganizacional.objects.all(),
        empty_label="Selecciona una unidad organizacional",
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=True
    )
   
    class Meta:
        model = Departamentos
        fields = ['UnidadOrganizacional', 'codigo_departamento', 'nombre_departamento', 'descripcion']  # Changed field name
        widgets = {
            'codigo_departamento': forms.TextInput(attrs={'class': 'form-control'}),
            'nombre_departamento': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'UnidadOrganizacional': 'Unidad Organizacional',  # Changed field name
            'codigo_departamento': 'Código del Departamento',
            'nombre_departamento': 'Nombre del Departamento', 
            'descripcion': 'Descripción'
        }

    def clean(self):
        cleaned_data = super().clean()
        unidad = cleaned_data.get('UnidadOrganizacional')  # Changed from unidadOrganizacional
        codigo = cleaned_data.get('codigo_departamento')
        nombre = cleaned_data.get('nombre_departamento')

        if unidad and codigo:
            exists = Departamentos.objects.filter(
                UnidadOrganizacional=unidad,  # Changed from unidadOrganizacional
                codigo_departamento=codigo
            ).exists()
            if exists and (not self.instance or self.instance.codigo_departamento != codigo):
                self.add_error('codigo_departamento', 'Ya existe un departamento con este código en la unidad organizacional seleccionada.')

        if unidad and nombre:
            exists = Departamentos.objects.filter(
                UnidadOrganizacional=unidad,  # Changed from unidadOrganizacional
                nombre_departamento=nombre
            ).exists()
            if exists and (not self.instance or self.instance.nombre_departamento != nombre):
                self.add_error('nombre_departamento', 'Ya existe un departamento con este nombre en la unidad organizacional seleccionada.')

        return cleaned_data

class RolUsuarioForm(forms.ModelForm):
    class Meta:
        model = RolDelUsuario
        fields = '__all__'


class UnidadOrganizacionalForm(forms.ModelForm):
   class Meta:
       model = UnidadOrganizacional  
       fields = ['codigo', 'nombre', 'descripcion']
       widgets = {
           'codigo': forms.TextInput(attrs={'class': 'form-control'}),
           'nombre': forms.TextInput(attrs={'class': 'form-control'}),
           'descripcion': forms.TextInput(attrs={'class': 'form-control'}),
       }
       labels = {
           'codigo': 'Código de la Unidad',
           'nombre': 'Nombre de la Unidad',
           'descripcion': 'Descripción',
       }

   def clean_codigo(self):
       codigo = self.cleaned_data.get('codigo')
       if len(codigo) < 2:
           raise forms.ValidationError("El código debe tener al menos 2 caracteres")
       return codigo


class UsuarioForm(forms.ModelForm):
   confirmar_contrasena = forms.CharField(
       widget=forms.PasswordInput(attrs={'class': 'form-control'}),
       label='Confirmar Contraseña'
   )
   
   class Meta:
       model = Usuario
       fields = ['cedula', 'nombres', 'apellidos', 'email', 'telefono', 
                'id_unidadOrganizacional', 'id_departamentos', 'id_rol_del_usuario', 
                'password']
       widgets = {
           'cedula': forms.TextInput(attrs={
               'class': 'form-control',
               'placeholder': 'Ingrese la cédula'
           }),
           'nombres': forms.TextInput(attrs={
               'class': 'form-control',
               'placeholder': 'Ingrese los nombres'
           }),
           'apellidos': forms.TextInput(attrs={
               'class': 'form-control',
               'placeholder': 'Ingrese los apellidos'
           }),
           'email': forms.EmailInput(attrs={
               'class': 'form-control',
               'placeholder': 'correo@ejemplo.com'
           }),
           'telefono': forms.TextInput(attrs={
               'class': 'form-control',
               'placeholder': 'Ingrese el teléfono'
           }),
           'id_unidadOrganizacional': forms.Select(attrs={
               'class': 'form-control'
           }),
           'id_departamentos': forms.Select(attrs={
               'class': 'form-control'
           }),
           'id_rol_del_usuario': forms.Select(attrs={
               'class': 'form-control'
           }),
           'password': forms.PasswordInput(attrs={
               'class': 'form-control',
               'placeholder': 'Ingrese la contraseña'
           })
       }

   def __init__(self, *args, **kwargs):
       super().__init__(*args, **kwargs)
       instance = kwargs.get('instance')

       # Obtener IDs de unidades y departamentos ya asignados
       unidades_asignadas = Usuario.objects.exclude(
           id_usuario=instance.id_usuario if instance else None
       ).filter(
           id_unidadOrganizacional__isnull=False
       ).values_list('id_unidadOrganizacional', flat=True)

       departamentos_asignados = Usuario.objects.exclude(
           id_usuario=instance.id_usuario if instance else None
       ).filter(
           id_departamentos__isnull=False
       ).values_list('id_departamentos', flat=True)

       # Filtrar solo las unidades y departamentos disponibles
       self.fields['id_unidadOrganizacional'].queryset = UnidadOrganizacional.objects.exclude(
           id_unidad__in=unidades_asignadas
       )
       self.fields['id_departamentos'].queryset = Departamentos.objects.exclude(
           id_departamentos__in=departamentos_asignados
       )

       # Agregar opción vacía
       self.fields['id_unidadOrganizacional'].empty_label = "Seleccione una unidad organizacional"
       self.fields['id_departamentos'].empty_label = "Seleccione un departamento"

       # Campos obligatorios
       self.fields['cedula'].required = True
       self.fields['nombres'].required = True
       self.fields['apellidos'].required = True
       self.fields['email'].required = True
       self.fields['password'].required = not bool(instance)

       # No requerir unidad y departamento individualmente 
       self.fields['id_unidadOrganizacional'].required = False
       self.fields['id_departamentos'].required = False

   def clean(self):
       cleaned_data = super().clean()
       unidadOrganizacional = cleaned_data.get('id_unidadOrganizacional')
       departamento = cleaned_data.get('id_departamentos')
       password = cleaned_data.get('password')
       confirmar_contrasena = cleaned_data.get('confirmar_contrasena')

       if unidadOrganizacional and departamento:
           raise forms.ValidationError(
               "No puede seleccionar tanto unidad organizacional como departamento. Debe elegir uno u otro."
           )
       
       if not unidadOrganizacional and not departamento:
           raise forms.ValidationError(
               "Debe seleccionar una unidad organizacional o un departamento."
           )

       if password:
           if not confirmar_contrasena:
               raise forms.ValidationError("Debe confirmar la contraseña.")
           if password != confirmar_contrasena:
               raise forms.ValidationError("Las contraseñas no coinciden.")

       return cleaned_data


######################################################################





class SolicitudForm(forms.ModelForm):
    class Meta:
        model = Solicitudes
        fields = ['id_tipos_de_solicitud', 'descripcion', 'bien_id', 'cantidad_solicitada', 'departamento_destino', 'fecha_maxima_traslado']
        widgets = {
            'id_tipos_de_solicitud': forms.Select(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'bien_id': forms.Select(attrs={'class': 'form-control'}),
            'cantidad_solicitada': forms.NumberInput(attrs={'class': 'form-control'}),
            'departamento_destino': forms.Select(attrs={'class': 'form-control'}),
            'fecha_maxima_traslado': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.user.id_rol_del_usuario.nombre_rol == 'ADMIN_BIENES':
            self.fields['usuario_solicitante'] = forms.ModelChoiceField(
                queryset=Usuario.objects.exclude(id_rol_del_usuario__nombre_rol='ADMIN_BIENES'),
                label="Usuario Solicitante",
                widget=forms.Select(attrs={'class': 'form-control'})
            )
            self.fields['departamento_solicitante'] = forms.ModelChoiceField(
                queryset=Departamentos.objects.all(),
                label="Departamento Solicitante",
                widget=forms.Select(attrs={'class': 'form-control'})
            )
        else:
            # Obtener todos los bienes asignados al departamento del usuario
            bienes_asignados = AsignacionDeBienes.objects.filter(
                id_departamentos=self.user.id_departamentos
            ).values_list('id_bienes', flat=True)

            # Filtrar los bienes disponibles
            self.fields['bien_id'].queryset = Bienes.objects.filter(id_bienes__in=bienes_asignados)
        
        self.fields['departamento_destino'].queryset = Departamentos.objects.exclude(id_departamentos=self.user.id_departamentos.id_departamentos)

        # Hacer que los campos sean inicialmente opcionales
        self.fields['bien_id'].required = False
        self.fields['cantidad_solicitada'].required = False
        self.fields['departamento_destino'].required = False
        self.fields['fecha_maxima_traslado'].required = False

    def clean(self):
        cleaned_data = super().clean()
        tipo_solicitud = cleaned_data.get('id_tipos_de_solicitud')
        bien = cleaned_data.get('bien_id')
        departamento_destino = cleaned_data.get('departamento_destino')
        fecha_maxima_traslado = cleaned_data.get('fecha_maxima_traslado')

        if tipo_solicitud:
            if tipo_solicitud.nombre == 'Desincorporación':
                if not bien:
                    self.add_error('bien_id', 'Debe seleccionar un bien para desincorporar')
            elif tipo_solicitud.nombre == 'Traslado':
                if not bien:
                    self.add_error('bien_id', 'Debe seleccionar un bien para trasladar')
                if not departamento_destino:
                    self.add_error('departamento_destino', 'Debe seleccionar un departamento de destino')
                if not fecha_maxima_traslado:
                    self.add_error('fecha_maxima_traslado', 'Debe especificar una fecha máxima de traslado')
            elif tipo_solicitud.nombre == 'Permanente':
                if bien:
                    self.add_error('bien_id', 'No se debe seleccionar un bien para solicitudes permanentes')
            elif tipo_solicitud.nombre == 'Temporal':
                if bien:
                    self.add_error('bien_id', 'No se debe seleccionar un bien para solicitudes temporales')
                if not fecha_maxima_traslado:
                    self.add_error('fecha_maxima_traslado', 'Debe especificar una fecha de devolución')

        return cleaned_data
    


class AsignarBienesForm(forms.Form):
   destino = forms.CharField(
       label="Unidad o Departamento",
       required=True,
       widget=forms.Select(
           attrs={
               'class': 'form-control select2',
               'style': 'width: 100%',
           }
       )
   )

   bienes = forms.ModelMultipleChoiceField(
       queryset=Bienes.objects.filter(
           stock__cantidad_disponible__gt=0
       ).distinct(),
       label="Bienes",
       widget=forms.CheckboxSelectMultiple(
           attrs={
               'class': 'form-check-input'
           }
       )
   )

   def __init__(self, *args, **kwargs):
       super().__init__(*args, **kwargs)
       
       self.fields['bienes'].queryset = Bienes.objects.filter(
           stock__cantidad_disponible__gt=0
       ).distinct().select_related('stock')
       
       # Obtener unidades y departamentos disponibles
       unidades = UnidadOrganizacional.objects.filter(
           usuario__isnull=False,
           usuario__estado='activo'
       ).annotate(
           tipo=Value('unidad', output_field=CharField())
       ).values('id_unidad', 'nombre', 'tipo')

       departamentos = Departamentos.objects.filter(
           usuario__isnull=False,
           usuario__estado='activo'
       ).exclude(
           nombre_departamento='Bienes'
       ).annotate(
           tipo=Value('departamento', output_field=CharField())
       ).values('id_departamentos', 'nombre_departamento', 'tipo')

       CHOICES = [('', 'Seleccione una opción')]
       
       if unidades.exists():
           CHOICES.append(('', '-' * 8 + ' Unidades Organizacionales ' + '-' * 8))
           CHOICES.extend([
               (f"U-{u['id_unidad']}", f"{u['nombre']}")
               for u in unidades
           ])

       if departamentos.exists():
           CHOICES.append(('', '-' * 8 + ' Departamentos ' + '-' * 8))
           CHOICES.extend([
               (f"D-{d['id_departamentos']}", f"{d['nombre_departamento']}")
               for d in departamentos
           ])

       self.fields['destino'].widget.choices = CHOICES

   def clean(self):
       cleaned_data = super().clean()
       bienes = cleaned_data.get('bienes')
       destino = cleaned_data.get('destino')

       if not bienes:
           raise ValidationError("Debe seleccionar al menos un bien para asignar.")

       if not destino:
           raise ValidationError("Debe seleccionar una unidad organizacional o departamento.")

       try:
           tipo, id_destino = destino.split('-')
           id_destino = int(id_destino)
       except ValueError:
           raise ValidationError("Destino inválido")

       if tipo == 'U':
           cleaned_data['unidadOrganizacional'] = UnidadOrganizacional.objects.get(id_unidad=id_destino)
           cleaned_data['departamento'] = None
       elif tipo == 'D':
           cleaned_data['departamento'] = Departamentos.objects.get(id_departamentos=id_destino)
           cleaned_data['unidadOrganizacional'] = None
       else:
           raise ValidationError("Tipo de destino inválido")

       for bien in bienes:
           try:
               stock = Stock.objects.get(bien_id=bien)
               
               if stock.cantidad_disponible < 1:
                   raise ValidationError(
                       f"El bien '{bien.nombre}' no tiene unidades disponibles."
                   )

               asignacion_existente = AsignacionDeBienes.objects.filter(
                   id_bienes=bien,
                   fecha_fin_temporal__isnull=True
               )

               if tipo == 'U':
                   asignacion_existente = asignacion_existente.filter(
                       id_UnidadOrganizacional=cleaned_data['unidadOrganizacional']
                   )
               else:
                   asignacion_existente = asignacion_existente.filter(
                       id_departamentos=cleaned_data['departamento']
                   )

               if asignacion_existente.exists():
                   destino_nombre = (cleaned_data['unidadOrganizacional'].nombre 
                                   if tipo == 'U'
                                   else cleaned_data['departamento'].nombre_departamento)
                   raise ValidationError(
                       f"El bien '{bien.nombre}' ya está asignado a {destino_nombre}."
                   )

           except Stock.DoesNotExist:
               raise ValidationError(
                   f"No se encontró información de stock para el bien '{bien.nombre}'."
               )

       return cleaned_data



class RegistroUsuarioForm(forms.ModelForm):
    contrasena = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ingrese su contraseña'
        }),
        label='Contraseña',
        required=True
    )
    
    confirmar_contrasena = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirme su contraseña'
        }),
        label='Confirmar Contraseña',
        required=True
    )

    id_unidadOrganizacional = forms.ModelChoiceField(
        queryset=UnidadOrganizacional.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Unidad Organizacional'
    )

    id_departamentos = forms.ModelChoiceField(
        queryset=Departamentos.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Departamento'
    )

    class Meta:
        model = Usuario
        fields = [
            'cedula',
            'nombres',
            'apellidos',
            'email',
            'telefono',
            'id_unidadOrganizacional',
            'id_departamentos',
            'id_rol_del_usuario'
        ]
        widgets = {
            'cedula': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingrese su cédula'
            }),
            'nombres': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingrese sus nombres'
            }),
            'apellidos': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingrese sus apellidos'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingrese su correo electrónico'
            }),
            'telefono': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingrese su teléfono'
            }),
            'id_rol_del_usuario': forms.Select(attrs={
                'class': 'form-control'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cedula'].required = True
        self.fields['nombres'].required = True
        self.fields['apellidos'].required = True
        self.fields['email'].required = True
        self.fields['telefono'].required = True
        self.fields['id_rol_del_usuario'].required = True

    def clean(self):
        cleaned_data = super().clean()
        contrasena = cleaned_data.get('contrasena')
        confirmar_contrasena = cleaned_data.get('confirmar_contrasena')
        unidad = cleaned_data.get('id_unidadOrganizacional')
        departamento = cleaned_data.get('id_departamentos')

        # Validar contraseñas
        if contrasena and confirmar_contrasena:
            if contrasena != confirmar_contrasena:
                raise forms.ValidationError('Las contraseñas no coinciden')
            if len(contrasena) < 8:
                raise forms.ValidationError('La contraseña debe tener al menos 8 caracteres')

        # Validar selección de unidad o departamento
        if unidad and departamento:
            raise forms.ValidationError('No puede seleccionar tanto una unidad organizacional como un departamento')
        if not unidad and not departamento:
            raise forms.ValidationError('Debe seleccionar una unidad organizacional o un departamento')

        return cleaned_data

    def clean_cedula(self):
        cedula = self.cleaned_data.get('cedula')
        if cedula:
            if not cedula.isdigit():
                raise forms.ValidationError('La cédula debe contener solo números')
            if len(cedula) < 7 or len(cedula) > 10:
                raise forms.ValidationError('La cédula debe tener entre 7 y 10 dígitos')
            if Usuario.objects.filter(cedula=cedula).exists():
                raise forms.ValidationError('Esta cédula ya está registrada')
        return cedula

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and Usuario.objects.filter(email=email).exists():
            raise forms.ValidationError('Este correo electrónico ya está registrado')
        return email
    
class StockForm(forms.ModelForm):
    class Meta:
        model = Stock
        fields = ['cantidad_total', 'cantidad_disponible', 'cantidad_asignada', 
                  'cantidad_prestada', 'cantidad_en_mantenimiento', 
                  'cantidad_desincorporada', 'cantidad_resguardada']

    def clean(self):
        cleaned_data = super().clean()
        total = cleaned_data.get('cantidad_total')
        disponible = cleaned_data.get('cantidad_disponible')
        asignada = cleaned_data.get('cantidad_asignada')
        prestada = cleaned_data.get('cantidad_prestada')
        mantenimiento = cleaned_data.get('cantidad_en_mantenimiento')
        desincorporada = cleaned_data.get('cantidad_desincorporada')
        resguardada = cleaned_data.get('cantidad_resguardada')

        if total != (disponible + asignada + prestada + mantenimiento + desincorporada + resguardada):
            raise forms.ValidationError("La suma de las cantidades debe ser igual al total.")

        return cleaned_data




class RestablecerContrasenaForm(forms.Form):
    nueva_contrasena = forms.CharField(
        widget=forms.PasswordInput(),
        label="Nueva Contraseña",
        strip=False
    )
    confirmar_contrasena = forms.CharField(
        widget=forms.PasswordInput(),
        label="Confirmar Nueva Contraseña",
        strip=False
    )

    def clean(self):
        cleaned_data = super().clean()
        nueva_contrasena = cleaned_data.get("nueva_contrasena")
        confirmar_contrasena = cleaned_data.get("confirmar_contrasena")

        if nueva_contrasena and confirmar_contrasena:
            if nueva_contrasena != confirmar_contrasena:
                raise ValidationError("Las contraseñas no coinciden.")
            
            try:
                # Validar la contraseña usando las validaciones predeterminadas de Django
                validate_password(nueva_contrasena)
            except ValidationError as e:
                self.add_error('nueva_contrasena', e)

        return cleaned_data
    

class AsignarRolForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ['id_rol_del_usuario']
        labels = {
            'id_rol_del_usuario': 'Rol del Usuario'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['id_rol_del_usuario'].queryset = RolDelUsuario.objects.all()
        self.fields['id_rol_del_usuario'].widget = forms.Select(attrs={'class': 'form-control'})



class DesincorporacionForm(forms.Form):
    bien = forms.ModelChoiceField(
        queryset=Bienes.objects.none(),
        label='Bien a desincorporar',
        empty_label="Seleccione un bien"
    )
    motivo = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4}),
        label='Motivo de la desincorporación'
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(DesincorporacionForm, self).__init__(*args, **kwargs)
        
        if user:
            # Obtener los bienes asignados que no están en traslado temporal
            if user.id_departamentos:
                bienes_disponibles = Bienes.objects.filter(
                    asignaciondebienes__id_departamentos=user.id_departamentos,
                    asignaciondebienes__fecha_fin_temporal__isnull=True  # No están en traslado temporal
                ).distinct()
            elif user.id_unidadOrganizacional:
                bienes_disponibles = Bienes.objects.filter(
                    asignaciondebienes__id_UnidadOrganizacional=user.id_unidadOrganizacional,
                    asignaciondebienes__fecha_fin_temporal__isnull=True  # No están en traslado temporal
                ).distinct()
            else:
                bienes_disponibles = Bienes.objects.none()

            # Excluir bienes que estén en traslado temporal
            bienes_en_traslado = AsignacionDeBienes.objects.filter(
                fecha_fin_temporal__isnull=False,
                fecha_fin_temporal__gt=timezone.now()
            ).values_list('id_bienes', flat=True)

            bienes_disponibles = bienes_disponibles.exclude(
                id_bienes__in=bienes_en_traslado
            )

            self.fields['bien'].queryset = bienes_disponibles

    
class ProcesarDesincorporacionForm(forms.Form):
    motivo_rechazo = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'style': 'display: none;'  # Ocultamos este campo ya que usamos el modal
        }),
        required=False
    )

    def clean_motivo_rechazo(self):
        motivo_rechazo = self.cleaned_data.get('motivo_rechazo')
        action = self.data.get('action')
        
        if action == 'rechazar' and not motivo_rechazo:
            raise forms.ValidationError("Debe proporcionar un motivo para rechazar la solicitud.")
            
        return motivo_rechazo


class SolicitudPermanenteForm(forms.ModelForm):
    class Meta:
        model = Solicitudes
        fields = ['descripcion']
        widgets = {
            'descripcion': forms.Textarea(attrs={
                'rows': 4, 
                'cols': 50, 
                'class': 'form-control',
                'placeholder': 'Describa el motivo del traslado permanente'
            })
        }

from django import forms
from django.utils import timezone
from .models import Solicitudes, Bienes, AsignacionDeBienes, Departamentos
import json


class ProcesarSolicitudPermanenteForm(forms.ModelForm):
    bien_id = forms.ModelChoiceField(
        queryset=Bienes.objects.none(),
        label="Bien a trasladar",
        widget=forms.Select(attrs={
            'class': 'form-control select2',
            'style': 'width: 100%',
            'data-placeholder': 'Seleccione un bien para trasladar'
        })
    )

    class Meta:
        model = Solicitudes
        fields = ['bien_id']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if self.instance:
            ubicacion_solicitante = None
            ubicacion_tipo = None
            
            if self.instance.departamento_solicitante:
                ubicacion_solicitante = self.instance.departamento_solicitante
                ubicacion_tipo = 'departamento'
            elif self.instance.UnidadOrganizacional_solicitante:
                ubicacion_solicitante = self.instance.UnidadOrganizacional_solicitante
                ubicacion_tipo = 'unidad'
            
            bienes_query = Bienes.objects.filter(
                condicion='Operativo',
                asignaciondebienes__fecha_fin_temporal__isnull=True,
                asignaciondebienes__cantidad_asignada__gt=0
            ).select_related(
                'stock'
            ).prefetch_related(
                'asignaciondebienes_set'
            )

            if ubicacion_tipo == 'departamento':
                bienes_query = bienes_query.exclude(
                    asignaciondebienes__id_departamentos=ubicacion_solicitante
                )
            elif ubicacion_tipo == 'unidad':
                bienes_query = bienes_query.exclude(
                    asignaciondebienes__id_UnidadOrganizacional=ubicacion_solicitante
                )

            bienes_disponibles = bienes_query.distinct()
            
            # Preparar diccionario de asignaciones para el frontend
            self.asignaciones = {}
            for bien in bienes_disponibles:
                asignaciones_bien = []
                for asignacion in bien.asignaciondebienes_set.filter(fecha_fin_temporal__isnull=True):
                    info_asignacion = {
                        'id': asignacion.id_asignacion_bienes,
                        'ubicacion_tipo': 'departamento' if asignacion.id_departamentos else 'unidad',
                        'ubicacion_nombre': '',
                        'cantidad': asignacion.cantidad_asignada
                    }
                    
                    if asignacion.id_departamentos:
                        info_asignacion.update({
                            'ubicacion_id': asignacion.id_departamentos.id_departamentos,
                            'ubicacion_nombre': asignacion.id_departamentos.nombre_departamento,
                            'unidad_nombre': asignacion.id_departamentos.UnidadOrganizacional.nombre if asignacion.id_departamentos.UnidadOrganizacional else None
                        })
                    elif asignacion.id_UnidadOrganizacional:
                        info_asignacion.update({
                            'ubicacion_id': asignacion.id_UnidadOrganizacional.id_unidad,
                            'ubicacion_nombre': asignacion.id_UnidadOrganizacional.nombre
                        })
                    
                    asignaciones_bien.append(info_asignacion)
                
                if asignaciones_bien:
                    self.asignaciones[str(bien.id_bienes)] = asignaciones_bien

            self.asignaciones_json = json.dumps(self.asignaciones)
            
            # Configurar el queryset y la función de etiqueta
            self.fields['bien_id'].queryset = bienes_disponibles
            self.fields['bien_id'].label_from_instance = self.get_bien_label

    def get_bien_label(self, bien):
        asignacion = bien.asignaciondebienes_set.filter(
            fecha_fin_temporal__isnull=True
        ).first()
        
        ubicacion = ""
        if asignacion:
            if asignacion.id_departamentos:
                ubicacion = f"Dpto: {asignacion.id_departamentos.nombre_departamento}"
                if asignacion.id_departamentos.UnidadOrganizacional:
                    ubicacion += f" - Unidad: {asignacion.id_departamentos.UnidadOrganizacional.nombre}"
            elif asignacion.id_UnidadOrganizacional:
                ubicacion = f"Unidad: {asignacion.id_UnidadOrganizacional.nombre}"
        
        return f"{bien.nombre} - {bien.numero_de_identificacion} - {ubicacion}"
    


class CrearSolicitudTemporalForm(forms.ModelForm):
    descripcion_bien = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Describa detalladamente el bien y el motivo del traslado temporal'
        }),
        label="Descripción de la solicitud",
        help_text="Indique el bien, el destino y el motivo del traslado temporal"
    )

    class Meta:
        model = Solicitudes
        fields = ['descripcion_bien']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_descripcion_bien(self):
        descripcion = self.cleaned_data.get('descripcion_bien')
        
        if not descripcion:
            raise forms.ValidationError(
                "La descripción es obligatoria."
            )
        
        if len(descripcion.strip()) < 10:
            raise forms.ValidationError(
                "Por favor, proporcione una descripción más detallada de la solicitud. "
                "Incluya el bien, el destino y el motivo del traslado temporal."
            )
        
        return descripcion

    def save(self, commit=True):
        solicitud = super().save(commit=False)
        
        # Asignar la descripción al campo correcto del modelo
        solicitud.descripcion = self.cleaned_data['descripcion_bien']
        
        if self.user:
            solicitud.usuario_id = self.user
            if self.user.id_departamentos:
                solicitud.departamento_solicitante = self.user.id_departamentos
                solicitud.UnidadOrganizacional_solicitante = None
            elif self.user.id_unidadOrganizacional:
                solicitud.UnidadOrganizacional_solicitante = self.user.id_unidadOrganizacional
                solicitud.departamento_solicitante = None
        
        if commit:
            solicitud.save()
        
        return solicitud
    


class ProcesarSolicitudTemporalForm(forms.ModelForm):
    fecha_inicio = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label='Fecha de Inicio',
        required=True
    )
    fecha_fin = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label='Fecha de Fin',
        required=True
    )

    class Meta:
        model = Solicitudes
        fields = ['bien_id', 'fecha_inicio', 'fecha_fin']
        widgets = {
            'bien_id': forms.Select(attrs={
                'class': 'form-control select2',
                'style': 'width: 100%',
                'data-placeholder': 'Seleccione un bien'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            logger.debug(f"Inicializando formulario para solicitud ID: {self.instance.pk}")
            
            try:
                departamento_mantenimiento = Departamentos.objects.get(nombre_departamento='Bienes en Mantenimiento')
            except Departamentos.DoesNotExist:
                departamento_mantenimiento = None

            # Query de bienes disponibles
            bienes_disponibles = Bienes.objects.filter(
                Q(asignaciondebienes__cantidad_asignada__gt=0),
                condicion='Operativo'
            ).exclude(
                Q(asignaciondebienes__fecha_fin_temporal__isnull=False) &
                Q(asignaciondebienes__fecha_fin_temporal__gte=timezone.now().date())
            ).select_related(
                'stock'
            ).prefetch_related(
                'asignaciondebienes_set',
                'asignaciondebienes_set__id_departamentos',
                'asignaciondebienes_set__id_UnidadOrganizacional',
                'asignaciondebienes_set__id_departamentos__UnidadOrganizacional'
            )

            if departamento_mantenimiento:
                bienes_disponibles = bienes_disponibles.exclude(
                    asignaciondebienes__id_departamentos=departamento_mantenimiento
                )

            # Excluir ubicación actual del solicitante
            if self.instance.departamento_solicitante:
                bienes_disponibles = bienes_disponibles.exclude(
                    asignaciondebienes__id_departamentos=self.instance.departamento_solicitante,
                    asignaciondebienes__fecha_fin_temporal__isnull=True
                )
            elif self.instance.UnidadOrganizacional_solicitante:
                bienes_disponibles = bienes_disponibles.exclude(
                    asignaciondebienes__id_UnidadOrganizacional=self.instance.UnidadOrganizacional_solicitante,
                    asignaciondebienes__fecha_fin_temporal__isnull=True
                )

            bienes_disponibles = bienes_disponibles.distinct()

            # Mantener el bien seleccionado si existe
            if self.instance.bien_id:
                bienes_disponibles = (
                    bienes_disponibles | Bienes.objects.filter(pk=self.instance.bien_id.pk)
                ).distinct()

            self.fields['bien_id'].queryset = bienes_disponibles
            self.fields['bien_id'].label_from_instance = self.get_bien_label

    def get_bien_label(self, bien):
        """Genera una etiqueta descriptiva para el bien que incluye su ubicación actual"""
        asignacion = bien.asignaciondebienes_set.filter(
            fecha_fin_temporal__isnull=True
        ).first()
        
        ubicacion = "Sin ubicación"
        if asignacion:
            if asignacion.id_departamentos:
                ubicacion = f"Ubicación: Departamento - {asignacion.id_departamentos.nombre_departamento}"
                if asignacion.id_departamentos.UnidadOrganizacional:
                    ubicacion += f" | Unidad Org. - {asignacion.id_departamentos.UnidadOrganizacional.nombre}"
            elif asignacion.id_UnidadOrganizacional:
                ubicacion = f"Ubicación: Unidad Org. - {asignacion.id_UnidadOrganizacional.nombre}"
        
        return f"{bien.nombre} ({bien.numero_de_identificacion}) | {ubicacion}"

    def clean(self):
        cleaned_data = super().clean()
        fecha_inicio = cleaned_data.get('fecha_inicio')
        fecha_fin = cleaned_data.get('fecha_fin')
        bien = cleaned_data.get('bien_id')
        action = self.data.get('action')

        # Validaciones específicas según la acción
        if action == 'aprobar':
            if not bien:
                raise forms.ValidationError({
                    'bien_id': 'Debe seleccionar un bien para aprobar la solicitud.'
                })

            if not fecha_inicio or not fecha_fin:
                raise forms.ValidationError('Las fechas de inicio y fin son requeridas.')

            if fecha_inicio and fecha_fin:
                # Validar que fecha inicio no sea anterior a hoy
                if fecha_inicio < timezone.now().date():
                    raise forms.ValidationError({
                        'fecha_inicio': 'La fecha de inicio no puede ser anterior a hoy'
                    })

                # Validar que fecha fin sea posterior a fecha inicio
                if fecha_fin <= fecha_inicio:
                    raise forms.ValidationError({
                        'fecha_fin': 'La fecha de fin debe ser posterior a la fecha de inicio'
                    })

                # Validar período máximo de 60 días
                dias_diferencia = (fecha_fin - fecha_inicio).days
                if dias_diferencia > 60:
                    raise forms.ValidationError({
                        'fecha_fin': 'El período de traslado temporal no puede ser mayor a 60 días'
                    })

                # Verificar traslados existentes
                if bien:
                    traslados_existentes = AsignacionDeBienes.objects.filter(
                        id_bienes=bien,
                        fecha_fin_temporal__gte=timezone.now().date()
                    ).exclude(
                        Q(fecha_fin_temporal__lt=fecha_inicio) |
                        Q(fecha_de_asignacion__gt=fecha_fin)
                    )

                    if traslados_existentes.exists():
                        raise forms.ValidationError(
                            'Ya existe un traslado temporal activo para este bien en el período seleccionado'
                        )

        return cleaned_data
        
from django.db.models import Q
class SolicitudNuevoBienForm(forms.ModelForm):
    descripcion = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Describa el bien que necesita, sus características y justifique su solicitud'
        }),
        help_text='Por favor, detalle qué tipo de bien necesita y por qué es necesario.'
    )
    
    class Meta:
        model = Solicitudes
        fields = ['descripcion']


class ProcesarNuevoBienForm(forms.ModelForm):
    bien_id = forms.ModelChoiceField(
        queryset=Bienes.objects.none(),
        label="Bien a asignar",
        widget=forms.Select(attrs={
            'class': 'form-control select2',
            'style': 'width: 100%',
            'data-placeholder': 'Seleccione un bien para asignar'
        }),
        required=False
    )
    
    class Meta:
        model = Solicitudes
        fields = ['bien_id']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Depuración inicial
        logger.debug("=== INICIANDO FILTRADO DE BIENES ===")
        
        # Obtener todos los bienes inicialmente
        todos_bienes = Bienes.objects.filter(condicion='Operativo')
        logger.debug(f"Total de bienes operativos: {todos_bienes.count()}")
        
        # Filtrar paso a paso
        bienes_query = Bienes.objects.filter(condicion='Operativo')
        logger.debug(f"1. Bienes operativos: {bienes_query.count()}")
        
        # Verificar cada bien individualmente
        available_bienes = []
        for bien in bienes_query:
            logger.debug(f"\nVerificando bien: {bien.nombre} (ID: {bien.id_bienes})")
            
            try:
                stock = Stock.objects.get(bien_id=bien)
                logger.debug(f"Stock encontrado - Disponible: {stock.cantidad_disponible}, "
                           f"Resguardada: {stock.cantidad_resguardada}, "
                           f"Desincorporada: {stock.cantidad_desincorporada}, "
                           f"Prestada: {stock.cantidad_prestada}")
                
                # Verificar asignaciones
                tiene_asignacion = AsignacionDeBienes.objects.filter(id_bienes=bien).exists()
                logger.debug(f"Tiene asignación: {tiene_asignacion}")
                
                # Verificar solicitudes pendientes
                tiene_solicitud = Solicitudes.objects.filter(
                    bien_id=bien,
                    estado_solicitud='pendiente'
                ).exists()
                logger.debug(f"Tiene solicitud pendiente: {tiene_solicitud}")
                
                # Verificar si el bien está realmente disponible
                if (stock.cantidad_disponible > 0 and
                    stock.cantidad_resguardada == 0 and
                    stock.cantidad_desincorporada == 0 and
                    stock.cantidad_prestada == 0 and
                    not tiene_asignacion and
                    not tiene_solicitud):
                    available_bienes.append(bien.id_bienes)
                    logger.debug("✓ Bien disponible para asignación")
                else:
                    logger.debug("✗ Bien no disponible para asignación")
            
            except Stock.DoesNotExist:
                logger.debug("✗ No se encontró stock para este bien")
                continue
        
        # Asignar los bienes filtrados al queryset del campo
        self.fields['bien_id'].queryset = Bienes.objects.filter(
            id_bienes__in=available_bienes
        )
        
        logger.debug(f"\nTotal de bienes disponibles para asignación: {len(available_bienes)}")
        for bien in self.fields['bien_id'].queryset:
            logger.debug(f"- {bien.nombre} (ID: {bien.id_bienes})")
        
        logger.debug("=== FIN DEL FILTRADO DE BIENES ===")
    
    def clean(self):
        cleaned_data = super().clean()
        action = self.data.get('action')
        bien_id = cleaned_data.get('bien_id')
        
        if action == 'aprobar' and not bien_id:
            raise forms.ValidationError({
                'bien_id': 'Este campo es requerido para aprobar la solicitud.'
            })
        
        if bien_id:
            # Verificar nuevamente la disponibilidad del bien
            try:
                stock = Stock.objects.get(bien_id=bien_id)
                if stock.cantidad_disponible <= 0:
                    raise forms.ValidationError({
                        'bien_id': 'Este bien ya no está disponible.'
                    })
                if stock.cantidad_resguardada > 0:
                    raise forms.ValidationError({
                        'bien_id': 'Este bien está en resguardo y no puede ser asignado.'
                    })
                if AsignacionDeBienes.objects.filter(id_bienes=bien_id).exists():
                    raise forms.ValidationError({
                        'bien_id': 'Este bien ya está asignado.'
                    })
            except Stock.DoesNotExist:
                raise forms.ValidationError({
                    'bien_id': 'No se encontró información de stock para este bien.'
                })
        
        return cleaned_data




class TipoBienForm(forms.ModelForm):
    nombre = forms.CharField(
        label=_('Nombre del Tipo de Bien'),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ingrese el nombre del tipo de bien',
            'autocomplete': 'off',
            'data-bs-toggle': 'tooltip',
            'title': 'Ingrese un nombre descriptivo y único'
        }),
        help_text=_('El nombre debe ser único y descriptivo'),
        error_messages={
            'required': _('El nombre es obligatorio'),
            'unique': _('Ya existe un tipo de bien con este nombre')
        }
    )

    descripcion = forms.CharField(
        label=_('Descripción'),
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Describa el tipo de bien...',
            'rows': 3,
            'style': 'resize: vertical;',
            'data-bs-toggle': 'tooltip',
            'title': 'Proporcione una descripción detallada'
        }),
        help_text=_('Proporcione una descripción clara y detallada'),
        required=False
    )

    stock_minimo = forms.IntegerField(
        label=_('Stock Mínimo'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '0',
            'step': '1',
            'data-bs-toggle': 'tooltip',
            'title': 'Cantidad mínima requerida en inventario'
        }),
        validators=[MinValueValidator(0)],
        help_text=_('Cantidad mínima que debe mantenerse en inventario'),
        error_messages={
            'required': _('Debe especificar un stock mínimo'),
            'min_value': _('El stock mínimo no puede ser negativo'),
            'invalid': _('Ingrese un número válido')
        }
    )

    stock_maximo = forms.IntegerField(
        label=_('Stock Máximo'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '0',
            'step': '1',
            'data-bs-toggle': 'tooltip',
            'title': 'Cantidad máxima permitida en inventario'
        }),
        validators=[MinValueValidator(0)],
        help_text=_('Cantidad máxima permitida en inventario (opcional)'),
        required=False,
        error_messages={
            'min_value': _('El stock máximo no puede ser negativo'),
            'invalid': _('Ingrese un número válido')
        }
    )

    class Meta:
        model = TipoBien
        fields = ['nombre', 'descripcion', 'stock_minimo', 'stock_maximo']

    def clean_nombre(self):
        """Validación personalizada para el campo nombre"""
        nombre = self.cleaned_data.get('nombre')
        if nombre:
            # Convertir a mayúsculas y eliminar espacios extras
            nombre = ' '.join(nombre.upper().split())
            
            # Verificar si ya existe (excluir la instancia actual en caso de edición)
            exists_query = TipoBien.objects.filter(nombre=nombre)
            if self.instance.pk:
                exists_query = exists_query.exclude(pk=self.instance.pk)
            
            if exists_query.exists():
                raise forms.ValidationError(_('Ya existe un tipo de bien con este nombre'))

        return nombre

    def clean_descripcion(self):
        """Validación personalizada para el campo descripción"""
        descripcion = self.cleaned_data.get('descripcion')
        if descripcion:
            # Capitalizar la primera letra de cada oración
            descripcion = '. '.join(s.capitalize() for s in descripcion.split('. '))
        return descripcion

    def clean(self):
        """Validación general del formulario"""
        cleaned_data = super().clean()
        stock_minimo = cleaned_data.get('stock_minimo')
        stock_maximo = cleaned_data.get('stock_maximo')
        
        if stock_minimo is not None and stock_maximo is not None:
            if stock_maximo < stock_minimo:
                raise forms.ValidationError({
                    'stock_maximo': _('El stock máximo debe ser mayor o igual que el stock mínimo')
                })
            
            # Validación adicional para valores razonables
            if stock_minimo > 9999:
                raise forms.ValidationError({
                    'stock_minimo': _('El stock mínimo parece ser muy alto. Por favor, verifique el valor')
                })
            
            if stock_maximo > 99999:
                raise forms.ValidationError({
                    'stock_maximo': _('El stock máximo parece ser muy alto. Por favor, verifique el valor')
                })

        return cleaned_data

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Agregar clases y atributos comunes a todos los campos
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({
                    'class': field.widget.attrs.get('class', '') + ' form-control',
                })

            # Marcar campos requeridos
            if field.required:
                field.label = f"{field.label} *"

        # Personalizar mensajes de error
        self.error_messages = {
            'required': _('Este campo es obligatorio.'),
            'invalid': _('Valor no válido.'),
        }

class GrupoForm(forms.ModelForm):
    class Meta:
        model = Grupo
        fields = ['codigo', 'nombre', 'descripcion']
        widgets = {
            'codigo': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'pattern': '[0-9]*',
                    'maxlength': '2',
                    'style': 'font-family: monospace;'
                }
            )
        }

    def clean_codigo(self):
        codigo = self.cleaned_data.get('codigo', '')
        
        if not codigo:
            raise forms.ValidationError("El código es requerido.")
        
        # Formatear el código con ceros a la izquierda
        codigo_formateado = codigo.zfill(2)
        
        # Verificar si el código ya existe
        existe = Grupo.objects.filter(codigo=codigo_formateado)
        if self.instance.pk:  # Si estamos editando
            existe = existe.exclude(pk=self.instance.pk)
            
        if existe.exists():
            raise forms.ValidationError(f"Ya existe un grupo con el código {codigo_formateado}")
            
        return codigo_formateado

    def clean(self):
        cleaned_data = super().clean()
        
        # Verificar el límite de grupos solo al crear uno nuevo
        if not self.instance.pk:  # Si es una creación nueva
            total_grupos = Grupo.objects.count()
            if total_grupos >= 1:
                raise forms.ValidationError(
                    "No se pueden crear más grupos. El límite máximo es de 1 grupo."
                )
                
        return cleaned_data

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Si hay una instancia (edición), formateamos el código
        if self.instance and self.instance.codigo:
            self.initial['codigo'] = self.instance.codigo.zfill(2)
        
        # Personalizar mensajes de error
        self.fields['codigo'].error_messages = {
            'required': 'El código es requerido.',
            'invalid': 'Ingrese un código válido (solo números).'
        }



class SubgrupoForm(forms.ModelForm):
    class Meta:
        model = Subgrupo
        fields = ['id_grupo', 'codigo', 'nombre', 'descripcion']
        widgets = {
            'id_grupo': forms.Select(attrs={
                'class': 'form-control'
            }),
            'codigo': forms.TextInput(attrs={
                'class': 'form-control',
                'pattern': '[0-9]*',
                'maxlength': '2',
                'style': 'font-family: monospace;'
            }),
            'nombre': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'descripcion': forms.TextInput(attrs={
                'class': 'form-control'
            }),
        }

    def clean_codigo(self):
        codigo = self.cleaned_data.get('codigo', '')
        grupo = self.cleaned_data.get('id_grupo')
        
        if not codigo:
            raise forms.ValidationError("El código es requerido.")
            
        codigo = str(codigo).zfill(2)
        
        # Verificar código único dentro del mismo grupo
        existe = Subgrupo.objects.filter(codigo=codigo, id_grupo=grupo)
        if self.instance.pk:
            existe = existe.exclude(pk=self.instance.pk)
            
        if existe.exists():
            raise forms.ValidationError(f"Ya existe un subgrupo con el código {codigo} en este grupo")
            
        return codigo

    def clean_nombre(self):
        nombre = self.cleaned_data.get('nombre')
        grupo = self.cleaned_data.get('id_grupo')
        
        if not nombre:
            raise forms.ValidationError("El nombre es requerido.")
            
        # Verificar nombre único dentro del mismo grupo
        existe = Subgrupo.objects.filter(nombre__iexact=nombre, id_grupo=grupo)
        if self.instance.pk:
            existe = existe.exclude(pk=self.instance.pk)
            
        if existe.exists():
            raise forms.ValidationError(f"Ya existe un subgrupo con el nombre '{nombre}' en este grupo")
            
        return nombre



class SeccionSubgrupoForm(forms.ModelForm):
    class Meta:
        model = SeccionSubgrupo
        fields = ['id_subgrupo', 'codigo', 'nombre', 'descripcion']
        widgets = {
            'id_subgrupo': forms.Select(attrs={
                'class': 'form-control'
            }),
            'codigo': forms.TextInput(attrs={
                'class': 'form-control',
                'pattern': '[0-9]*',
                'maxlength': '2',
                'style': 'font-family: monospace;'
            }),
            'nombre': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'descripcion': forms.TextInput(attrs={
                'class': 'form-control'
            }),
        }

    def clean_codigo(self):
        codigo = self.cleaned_data.get('codigo', '')
        subgrupo = self.cleaned_data.get('id_subgrupo')
        
        if not codigo:
            raise forms.ValidationError("El código es requerido.")
            
        codigo = str(codigo).zfill(2)
        
        # Verificar código único dentro del mismo subgrupo
        existe = SeccionSubgrupo.objects.filter(codigo=codigo, id_subgrupo=subgrupo)
        if self.instance.pk:
            existe = existe.exclude(pk=self.instance.pk)
            
        if existe.exists():
            raise forms.ValidationError(f"Ya existe una sección con el código {codigo} en este subgrupo")
            
        return codigo

    def clean_nombre(self):
        nombre = self.cleaned_data.get('nombre')
        subgrupo = self.cleaned_data.get('id_subgrupo')
        
        if not nombre:
            raise forms.ValidationError("El nombre es requerido.")
            
        # Verificar nombre único dentro del mismo subgrupo
        existe = SeccionSubgrupo.objects.filter(nombre__iexact=nombre, id_subgrupo=subgrupo)
        if self.instance.pk:
            existe = existe.exclude(pk=self.instance.pk)
            
        if existe.exists():
            raise forms.ValidationError(f"Ya existe una sección con el nombre '{nombre}' en este subgrupo")
            
        return nombre



    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Personalizar mensajes de error
        self.fields['codigo'].error_messages = {
            'required': 'El código es requerido.',
            'invalid': 'Ingrese un código válido (solo números).'
        }
        self.fields['nombre'].error_messages = {
            'required': 'El nombre es requerido.'
        }
    




class FiltroFechaForm(forms.Form):
    fecha_inicio = forms.DateField(
        label='Fecha de Inicio',
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    fecha_fin = forms.DateField(
        label='Fecha de Fin',
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    department_id = forms.ChoiceField(
        label='Departamento',
        required=False,
        choices=[('todos', 'Todos los departamentos')],
        initial='todos'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Obtener todos los departamentos y agregarlos a las opciones
        departamentos = Departamentos.objects.all().order_by('nombre_departamento')
        self.fields['department_id'].choices += [
            (dept.id_departamentos, dept.nombre_departamento)
            for dept in departamentos
        ]


class CrearSolicitudMantenimientoForm(forms.ModelForm):
    descripcion = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 4, 
            'class': 'form-control',
            'placeholder': 'Describe el problema y el tipo de mantenimiento requerido'
        }),
        help_text='Describe el problema y el tipo de mantenimiento requerido'
    )
    
    class Meta:
        model = Solicitudes
        fields = ['bien_id', 'descripcion']
        widgets = {
            'bien_id': forms.Select(attrs={'class': 'form-control'})
        }

    def __init__(self, user=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            logger.debug(f"Inicializando formulario para usuario: {user.username}")
            logger.debug(f"Departamento: {user.id_departamentos}")
            logger.debug(f"Unidad Organizacional: {user.id_unidadOrganizacional}")
            
            # Base query para bienes asignados
            bienes_query = Bienes.objects.filter(
                asignaciondebienes__fecha_fin_temporal__isnull=True
            )
            
            if user.id_departamentos:
                # Si el usuario pertenece a un departamento
                logger.debug(f"Filtrando por departamento: {user.id_departamentos}")
                bienes_query = bienes_query.filter(
                    asignaciondebienes__id_departamentos=user.id_departamentos
                )
            elif user.id_unidadOrganizacional:
                # Si el usuario pertenece a una unidad organizacional
                logger.debug(f"Filtrando por unidad organizacional: {user.id_unidadOrganizacional}")
                bienes_query = bienes_query.filter(
                    asignaciondebienes__id_UnidadOrganizacional=user.id_unidadOrganizacional
                )
            
            # Aplicar filtros adicionales
            bienes_query = bienes_query.filter(
                condicion='Operativo'
            ).exclude(
                # Excluir bienes que ya tienen solicitudes de mantenimiento pendientes
                id_bienes__in=Solicitudes.objects.filter(
                    estado_solicitud='pendiente',
                    id_tipos_de_solicitud__nombre='Mantenimiento'
                ).values('bien_id')
            ).distinct()
            
            logger.debug(f"Total de bienes encontrados: {bienes_query.count()}")
            self.fields['bien_id'].queryset = bienes_query


class ProcesarSolicitudMantenimientoForm(forms.ModelForm):
    motivo_rechazo = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'style': 'display: none;'  # Se mostrará/ocultará con JavaScript
        }),
        required=False
    )

    class Meta:
        model = Solicitudes
        fields = ['bien_id', 'motivo_rechazo']
        widgets = {
            'bien_id': forms.Select(attrs={'class': 'form-control'})
        }

    def clean(self):
        cleaned_data = super().clean()
        action = self.data.get('action')
        
        if action == 'rechazar' and not cleaned_data.get('motivo_rechazo'):
            raise forms.ValidationError('Debe proporcionar un motivo para rechazar la solicitud.')
        
        if action == 'aprobar' and not cleaned_data.get('bien_id'):
            raise forms.ValidationError('Debe seleccionar un bien')
        
        return cleaned_data
    
    
class TiposDeSolicitudForm(forms.ModelForm):
    class Meta:
        model = TiposDeSolicitud
        fields = ['nombre', 'descripcion']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingrese el nombre del tipo de solicitud'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Ingrese una descripción',
                'rows': 3
            })
        }
        labels = {
            'nombre': 'Nombre',
            'descripcion': 'Descripción'
        }

    def clean_nombre(self):
        nombre = self.cleaned_data.get('nombre')
        if nombre:
            # Capitalizar primera letra de cada palabra
            nombre = nombre.title()
        return nombre
    
class ConceptoDeMovimientoForm(forms.ModelForm):
    class Meta:
        model = ConceptoDeMovimiento
        fields = ['codigo', 'nombre', 'descripcion']
        widgets = {
            'codigo': forms.TextInput(attrs={
                'class': 'form-control',
                'pattern': '[0-9]*',
                'maxlength': '2',
                'style': 'font-family: monospace;'
            }),
            'nombre': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'descripcion': forms.TextInput(attrs={
                'class': 'form-control'
            }),
        }

    def clean_codigo(self):
        codigo = self.cleaned_data.get('codigo', '')
        
        if not codigo:
            raise forms.ValidationError("El código es requerido.")
            
        codigo = str(codigo).zfill(2)
        
        # Verificar código único
        existe = ConceptoDeMovimiento.objects.filter(codigo=codigo)
        if self.instance.pk:
            existe = existe.exclude(pk=self.instance.pk)
            
        if existe.exists():
            raise forms.ValidationError(f"Ya existe un concepto de movimiento con el código {codigo}")
            
        return codigo

    def clean_nombre(self):
        nombre = self.cleaned_data.get('nombre')
        
        if not nombre:
            raise forms.ValidationError("El nombre es requerido.")
            
        # Verificar nombre único (case-insensitive)
        existe = ConceptoDeMovimiento.objects.filter(nombre__iexact=nombre)
        if self.instance.pk:
            existe = existe.exclude(pk=self.instance.pk)
            
        if existe.exists():
            raise forms.ValidationError(f"Ya existe un concepto de movimiento con el nombre '{nombre}'")
            
        return nombre

    def clean(self):
        cleaned_data = super().clean()
        
        if not self.instance.pk:  # Solo al crear nuevo concepto
            # Verificar límite de conceptos
            total_conceptos = ConceptoDeMovimiento.objects.count()
            if total_conceptos >= 2:
                raise forms.ValidationError(
                    "No se pueden crear más conceptos de movimiento. El límite máximo es de 2 conceptos."
                )
        
        return cleaned_data

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Si hay una instancia (edición), formateamos el código
        if self.instance and self.instance.codigo:
            self.initial['codigo'] = self.instance.codigo.zfill(2)
            
        # Personalizar mensajes de error
        self.fields['codigo'].error_messages = {
            'required': 'El código es requerido.',
            'invalid': 'Ingrese un código válido (solo números).'
        }
        self.fields['nombre'].error_messages = {
            'required': 'El nombre es requerido.'
        }



class PerfilUsuarioForm(forms.ModelForm):
    confirmar_email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = Usuario
        fields = ['nombres', 'apellidos', 'email', 'telefono']
        widgets = {
            'nombres': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingrese sus nombres'
            }),
            'apellidos': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingrese sus apellidos'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingrese su correo electrónico'
            }),
            'telefono': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingrese su número de teléfono'
            })
        }
        
    def clean_telefono(self):
        telefono = self.cleaned_data.get('telefono')
        if telefono:
            # Eliminar espacios y guiones
            telefono = re.sub(r'[\s-]', '', telefono)
            # Verificar que solo contenga números
            if not telefono.isdigit():
                raise ValidationError('El teléfono solo debe contener números')
            # Verificar longitud
            if len(telefono) < 10 or len(telefono) > 15:
                raise ValidationError('El número de teléfono debe tener entre 10 y 15 dígitos')
        return telefono

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        confirmar_email = cleaned_data.get('confirmar_email')

        if email and confirmar_email and email != confirmar_email:
            raise ValidationError('Los correos electrónicos no coinciden')
        
        return cleaned_data

class CambiarPasswordForm(forms.Form):
    password_actual = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label='Contraseña actual'
    )
    password_nuevo = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label='Nueva contraseña',
        min_length=8
    )
    confirmar_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label='Confirmar nueva contraseña'
    )

    def clean(self):
        cleaned_data = super().clean()
        password_nuevo = cleaned_data.get('password_nuevo')
        confirmar_password = cleaned_data.get('confirmar_password')

        if password_nuevo and confirmar_password:
            if password_nuevo != confirmar_password:
                raise ValidationError('Las contraseñas no coinciden')
            
            # Validar complejidad de la contraseña
            if not re.search(r'[A-Z]', password_nuevo):
                raise ValidationError('La contraseña debe contener al menos una letra mayúscula')
            if not re.search(r'[a-z]', password_nuevo):
                raise ValidationError('La contraseña debe contener al menos una letra minúscula')
            if not re.search(r'\d', password_nuevo):
                raise ValidationError('La contraseña debe contener al menos un número')
            if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password_nuevo):
                raise ValidationError('La contraseña debe contener al menos un carácter especial')

        return cleaned_data

class CambiarPasswordForm(forms.Form):
    password_actual = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label='Contraseña actual'
    )
    password_nuevo = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label='Nueva contraseña',
        min_length=8
    )
    confirmar_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label='Confirmar nueva contraseña'
    )

    def clean(self):
        cleaned_data = super().clean()
        password_nuevo = cleaned_data.get('password_nuevo')
        confirmar_password = cleaned_data.get('confirmar_password')

        if password_nuevo and confirmar_password:
            if password_nuevo != confirmar_password:
                raise ValidationError('Las contraseñas no coinciden')
            
            # Validar complejidad de la contraseña
            if not re.search(r'[A-Z]', password_nuevo):
                raise ValidationError('La contraseña debe contener al menos una letra mayúscula')
            if not re.search(r'[a-z]', password_nuevo):
                raise ValidationError('La contraseña debe contener al menos una letra minúscula')
            if not re.search(r'\d', password_nuevo):
                raise ValidationError('La contraseña debe contener al menos un número')
            if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password_nuevo):
                raise ValidationError('La contraseña debe contener al menos un carácter especial')

        return cleaned_data
