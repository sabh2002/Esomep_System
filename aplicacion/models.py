from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from datetime import datetime, timedelta
from django.db.models import Q
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from decimal import Decimal
import logging
from django.db import transaction
from django.contrib import messages
from django.shortcuts import redirect, render
from django.http import JsonResponse
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.contrib.auth.models import Permission
from django.contrib.auth.models import Group

logger = logging.getLogger(__name__)

#
class RolDelUsuario(models.Model):
    ROLES = (
        ('ADMIN_BIENES', 'Administrador de Bienes'),
        ('USUARIO_ESTANDAR', 'Usuario Estándar'),
    )
    
    id_rol_del_usuario = models.AutoField(primary_key=True)
    nombre_rol = models.CharField(max_length=20, choices=ROLES, unique=True, null=True)
    descripcion = models.CharField(max_length=255)

    class Meta:
        db_table = 'roles_usuario'

    def __str__(self):
        return self.get_nombre_rol_display()

#
class TiposDeSolicitud(models.Model):
    id_tipos_de_solicitud = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50)
    descripcion = models.CharField(max_length=255)

    class Meta:
        db_table = 'tipos_solicitud'

    def __str__(self):
        return self.nombre


#
class UnidadOrganizacional(models.Model):
    """Tabla para almacenar unidades organizacionales (Gerencias, Auditoría, Presidencia, etc.)"""
    id_unidad = models.AutoField(primary_key=True)
    codigo = models.CharField(max_length=50, unique=True)
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.CharField(max_length=255)
    
    class Meta:
        db_table = 'unidades_organizacionales'
        verbose_name = 'Unidad Organizacional'
        verbose_name_plural = 'Unidades Organizacionales'
        ordering = ['codigo']

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"

    def get_bienes_total(self):
        return Bienes.objects.filter(
            Q(asignaciondebienes__id_UnidadOrganizacional=self) |
            Q(asignaciondebienes__id_departamentos__UnidadOrganizacional=self)
        ).distinct()
#
class Departamentos(models.Model):
    id_departamentos = models.AutoField(primary_key=True)
    UnidadOrganizacional = models.ForeignKey('UnidadOrganizacional', on_delete=models.CASCADE, null=True, blank=True)
    codigo_departamento = models.CharField(max_length=50)
    nombre_departamento = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=255)

    class Meta:
        db_table = 'departamentos'
        unique_together = [
            ('UnidadOrganizacional', 'codigo_departamento'),
            ('UnidadOrganizacional', 'nombre_departamento')
        ]
        ordering = ['UnidadOrganizacional', 'codigo_departamento']

    def __str__(self):
        return f"{self.codigo_departamento} - {self.nombre_departamento}"

    def get_bienes(self):
        """Obtiene los bienes asignados al departamento"""
        return self.asignaciondebienes_set.all()


# 

class Grupo(models.Model):
        id_grupo = models.AutoField(primary_key=True)
        codigo = models.CharField(
            max_length=10,
            validators=[
                RegexValidator(
                    regex='^[0-9]+$',
                    message='El código debe contener solo números',
                    code='invalid_codigo'
                )
            ]
        )
        nombre = models.CharField(max_length=100)
        descripcion = models.CharField(max_length=255)


        def save(self, *args, **kwargs):
            # Asegurar que el código tenga el formato correcto antes de guardar
            if self.codigo:
                self.codigo = self.codigo.zfill(2)
            super().save(*args, **kwargs)

        def __str__(self):
            return f"{self.codigo.zfill(2)} - {self.nombre}"

        class Meta:
            db_table = 'grupos'
            ordering = ['codigo']

#
class Subgrupo(models.Model):
    id_subgrupo = models.AutoField(primary_key=True)
    id_grupo = models.ForeignKey(Grupo, on_delete=models.CASCADE)
    codigo = models.CharField(max_length=10)
    nombre = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"
    
    class Meta:
        db_table = 'subgrupos'
    

#
class SeccionSubgrupo(models.Model):
    id_seccion_subgrupo = models.AutoField(primary_key=True)
    id_subgrupo = models.ForeignKey(Subgrupo, on_delete=models.CASCADE)
    codigo = models.CharField(max_length=10)
    nombre = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"
    
    class Meta:
        db_table = 'secciones_subgrupo'

#
class ConceptoDeMovimiento(models.Model):
    id_concepto_de_movimiento = models.AutoField(primary_key=True)
    codigo = models.CharField(max_length=10)
    nombre = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"
    
    class Meta:
        db_table = 'conceptos_movimiento'


class TipoBien(models.Model):
    id_tipo_bien = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(null=True, blank=True)
    stock_minimo = models.IntegerField(default=1)
    stock_maximo = models.IntegerField(null=True, blank=True)

    def clean(self):
        if self.stock_maximo and self.stock_minimo and self.stock_maximo < self.stock_minimo:
            raise ValidationError({
                'stock_maximo': 'El stock máximo debe ser mayor que el stock mínimo'
            })

    def __str__(self):
        return self.nombre
    
    def get_total_bienes(self):
        return self.bienes_set.count()
    
    def get_stock_actual(self):
        from django.db.models import Sum
        stock = Stock.objects.filter(
            bien_id__tipo_bien=self
        ).aggregate(
            disponible=Sum('cantidad_disponible'),
            asignado=Sum('cantidad_asignada'),
            prestado=Sum('cantidad_prestada'),
            mantenimiento=Sum('cantidad_en_mantenimiento')
        )
        return stock
    
    class Meta:
        db_table = 'tipos_bien'
        verbose_name = 'Tipo de Bien'
        verbose_name_plural = 'Tipos de Bienes'
        ordering = ['nombre']
#
class Bienes(models.Model):
    CONDICION_CHOICES = [
        ('Operativo', 'Operativo'),
        ('No', 'No Operativo'),
    ]
    id_bienes = models.AutoField(primary_key=True)
    id_grupo = models.ForeignKey(Grupo, on_delete=models.CASCADE, null=True, blank=True)
    id_subgrupo = models.ForeignKey(Subgrupo, on_delete=models.CASCADE, null=True, blank=True)
    id_seccion_subgrupo = models.ForeignKey(SeccionSubgrupo, on_delete=models.CASCADE, null=True, blank=True)
    id_concepto_de_movimiento = models.ForeignKey(ConceptoDeMovimiento, on_delete=models.CASCADE, null=True, blank=True)
    nombre = models.CharField(max_length=100)
    numero_de_identificacion = models.CharField(
        max_length=50,
        unique=True,
        error_messages={
            'unique': 'Ya existe un bien con este número de identificación.'
        }
    )
    incorporacion = models.CharField(
        max_length=50,  # Suficientemente largo para cualquier monto
        default='0'
    )
    desincorporacion = models.CharField(
        max_length=50,  # Suficientemente largo para cualquier monto
        default='0'
    )
    condicion = models.CharField(max_length=50, null=True, blank=True, choices=CONDICION_CHOICES, default='Operativo')
    observacion = models.CharField(max_length=255)
    archivo_multimedia = models.FileField(upload_to='archivos_multimedia/', null=True, blank=True)
    fecha_de_registro = models.DateField(default=timezone.now)
    tipo_bien = models.ForeignKey(TipoBien, on_delete=models.PROTECT,  null=True, blank=True)

    def __str__(self):
        return f" {self.nombre} - {self.numero_de_identificacion}"
    
    class Meta:
        db_table = 'bienes'

    def get_ubicacion_actual(self):
        asignacion = self.asignaciondebienes_set.order_by('-fecha_de_asignacion').first()
        if asignacion:
            return asignacion.id_UnidadOrganizacional or asignacion.id_departamentos
        return None

    def get_unidad_actual(self):
        asignacion = self.asignaciondebienes_set.order_by('-fecha_de_asignacion').first()
        if asignacion:
            return asignacion.id_UnidadOrganizacional or (
                asignacion.id_departamentos.UnidadOrganizacional if asignacion.id_departamentos else None
            )
        return None

    def esta_en_mantenimiento(self):
        """Verifica si el bien está actualmente en mantenimiento"""
        return (
            self.stock.cantidad_en_mantenimiento > 0 and
            self.asignaciondebienes_set.filter(
                id_departamentos__nombre_departamento="Bienes en Mantenimiento"
            ).exists()
        )
    

    def get_departamento_nombre(self):
        asignacion = AsignacionDeBienes.objects.filter(id_bienes=self).first()
        if asignacion:
            return asignacion.id_departamentos.nombre_departamento
        return "No asignado"

    def get_departamento_actual(self):
        asignacion = self.asignaciondebienes_set.order_by('-fecha_de_asignacion').first()
        return asignacion.id_departamentos if asignacion else None

    def puede_ser_eliminado(self):
        """
        Verifica si el bien puede ser eliminado basado en:
        1. Tiempo desde su registro (menos de 48 horas)
        2. No está asignado a ningún departamento
        """
        # Convertir la fecha de registro a datetime aware
        fecha_registro_inicio = timezone.make_aware(
            datetime.combine(self.fecha_de_registro, datetime.min.time())
        )
        
        # Calcular el tiempo transcurrido
        tiempo_transcurrido = timezone.now() - fecha_registro_inicio
        
        # Verificar si tiene asignaciones
        from .models import AsignacionDeBienes
        tiene_asignacion = AsignacionDeBienes.objects.filter(id_bienes=self).exists()
        
        # Retornar True solo si han pasado menos de 48 horas y no está asignado
        return tiempo_transcurrido <= timedelta(hours=48) and not tiene_asignacion

    def get_tiempo_restante(self):
        """
        Retorna el tiempo restante en un formato detallado
        """
        fecha_registro_inicio = timezone.make_aware(
            datetime.combine(self.fecha_de_registro, datetime.min.time())
        )
        tiempo_transcurrido = timezone.now() - fecha_registro_inicio
        tiempo_restante = timedelta(hours=48) - tiempo_transcurrido
        
        if tiempo_restante.total_seconds() <= 0:
            return None
            
        # Convertir a horas, minutos y segundos
        total_segundos = int(tiempo_restante.total_seconds())
        horas = total_segundos // 3600
        minutos = (total_segundos % 3600) // 60
        segundos = total_segundos % 60
        
        return {
            'horas': horas,
            'minutos': minutos,
            'segundos': segundos,
            'total_segundos': total_segundos
        }

    def actualizar_ubicacion(self, nueva_unidad=None, nuevo_departamento=None, usuario=None):
        if nueva_unidad and nuevo_departamento:
            raise ValidationError("No se puede asignar a unidad organizacional y departamento simultáneamente")
            
        if nuevo_departamento and nueva_unidad and \
        nuevo_departamento.UnidadOrganizacional != nueva_unidad:
            raise ValidationError("El departamento debe pertenecer a la unidad organizacional seleccionada")
        
        ubicacion_anterior = self.get_ubicacion_actual()
        
        AsignacionDeBienes.objects.create(
            id_bienes=self,
            id_UnidadOrganizacional=nueva_unidad,
            id_departamentos=nuevo_departamento,
            fecha_de_asignacion=timezone.now()
        )

        tipo_evento = TiposDeEvento.objects.get(nombre="Cambio de Ubicación")
        
        HistorialBienes.objects.create(
            bien_id=self,
            fecha_evento=timezone.now(),
            id_tipos_de_evento=tipo_evento,
            descripcion=f"Cambio de ubicación de {ubicacion_anterior} a {nueva_unidad or nuevo_departamento}",
            cantidad_afectada=1,
            usuario_id=usuario,
            UnidadOrganizacional_origen=ubicacion_anterior.id_UnidadOrganizacional if hasattr(ubicacion_anterior, 'id_UnidadOrganizacional') else None,
            UnidadOrganizacional_destino=nueva_unidad,
            departamento_origen=ubicacion_anterior.id_departamentos if hasattr(ubicacion_anterior, 'id_departamentos') else None,
            departamento_destino=nuevo_departamento
        )
        
#
class Especificacion(models.Model):
    id_especificacion = models.AutoField(primary_key=True)
    id_bien = models.ForeignKey(Bienes, on_delete=models.CASCADE)
    especificacion = models.CharField(max_length=100)
    descripcion_especificacion = models.CharField(max_length=255)

    class Meta:
        db_table = 'especificaciones'
    



#
class Usuario(AbstractUser):
    # Deshabilitar campos de AbstractUser que no necesitamos
    first_name = None
    last_name = None
    date_joined = None
    groups = models.ManyToManyField(
        Group,
        verbose_name='groups',
        blank=True,
        related_name='custom_user_groups',
    )
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name='user permissions',
        blank=True,
        related_name='custom_user_permissions',
    )

    # Tus campos personalizados
    ESTADO_CHOICES = [
        ('activo', 'Activo'),
        ('bloqueado', 'Bloqueado'),
        ('eliminado', 'Eliminado')
    ]
    
    id_usuario = models.AutoField(primary_key=True)
    cedula = models.CharField(max_length=50, unique=True, null=True)
    nombres = models.CharField(max_length=50, null=True)
    apellidos = models.CharField(max_length=50, null=True)
    email = models.EmailField(unique=True, null=True)
    telefono = models.CharField(max_length=15, null=True)
    id_unidadOrganizacional = models.ForeignKey(UnidadOrganizacional, on_delete=models.SET_NULL, null=True, blank=True)
    id_departamentos = models.ForeignKey('Departamentos', on_delete=models.SET_NULL, null=True)
    id_rol_del_usuario = models.ForeignKey('RolDelUsuario', on_delete=models.SET_NULL, null=True)
    fecha_de_registro = models.DateField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='activo', null=True)
    bienes_asignados = models.ManyToManyField('Bienes', related_name='usuarios_asignados', blank=True)
    username = models.CharField(max_length=150, unique=True, null=True)
    password = models.CharField(max_length=128, null=True)
    fecha_bloqueo = models.DateTimeField(null=True, blank=True)
    fecha_eliminacion = models.DateTimeField(null=True, blank=True)

    def clean(self):
        if (self.id_unidadOrganizacional and self.id_departamentos) or \
        (not self.id_unidadOrganizacional and not self.id_departamentos):
            raise ValidationError("El usuario debe pertenecer a una unidad organizacional o a un departamento")
            
        # Solo verificar la relación si ambos campos están establecidos
        if self.id_departamentos and self.id_unidadOrganizacional and \
        self.id_departamentos.UnidadOrganizacional != self.id_unidadOrganizacional:
            raise ValidationError("El departamento debe pertenecer a la unidad organizacional seleccionada")
        
    def get_bienes_asignados(self):
        if self.id_unidadOrganizacional:
            return Bienes.objects.filter(
                asignaciondebienes__id_UnidadOrganizacional=self.id_unidadOrganizacional,
                condicion='Operativo'
            ).filter(
                Q(asignaciondebienes__fecha_fin_temporal__isnull=True) |
                Q(asignaciondebienes__fecha_fin_temporal__gt=timezone.now())
            ).distinct()  # Añadido distinct() para evitar duplicados
        elif self.id_departamentos:
            return Bienes.objects.filter(
                asignaciondebienes__id_departamentos=self.id_departamentos,
                condicion='Operativo'
            ).filter(
                Q(asignaciondebienes__fecha_fin_temporal__isnull=True) |
                Q(asignaciondebienes__fecha_fin_temporal__gt=timezone.now())
            ).distinct()  # Añadido distinct() para evitar duplicados
        return Bienes.objects.none()

    def get_bienes_count(self):
        if self.id_unidadOrganizacional:
            return AsignacionDeBienes.objects.filter(
                id_UnidadOrganizacional=self.id_unidadOrganizacional,
                id_bienes__condicion='Operativo',
                fecha_fin_temporal__isnull=True
            ).distinct().count()
        elif self.id_departamentos:
            return AsignacionDeBienes.objects.filter(
                id_departamentos=self.id_departamentos,
                id_bienes__condicion='Operativo',
                fecha_fin_temporal__isnull=True
            ).distinct().count()
        return 0
    
    def puede_asignar_bienes(self):
        return self.estado == 'activo' and self.is_active

    def get_full_name(self):
        return f"{self.nombres} {self.apellidos}"

    USERNAME_FIELD = 'cedula'
    REQUIRED_FIELDS = ['email', 'nombres', 'apellidos']

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = self.cedula
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nombres} {self.apellidos}"
    


    class Meta:
        db_table = 'usuarios'
 

#
class Solicitudes(models.Model):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('aprobada', 'Aprobada'),
        ('rechazada', 'Rechazada'),
    ]

    id_solicitudes = models.AutoField(primary_key=True)
    UnidadOrganizacional_solicitante = models.ForeignKey(
        UnidadOrganizacional, 
        on_delete=models.CASCADE, 
        related_name='solicitudes_hechas_unidad', 
        null=True, 
        blank=True
    )
    UnidadOrganizacional_destino = models.ForeignKey(
        UnidadOrganizacional, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='solicitudes_destino_unidad'
    )
    departamento_solicitante = models.ForeignKey(Departamentos, on_delete=models.CASCADE, related_name='solicitudes_hechas', null = True, blank = True)
    bien_id = models.ForeignKey(Bienes, on_delete=models.CASCADE, null=True, blank=True)
    fecha_solicitud = models.DateField(auto_now_add=True)
    id_tipos_de_solicitud = models.ForeignKey(TiposDeSolicitud, on_delete=models.CASCADE)
    estado_solicitud = models.CharField(max_length=50, choices=ESTADO_CHOICES, default='pendiente')
    cantidad_solicitada = models.IntegerField(null=True, blank=True)
    usuario_id = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    descripcion = models.TextField()
    departamento_destino = models.ForeignKey(Departamentos, on_delete=models.SET_NULL, null=True, blank=True, related_name='solicitudes_destino')
    fecha_maxima_traslado = models.DateField(null=True, blank=True)
    motivo_rechazo = models.TextField(null=True, blank=True, verbose_name='Motivo de rechazo')  

    class Meta:
        db_table = 'solicitudes'

    def __str__(self):
        return f"Solicitud {self.id_solicitudes} de {self.usuario_id} - {self.id_tipos_de_solicitud}"
    



    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)



class Notificacion(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='notificaciones', null=True )
    solicitud = models.ForeignKey(Solicitudes, on_delete=models.SET_NULL, null=True, blank=True, related_name='notificaciones')
    mensaje = models.TextField()
    fecha = models.DateTimeField(auto_now_add=True)
    leida = models.BooleanField(default=False)

    def __str__(self):
        return f"Notificación para {self.usuario}: {self.mensaje[:50]}..."
    
    class Meta:
        db_table = 'notificaciones'

#
class MovimientosBienes(models.Model):
    id = models.AutoField(primary_key=True)
    bien_id = models.ForeignKey('Bienes', on_delete=models.CASCADE)
    UnidadOrganizacional_solicitante = models.ForeignKey(
        'UnidadOrganizacional', 
        on_delete=models.CASCADE, 
        related_name='movimientos_solicitados_unidad', 
        null=True, 
        blank=True
    )
    UnidadOrganizacional_destino = models.ForeignKey(
        'UnidadOrganizacional', 
        on_delete=models.CASCADE, 
        related_name='movimientos_recibidos_unidad', 
        null=True, 
        blank=True
    )
    departamento_solicitante_id = models.ForeignKey(
        'Departamentos', 
        on_delete=models.CASCADE, 
        related_name='movimientos_solicitados',
        null=True,
        blank=True
    )
    departamento_destino_id = models.ForeignKey(
        'Departamentos', 
        on_delete=models.CASCADE, 
        related_name='movimientos_recibidos',
        null=True,
        blank=True
    )
    fecha_movimiento = models.DateField()
    fecha_entrega = models.DateField()
    tipo_movimiento = models.CharField(max_length=50)
    cantidad = models.IntegerField()
    usuario_id = models.ForeignKey('Usuario', on_delete=models.CASCADE)
    estado_solicitud = models.CharField(max_length=50)
    descripcion = models.CharField(max_length=255)

    def clean(self):
        # Validar que no se especifiquen tanto unidad como departamento
        if (self.UnidadOrganizacional_solicitante and self.departamento_solicitante_id) or \
           (self.UnidadOrganizacional_destino and self.departamento_destino_id):
            raise ValidationError("No se puede especificar unidad organizacional y departamento simultáneamente")

        # Validar que al menos se especifique una unidad o departamento
        if not self.UnidadOrganizacional_solicitante and not self.departamento_solicitante_id:
            raise ValidationError("Debe especificar una unidad organizacional o departamento solicitante")
        
        if not self.UnidadOrganizacional_destino and not self.departamento_destino_id:
            raise ValidationError("Debe especificar una unidad organizacional o departamento destino")

    class Meta:
        db_table = 'movimientos_bienes'

    def __str__(self):
        return f"Movimiento {self.id} de {self.bien_id}"

#
class AsignacionDeBienes(models.Model):
    id_asignacion_bienes = models.AutoField(primary_key=True)
    id_bienes = models.ForeignKey(Bienes, on_delete=models.CASCADE)
    id_UnidadOrganizacional = models.ForeignKey(UnidadOrganizacional, on_delete=models.PROTECT, null=True, blank=True)
    id_departamentos = models.ForeignKey(Departamentos, on_delete=models.PROTECT, null=True, blank=True)
    cantidad_asignada = models.IntegerField()
    fecha_de_asignacion = models.DateField(null=True, blank=True, default=timezone.now)
    fecha_fin_temporal = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"Asignación de {self.id_bienes} a {self.id_departamentos}"

    def clean(self):
        if (self.id_UnidadOrganizacional and self.id_departamentos) or \
        (not self.id_UnidadOrganizacional and not self.id_departamentos):
            raise ValidationError("Debe especificar una Unidad Organizacional o un departamento, pero no ambos")
            
        if self.id_departamentos and self.id_departamentos.UnidadOrganizacional != self.id_UnidadOrganizacional:
            raise ValidationError("El departamento debe pertenecer a la Unidad Organizacional seleccionada")
    
    class Meta:
        db_table = 'asignaciones_bienes'

#
class Stock(models.Model):
    id_stock = models.AutoField(primary_key=True)
    bien_id = models.OneToOneField(Bienes, on_delete=models.CASCADE)
    cantidad_total = models.IntegerField(default=0)
    cantidad_disponible = models.IntegerField(default=0)
    cantidad_asignada = models.IntegerField(default=0)
    cantidad_prestada = models.IntegerField(default=0)
    cantidad_en_mantenimiento = models.IntegerField(default=0)
    cantidad_desincorporada = models.IntegerField(default=0)
    cantidad_resguardada = models.IntegerField(default=0)

    def __str__(self):
        return f"Stock de {self.bien_id.nombre}"
    
    class Meta:
        db_table = 'stock'

#   
class Descripcion(models.Model):
    ESTADO_CHOICES = [
        ('bueno', 'Bueno'),
        ('malo', 'Malo'),
        ('regular', 'Regular'),
        ('no existe', 'No existe'),
    ]

    id_descripcion = models.AutoField(primary_key=True)
    id_bien = models.ForeignKey('Bienes', on_delete=models.CASCADE)
    descripcion = models.CharField(max_length=255)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES)

    def __str__(self):
        return f"Característica de {self.id_bien}: {self.descripcion}"
    
    class Meta:
        db_table = 'descripciones'
#
class TiposDeEvento(models.Model):
    TIPOS_EVENTO = [
        ('REGISTRO', 'Registro Inicial'),
        ('INCORPORACION', 'Incorporación'),
        ('ASIGNACION', 'Asignación'),
        ('TRASLADO_TEMPORAL', 'Traslado Temporal'),
        ('TRASLADO_PERMANENTE', 'Traslado Permanente'),
        ('DESINCORPORACION', 'Desincorporación'),
        ('MANTENIMIENTO', 'Entrada a Mantenimiento'),
        ('FIN_MANTENIMIENTO', 'Salida de Mantenimiento'),
        ('PRESTAMO', 'Préstamo'),
        ('DEVOLUCION', 'Devolución de Préstamo'),
        ('RESGUARDO', 'Entrada a Resguardo'),
        ('SALIDA_RESGUARDO', 'Salida de Resguardo'),
        ('BAJA', 'Baja Definitiva'),
        ('CAMBIO_CONCEPTO', 'Cambio de Concepto de Movimiento'), 
    ]

    id_tipos_de_evento = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50, choices=TIPOS_EVENTO, unique=True)
    descripcion = models.CharField(max_length=255)

    class Meta:
        db_table = 'tipos_evento'

    def __str__(self):
        return self.get_nombre_display()
#
class HistorialBienes(models.Model):
    bien_id = models.ForeignKey('Bienes', on_delete=models.CASCADE)
    fecha_evento = models.DateTimeField(default=timezone.now)
    id_tipos_de_evento = models.ForeignKey('TiposDeEvento', on_delete=models.CASCADE)
    descripcion = models.TextField()
    cantidad_afectada = models.IntegerField()
    usuario_id = models.ForeignKey('Usuario', on_delete=models.SET_NULL, null=True)
    departamento_origen = models.ForeignKey('Departamentos', on_delete=models.SET_NULL, null=True, related_name='historial_origen')
    departamento_destino = models.ForeignKey('Departamentos', on_delete=models.SET_NULL, null=True, related_name='historial_destino')
    UnidadOrganizacional_origen = models.ForeignKey(
    'UnidadOrganizacional', 
            on_delete=models.SET_NULL, 
            null=True, 
            blank=True, 
            related_name='historial_origen_unidad'  # Cambiar de UnidadOrganizativa a unidad
        )
    UnidadOrganizacional_destino = models.ForeignKey(
        'UnidadOrganizacional', 
        on_delete=models.SET_NULL,  
        null=True, 
        blank=True,  
        related_name='historial_destino_unidad'  # Cambiar de UnidadOrganizativa a unidad
    )
    
    def clean(self):
        if (self.UnidadOrganizacional_origen and self.departamento_origen) or \
        (self.UnidadOrganizacional_destino and self.departamento_destino):
            raise ValidationError("No se puede especificar Unidad Organizacional y departamento simultáneamente")
            
        if self.departamento_origen and self.departamento_origen.UnidadOrganizacional != self.UnidadOrganizacional_origen:
            raise ValidationError("El departamento de origen debe pertenecer a la Unidad Organizacional de origen")
            
        if self.departamento_destino and self.departamento_destino.UnidadOrganizacional != self.UnidadOrganizacional_destino:
            raise ValidationError("El departamento destino debe pertenecer a la Unidad Organizacional destino")


    def __str__(self):
        return f"{self.id_tipos_de_evento} - {self.bien_id} - {self.fecha_evento}"

    class Meta:
        db_table = 'historial_bienes'
        ordering = ['-fecha_evento']


class HistorialUsuario(models.Model):
    ACCIONES = (
        ('bloqueo', 'Bloqueo'),
        ('desbloqueo', 'Desbloqueo'),
        ('eliminacion', 'Eliminación'),
    )

    usuario = models.ForeignKey('Usuario', on_delete=models.CASCADE, related_name='historial')
    fecha = models.DateTimeField(auto_now_add=True)
    accion = models.CharField(max_length=20, choices=ACCIONES)
    realizado_por = models.ForeignKey('Usuario', on_delete=models.SET_NULL, null=True, related_name='acciones_realizadas')
    detalles = models.TextField()

    class Meta:
        db_table = 'historial_usuarios'
        ordering = ['-fecha']


class DescripcionPDF(models.Model):
    historial = models.ForeignKey(HistorialBienes, on_delete=models.CASCADE)
    descripcion = models.TextField()
    detalles_adicionales = models.JSONField(null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'descripciones_pdf'