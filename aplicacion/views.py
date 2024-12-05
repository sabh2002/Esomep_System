from django.shortcuts import render, redirect, get_object_or_404
import logging
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from .forms import GrupoForm, SubgrupoForm, SeccionSubgrupoForm
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
import calendar
from django.db.models.functions import Concat, LPad, Coalesce
from datetime import datetime
from django.db.models import Case, When, Value, CharField, Exists, Max,  OuterRef, Prefetch, Subquery, Q, F,  BooleanField, Sum, Count
from django.forms import inlineformset_factory
from django.views.generic.edit import UpdateView
from django.contrib.auth.decorators import login_required, user_passes_test
from django.urls import reverse
from django.utils import timezone
from django.views.generic import CreateView, ListView
from django.db import transaction, IntegrityError
from .serializers import BienesSerializer, StockSerializer
from rest_framework import viewsets
from django.views.decorators.http import require_http_methods
from django.contrib.auth.mixins import LoginRequiredMixin
from .decorators import role_required
from .models import ( Stock, Descripcion, Especificacion, HistorialBienes, TiposDeEvento,
    Bienes, Departamentos, RolDelUsuario, HistorialUsuario,  HistorialBienes, Grupo, Subgrupo, SeccionSubgrupo, TipoBien,
    Solicitudes, Usuario, Notificacion, TiposDeSolicitud, AsignacionDeBienes,  MovimientosBienes, DescripcionPDF
)
from django.shortcuts import redirect, render
from django.views.generic import ListView
from django.contrib.auth.mixins import UserPassesTestMixin
from django.utils import timezone

from .forms import ( AsignarBienesForm, ConceptoDeMovimientoForm, CrearSolicitudMantenimientoForm, FiltroFechaForm, AsignarRolForm, RestablecerContrasenaForm, ProcesarSolicitudTemporalForm, SolicitudNuevoBienForm, ProcesarNuevoBienForm, SolicitudPermanenteForm, ProcesarSolicitudPermanenteForm, TipoBienForm, BienForm, BienForm, DescripcionFormSet, EspecificacionFormSet,
    BienForm, DepartamentoForm, DesincorporacionForm, ProcesarDesincorporacionForm, ProcesarSolicitudMantenimientoForm, 
    RolUsuarioForm, SolicitudForm, UsuarioForm, RegistroUsuarioForm, BienForm, CrearSolicitudTemporalForm
)
from django.views.generic import FormView, DetailView
from django.template.loader import render_to_string
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.mixins import UserPassesTestMixin
from django.utils.decorators import method_decorator
from .models import TiposDeSolicitud
from .forms import TiposDeSolicitudForm

from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from .models import UnidadOrganizacional
from .forms import UnidadOrganizacionalForm
from django.conf import settings
import os
import base64
from django.http import HttpResponse
from weasyprint import HTML
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import (
    Count, Sum, Avg, F, Q, Subquery, OuterRef,
    FloatField, DurationField, ExpressionWrapper
)
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render
from datetime import datetime, timedelta
from django.core.exceptions import PermissionDenied
from functools import wraps

def admin_bienes_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.id_rol_del_usuario.nombre_rol != 'ADMIN_BIENES':
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapped

###############################################################################################################



def index(request):
    if request.user.is_authenticated:
        # Estadísticas generales
        totales_stock = Stock.objects.aggregate(
            total_disponibles=Sum('cantidad_disponible'),
            total_asignados=Sum('cantidad_asignada'),
            total_resguardados=Sum('cantidad_resguardada'),
            total_mantenimiento=Sum('cantidad_en_mantenimiento'),
            total_prestados=Sum('cantidad_prestada')
        )

        # Contar el total de bienes únicos
        total_bienes = Bienes.objects.count()

        # Estadísticas por tipo de bien
        tipos_bien = TipoBien.objects.annotate(
            total_bienes=Count('bienes')
        )

        # Preparar el contexto base
        context = {
            'total_bienes': total_bienes,
            'bienes_disponibles': totales_stock['total_disponibles'] or 0,
            'bienes_asignados': totales_stock['total_asignados'] or 0,
            'bienes_resguardados': totales_stock['total_resguardados'] or 0,
            'bienes_mantenimiento': totales_stock['total_mantenimiento'] or 0,
            'bienes_prestados': totales_stock['total_prestados'] or 0,
            'tipos_bien': tipos_bien,
            'user': request.user,
        }

        # Si no es admin, mostrar estadísticas específicas de su ubicación
        if request.user.id_rol_del_usuario.nombre_rol != 'ADMIN_BIENES':
            if request.user.id_departamentos:
                # Estadísticas para usuario de departamento
                stock_ubicacion = Stock.objects.filter(
                    bien_id__asignaciondebienes__id_departamentos=request.user.id_departamentos,
                    bien_id__asignaciondebienes__fecha_fin_temporal__isnull=True
                ).aggregate(
                    total_asignados=Sum('cantidad_asignada'),
                    total_prestados=Sum('cantidad_prestada'),
                    total_mantenimiento=Sum('cantidad_en_mantenimiento')
                )

                # Contar bienes únicos asignados al departamento
                bienes_asignados = Bienes.objects.filter(
                    asignaciondebienes__id_departamentos=request.user.id_departamentos,
                    asignaciondebienes__fecha_fin_temporal__isnull=True
                ).distinct().count()

                context.update({
                    'bienes_departamento_asignados': bienes_asignados,
                    'bienes_departamento_prestados': stock_ubicacion['total_prestados'] or 0,
                    'bienes_departamento_mantenimiento': stock_ubicacion['total_mantenimiento'] or 0,
                    'ubicacion_tipo': 'Departamento',
                    'ubicacion_nombre': request.user.id_departamentos.nombre_departamento
                })

            elif request.user.id_unidadOrganizacional:
                # Estadísticas para usuario de unidad organizacional
                stock_ubicacion = Stock.objects.filter(
                    bien_id__asignaciondebienes__id_UnidadOrganizacional=request.user.id_unidadOrganizacional,
                    bien_id__asignaciondebienes__fecha_fin_temporal__isnull=True
                ).aggregate(
                    total_asignados=Sum('cantidad_asignada'),
                    total_prestados=Sum('cantidad_prestada'),
                    total_mantenimiento=Sum('cantidad_en_mantenimiento')
                )

                # Contar bienes únicos asignados a la unidad organizacional
                bienes_asignados = Bienes.objects.filter(
                    asignaciondebienes__id_UnidadOrganizacional=request.user.id_unidadOrganizacional,
                    asignaciondebienes__fecha_fin_temporal__isnull=True
                ).distinct().count()

                context.update({
                    'bienes_departamento_asignados': bienes_asignados,
                    'bienes_departamento_prestados': stock_ubicacion['total_prestados'] or 0,
                    'bienes_departamento_mantenimiento': stock_ubicacion['total_mantenimiento'] or 0,
                    'ubicacion_tipo': 'Unidad Organizacional',
                    'ubicacion_nombre': request.user.id_unidadOrganizacional.nombre
                })

        # Agregar logging para depuración
        logger.debug("Contexto de la vista index:")
        logger.debug(f"Usuario: {request.user.username}")
        logger.debug(f"Rol: {request.user.id_rol_del_usuario.nombre_rol}")
        logger.debug(f"Departamento: {request.user.id_departamentos}")
        logger.debug(f"Unidad Organizacional: {request.user.id_unidadOrganizacional}")
        logger.debug(f"Bienes asignados: {context.get('bienes_departamento_asignados', 0)}")

        return render(request, 'index.html', context)
    
    # Si el usuario no está autenticado
    return render(request, 'index.html')

from django.db.models import Q, OuterRef, Subquery



class BienDeleteView(LoginRequiredMixin, DeleteView):
    model = Bienes
    template_name = 'bien_confirm_delete.html'
    success_url = reverse_lazy('bien_list')

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.puede_ser_eliminado():
            messages.error(
                request, 
                'Este bien no puede ser eliminado. Solo se pueden eliminar bienes '
                'que tengan menos de 48 horas de registro y no estén asignados.'
            )
            return redirect('bien_list')
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.puede_ser_eliminado():
            messages.error(
                request, 
                'Este bien no puede ser eliminado. Solo se pueden eliminar bienes '
                'que tengan menos de 48 horas de registro y no estén asignados.'
            )
            return redirect('bien_list')

        try:
            self.object.delete()
            messages.success(request, 'El bien ha sido eliminado exitosamente.')
        except Exception as e:
            messages.error(request, f'Error al eliminar el bien: {str(e)}')
        return redirect('bien_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tiempo_restante'] = self.object.get_tiempo_restante()
        context['tiene_asignacion'] = hasattr(self.object, 'asignaciondebienes_set') and self.object.asignaciondebienes_set.exists()
        return context







logger = logging.getLogger(__name__)

class BienCreateView(LoginRequiredMixin, CreateView):
    model = Bienes
    form_class = BienForm
    template_name = 'bien_form.html'
    success_url = reverse_lazy('bien_list')

    def get_context_data(self, **kwargs):
        """Agrega los formsets de descripciones y especificaciones al contexto."""
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['descripcion_formset'] = DescripcionFormSet(self.request.POST, prefix='descripcion')
            data['especificacion_formset'] = EspecificacionFormSet(self.request.POST, prefix='especificacion')
        else:
            data['descripcion_formset'] = DescripcionFormSet(prefix='descripcion')
            data['especificacion_formset'] = EspecificacionFormSet(prefix='especificacion')
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        descripcion_formset = context['descripcion_formset']
        especificacion_formset = context['especificacion_formset']

        if descripcion_formset.is_valid() and especificacion_formset.is_valid():
            try:
                with transaction.atomic():
                    # Guardar bien y asociar descripciones y especificaciones
                    self.object = form.save()
                    descripcion_formset.instance = self.object
                    descripcion_formset.save()
                    especificacion_formset.instance = self.object
                    especificacion_formset.save()

                    # Crear registro en el historial
                    tipo_evento, _ = TiposDeEvento.objects.get_or_create(nombre="CREACION_BIEN")
                    fecha_registro = datetime.combine(self.object.fecha_de_registro, datetime.min.time())
                    fecha_evento = timezone.make_aware(fecha_registro)

                    HistorialBienes.objects.create(
                        bien_id=self.object,
                        fecha_evento=fecha_evento,
                        id_tipos_de_evento=tipo_evento,
                        descripcion=f"Creación del bien: {self.object.nombre}",
                        cantidad_afectada=1,
                        usuario_id=self.request.user
                    )

                    # Crear el registro de stock
                    Stock.objects.create(
                        bien_id=self.object,
                        cantidad_total=1,
                        cantidad_disponible=0,  # Cambiado a 0 porque estará asignado
                        cantidad_asignada=1     # Asignado desde el inicio
                    )

                    # Obtener o crear el departamento de bienes
                    try:
                        depto_bienes = Departamentos.objects.get(
                            codigo_departamento='02',
                            nombre_departamento='Departamento de Bienes'
                        )
                    except Departamentos.DoesNotExist:
                        # Si no existe, lo creamos
                        depto_bienes = Departamentos.objects.create(
                            codigo_departamento='02',
                            nombre_departamento='Departamento de Bienes',
                            descripcion='Departamento encargado de gestion de bienes',
                            UnidadOrganizacional=UnidadOrganizacional.objects.get(nombre='Gerencia de Administracion y Finanzas')
                        )

                    # Crear la asignación al departamento de bienes
                    AsignacionDeBienes.objects.create(
                        id_bienes=self.object,
                        id_departamentos=depto_bienes,
                        cantidad_asignada=1,
                        fecha_de_asignacion=timezone.now()
                    )

                    # Registrar la asignación en el historial
                    tipo_evento_asignacion, _ = TiposDeEvento.objects.get_or_create(
                        nombre="ASIGNACION",
                        defaults={'descripcion': 'Asignación inicial de bien'}
                    )

                    HistorialBienes.objects.create(
                        bien_id=self.object,
                        fecha_evento=timezone.now(),
                        id_tipos_de_evento=tipo_evento_asignacion,
                        descripcion=f"Asignación inicial del bien al departamento {depto_bienes.nombre_departamento}",
                        cantidad_afectada=1,
                        usuario_id=self.request.user,
                        departamento_destino=depto_bienes
                    )

                    self._log_descripciones_guardadas(self.object)
                    self._log_especificaciones_guardadas(self.object)

                messages.success(self.request, "Bien registrado y asignado al Departamento de Bienes exitosamente.")
                return JsonResponse({
                    'success': True,
                    'redirect_url': self.get_success_url(),
                    'numero_registro': self.object.id_bienes
                })
            except IntegrityError as e:
                logger.error(f"Error al guardar el bien: {e}")
                return self._json_error_response("Hubo un error al guardar los datos. Intenta nuevamente.")

        return self.form_invalid(form)

    def form_invalid(self, form):
        """Maneja los errores en los formularios y formsets."""
        context = self.get_context_data()
        descripcion_formset = context['descripcion_formset']
        especificacion_formset = context['especificacion_formset']
        logger.error(f"Errores en el formulario: {form.errors}")
        logger.error(f"Errores en el formset de descripciones: {descripcion_formset.errors}")
        logger.error(f"Errores en el formset de especificaciones: {especificacion_formset.errors}")

        return JsonResponse({
            'success': False,
            'errors': form.errors,
            'descripcion_errors': [error for error in descripcion_formset.errors if error],
            'especificacion_errors': [error for error in especificacion_formset.errors if error]
        }, status=400)

    def _log_descripciones_guardadas(self, bien):
        """Registra las descripciones guardadas en los logs."""
        descripciones = Descripcion.objects.filter(id_bien=bien)
        logger.info(f"Guardadas {descripciones.count()} descripciones para el bien {bien.id_bienes}.")
        for desc in descripciones:
            logger.info(f"Descripción: {desc.descripcion} - Estado: {desc.estado}")

    def _log_especificaciones_guardadas(self, bien):
        """Registra las especificaciones guardadas en los logs."""
        especificaciones = Especificacion.objects.filter(id_bien=bien)
        logger.info(f"Guardadas {especificaciones.count()} especificaciones para el bien {bien.id_bienes}.")
        for esp in especificaciones:
            logger.info(f"Especificación: {esp.especificacion} - Descripción: {esp.descripcion_especificacion}")

    def _json_error_response(self, message):
        """Genera una respuesta JSON para errores generales."""
        return JsonResponse({'success': False, 'message': message}, status=500)
    

def get_subgrupos(request):
    grupo_id = request.GET.get('grupo_id')
    subgrupos = []
    
    if grupo_id:
        subgrupos = list(Subgrupo.objects.filter(id_grupo_id=grupo_id).values('id_subgrupo', 'nombre', 'codigo'))
    
    return JsonResponse({'subgrupos': subgrupos})

def get_secciones(request):
    subgrupo_id = request.GET.get('subgrupo_id')
    secciones = []
    
    if subgrupo_id:
        secciones = list(SeccionSubgrupo.objects.filter(id_subgrupo_id=subgrupo_id).values('id_seccion_subgrupo', 'nombre', 'codigo'))
    
    return JsonResponse({'secciones': secciones})
    
class StockListView(ListView):
    model = Stock
    template_name = 'stock_list.html'
    context_object_name = 'stocks'

    def get_queryset(self):
        queryset = Stock.objects.select_related(
            'bien_id',
            'bien_id__id_grupo',
            'bien_id__id_subgrupo',
            'bien_id__id_seccion_subgrupo',
            'bien_id__id_concepto_de_movimiento'
        )
        
        # Aplicar filtros si es necesario
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(bien_id__nombre__icontains=search_query) |
                Q(bien_id__numero_de_identificacion__icontains=search_query)
            )
        
        return queryset
    
class StockDetailView(DetailView):
    model = Stock
    template_name = 'stock_detail.html'
    context_object_name = 'stock'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        stock = self.object  # Obtiene el objeto Stock actual

        # Obtener los departamentos asignados
        departamentos_asignados = AsignacionDeBienes.objects.filter(id_bienes=stock.bien_id).select_related('id_departamentos')

        # Añadir los departamentos asignados al contexto
        context['departamentos_asignados'] = departamentos_asignados

        # Imprimir información de depuración
        print(f"Stock: {stock}")
        print(f"Departamentos asignados: {departamentos_asignados}")

        return context




logger = logging.getLogger(__name__)

@login_required
def bien_descripcion(request, bien_id):
    try:
        bien = get_object_or_404(Bienes, id_bienes=bien_id)
        descripciones = Descripcion.objects.filter(id_bien=bien)
        especificaciones = Especificacion.objects.filter(id_bien=bien)
        
        logger.info(f"Recuperadas {descripciones.count()} descripciones y {especificaciones.count()} especificaciones para el bien {bien_id}")
        
        return render(request, 'descripcion_bien.html', {
            'bien': bien, 
            'descripciones': descripciones,
            'especificaciones': especificaciones
        })
    except Exception as e:
        logger.error(f"Error al recuperar información para el bien {bien_id}: {str(e)}")
        return render(request, 'error.html', {'mensaje': 'No se pudo cargar la información del bien'})


##############################################################################################################

@login_required
def pdf_bienes(request):
    bienes = Bienes.objects.all()
    html_string = render_to_string('pdf.html', {'bienes': bienes})
    html = HTML(string=html_string)
    pdf = html.write_pdf()
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="lista_bienes.pdf"'
    return response

##############################################################################################################



@login_required
def lista_solicitudes(request):
    # Obtener el rol del usuario
    rol_usuario = request.user.id_rol_del_usuario

    if rol_usuario and rol_usuario.nombre_rol == 'ADMIN_BIENES':
        # Si el usuario es administrador de bienes, mostrar todas las solicitudes pendientes
        solicitudes = Solicitudes.objects.filter(estado_solicitud='pendiente')
    else:
        # Para usuarios estándar, mostrar solo sus propias solicitudes
        solicitudes = Solicitudes.objects.filter(usuario_id=request.user)

    return render(request, 'lista_solicitudes.html', {'solicitudes': solicitudes})



def login_view(request):
    if request.method == 'POST':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            username = request.POST.get('username')
            password = request.POST.get('password')
            
            try:
                # Primero verificar si el usuario existe y su estado
                try:
                    usuario = Usuario.objects.get(username=username)
                    
                    # Verificar si el usuario está bloqueado
                    if usuario.estado == 'bloqueado':
                        return JsonResponse({
                            'success': False,
                            'error_type': 'blocked',
                            'error': 'Tu cuenta está bloqueada. Contacta al administrador.'
                        })
                    
                    # Verificar si el usuario está eliminado
                    if usuario.estado == 'eliminado':
                        return JsonResponse({
                            'success': False,
                            'error_type': 'deleted',
                            'error': 'Esta cuenta ha sido eliminada del sistema.'
                        })
                        
                    # Si el usuario existe y no está bloqueado ni eliminado, proceder con la autenticación
                    user = authenticate(request, username=username, password=password)
                    
                    if user is not None:
                        if user.is_active:
                            if user.estado == 'activo':
                                login(request, user)
                                return JsonResponse({
                                    'success': True,
                                    'redirect_url': reverse('index')
                                })
                            else:
                                return JsonResponse({
                                    'success': False,
                                    'error_type': 'status',
                                    'error': 'Tu cuenta no está activa. Contacta al administrador.'
                                })
                        else:
                            return JsonResponse({
                                'success': False,
                                'error_type': 'account',
                                'error': 'Tu cuenta está desactivada. Contacta al administrador.'
                            })
                    else:
                        return JsonResponse({
                            'success': False,
                            'error_type': 'password',
                            'error': 'La contraseña ingresada es incorrecta.'
                        })
                        
                except Usuario.DoesNotExist:
                    return JsonResponse({
                        'success': False,
                        'error_type': 'username',
                        'error': 'La cédula ingresada no está registrada en el sistema.'
                    })
            
            except Exception as e:
                print(f"Error en login: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'error_type': 'general',
                    'error': 'Error al procesar la solicitud. Por favor, intente nuevamente.'
                })
        else:
            form = AuthenticationForm(request, data=request.POST)
            if form.is_valid():
                username = form.cleaned_data.get('username')
                try:
                    usuario = Usuario.objects.get(username=username)
                    
                    # Verificar estado del usuario para el formulario normal
                    if usuario.estado == 'bloqueado':
                        form.add_error(None, 'Tu cuenta está bloqueada. Contacta al administrador.')
                        return render(request, 'login.html', {'form': form})
                    
                    if usuario.estado == 'eliminado':
                        form.add_error(None, 'Esta cuenta ha sido eliminada del sistema.')
                        return render(request, 'login.html', {'form': form})
                    
                    if usuario.estado != 'activo':
                        form.add_error(None, 'Tu cuenta no está activa. Contacta al administrador.')
                        return render(request, 'login.html', {'form': form})
                    
                    password = form.cleaned_data.get('password')
                    user = authenticate(username=username, password=password)
                    if user is not None and user.is_active:
                        login(request, user)
                        return redirect('index')
                        
                except Usuario.DoesNotExist:
                    form.add_error(None, 'Usuario no encontrado.')
                    
            return render(request, 'login.html', {'form': form})
    else:
        form = AuthenticationForm()
    
    return render(request, 'login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')




logger = logging.getLogger(__name__)

def es_admin_bienes(user):
    return user.id_rol_del_usuario and user.id_rol_del_usuario.nombre_rol == 'ADMIN_BIENES'


@login_required
@user_passes_test(es_admin_bienes)
def asignar_bienes(request):
   try:
       if request.method == 'POST':
           form = AsignarBienesForm(request.POST)
           logger.info(f"Formulario recibido para asignación de bienes de usuario: {request.user.username}")

           if form.is_valid():
               unidadOrganizacional = form.cleaned_data['unidadOrganizacional']
               departamento = form.cleaned_data['departamento']
               bienes_seleccionados = form.cleaned_data['bienes']
               
               destino = departamento if departamento else unidadOrganizacional
               logger.info(f"Iniciando asignación de {len(bienes_seleccionados)} bienes a {destino}")

               try:
                   with transaction.atomic():
                       tipo_evento = TiposDeEvento.objects.get_or_create(
                           nombre="ASIGNACION",
                           defaults={'descripcion': 'Asignación de bienes'}
                       )[0]

                       for bien in bienes_seleccionados:
                           if departamento:
                               asignado = AsignacionDeBienes.objects.filter(
                                   id_bienes=bien,
                                   id_departamentos=departamento,
                                   fecha_fin_temporal__isnull=True
                               ).exists()
                               destino_nombre = departamento.nombre_departamento
                           else:
                               asignado = AsignacionDeBienes.objects.filter(
                                   id_bienes=bien,
                                   id_UnidadOrganizacional=unidadOrganizacional,
                                   fecha_fin_temporal__isnull=True
                               ).exists()
                               destino_nombre = unidadOrganizacional.nombre

                           if asignado:
                               raise ValidationError(
                                   f"El bien {bien.nombre} ya está asignado a {destino_nombre}"
                               )

                           stock = Stock.objects.select_for_update().get(bien_id=bien)
                           
                           if stock.cantidad_disponible < 1:
                               raise ValidationError(
                                   f"No hay unidades disponibles del bien {bien.nombre}"
                               )

                           AsignacionDeBienes.objects.create(
                               id_bienes=bien,
                               id_UnidadOrganizacional=unidadOrganizacional if not departamento else None,
                               id_departamentos=departamento if departamento else None,
                               cantidad_asignada=1,
                               fecha_de_asignacion=timezone.now().date()
                           )

                           stock.cantidad_disponible -= 1
                           stock.cantidad_asignada += 1
                           stock.save()

                           HistorialBienes.objects.create(
                               bien_id=bien,
                               fecha_evento=timezone.now(),
                               id_tipos_de_evento=tipo_evento,
                               descripcion=f"Asignación a {destino_nombre}",
                               cantidad_afectada=1,
                               usuario_id=request.user,
                               departamento_destino=departamento if departamento else None,
                               UnidadOrganizacional_destino=unidadOrganizacional if not departamento else None
                           )

                       messages.success(request, f'Se han asignado {len(bienes_seleccionados)} bienes a {destino_nombre}')
                       return redirect('bien_list')

               except ValidationError as e:
                   logger.warning(f"Error de validación en asignación: {str(e)}")
                   messages.error(request, str(e))
               except Exception as e:
                   logger.error(f"Error inesperado en asignación de bienes: {str(e)}")
                   messages.error(request, 'Ha ocurrido un error al procesar la asignación.')
       else:
           form = AsignarBienesForm()

       # Obtener unidades organizacionales que tienen usuarios activos
       unidades_organizacionales = UnidadOrganizacional.objects.filter(
           usuario__estado='activo',
           usuario__is_active=True
       ).distinct().order_by('nombre')

       # Obtener departamentos que tienen usuarios activos y excluir los especiales
       departamentos = Departamentos.objects.filter(
           usuario__estado='activo',
           usuario__is_active=True
       ).exclude(
           Q(codigo_departamento__in=['MANT', 'RESG']) |
           Q(nombre_departamento__in=['Bienes en Mantenimiento', 'Bienes en Resguardo'])
       ).distinct().order_by(
           'UnidadOrganizacional__nombre', 
           'nombre_departamento'
       )

       # Obtener bienes con stock disponible
       bienes_con_stock = Stock.objects.select_related('bien_id').filter(
           cantidad_disponible__gt=0
       ).annotate(
           bien_nombre=F('bien_id__nombre'),
           bien_codigo=F('bien_id__numero_de_identificacion')
       ).values(
           'bien_id',
           'bien_nombre', 
           'bien_codigo',
           'cantidad_disponible'
       ).order_by('bien_nombre')

       bienes_formateados = [
           {
               'bien': {
                   'id_bienes': item['bien_id'],
                   'nombre': item['bien_nombre'],
                   'numero_de_identificacion': item['bien_codigo']
               },
               'cantidad_disponible': item['cantidad_disponible']
           }
           for item in bienes_con_stock
       ]

       context = {
           'form': form,
           'bienes_con_stock': bienes_formateados,
           'bienes_count': len(bienes_formateados),
           'unidades_organizacionales': unidades_organizacionales,
           'departamentos': departamentos,
       }

       return render(request, 'asignar_bienes.html', context)
   
   except Exception as e:
       logger.error(f"Error general en la vista de asignación: {str(e)}")
       messages.error(request, 'Ha ocurrido un error inesperado.')
       return redirect('bien_list')



@login_required
def bienes_asignados(request):
    usuario = request.user
    es_admin = usuario.id_rol_del_usuario.nombre_rol == 'ADMIN_BIENES'
    
    logger.info(f"Usuario: {usuario.nombres} {usuario.apellidos} (ID: {usuario.id_usuario})")
    logger.info(f"Rol: {'Administrador' if es_admin else 'Usuario Estándar'}")

    if es_admin:
        departamento = "Departamento de Bienes"
        logger.info("Mostrando bienes para el administrador")
    else:
        departamento = usuario.id_departamentos
        logger.info(f"Departamento: {departamento.nombre_departamento} (ID: {departamento.id_departamentos})")

    bienes_asignados = []

    if es_admin:
        # Obtener todos los bienes para el admin
        asignaciones = AsignacionDeBienes.objects.all().select_related('id_bienes')
    else:
        # Obtener bienes asignados al departamento del usuario
        asignaciones = AsignacionDeBienes.objects.filter(id_departamentos=departamento).select_related('id_bienes')

    for asignacion in asignaciones:
        bien = asignacion.id_bienes
        stock = Stock.objects.filter(bien_id=bien).first()
        
        if stock:
            cantidad_disponible = stock.cantidad_disponible
            cantidad_resguardada = stock.cantidad_resguardada
            cantidad_desincorporada = stock.cantidad_desincorporada
        else:
            cantidad_disponible = cantidad_resguardada = cantidad_desincorporada = 0

        # Determinar el estado basado en el stock
        if cantidad_resguardada > 0:
            estado = 'Resguardado'
        elif cantidad_desincorporada > 0:
            estado = 'Desincorporado'
        elif cantidad_disponible > 0:
            estado = 'Disponible'
        else:
            estado = 'No disponible'

        bienes_asignados.append({
            'bien': bien,
            'cantidad_disponible': cantidad_disponible,
            'cantidad_asignada': asignacion.cantidad_asignada,
            'estado': estado,
            'fecha_asignacion': asignacion.fecha_de_asignacion
        })
        logger.info(f"Bien: {bien.nombre} - Cantidad Disponible: {cantidad_disponible} - Cantidad Asignada: {asignacion.cantidad_asignada} - Estado: {estado}")

    logger.info("Bienes a mostrar en el template:")
    for bien in bienes_asignados:
        logger.info(f"Bien: {bien['bien'].nombre}, Cantidad Disponible: {bien['cantidad_disponible']}, Cantidad Asignada: {bien['cantidad_asignada']}, Estado: {bien['estado']}, Fecha: {bien['fecha_asignacion']}")

    context = {
        'departamento': departamento,
        'bienes_asignados': bienes_asignados,
        'es_admin': es_admin,
        'debug_info': {
            'usuario_id': usuario.id_usuario,
            'departamento_id': departamento.id_departamentos if not es_admin else None,
            'total_bienes': len(bienes_asignados),
            'bienes_list': [
                {
                    'bien_id': bien['bien'].id_bienes,
                    'bien_nombre': bien['bien'].nombre,
                    'cantidad_disponible': bien['cantidad_disponible'],
                    'cantidad_asignada': bien['cantidad_asignada'],
                    'estado': bien['estado'],
                    'fecha_asignacion': bien['fecha_asignacion']
                } for bien in bienes_asignados
            ]
        }
    }
    return render(request, 'bienes_asignados.html', context)

def sincronizar_stock_y_asignaciones():
    logger.info("Iniciando sincronización de Stock y AsignacionDeBienes")
    
    for bien in Bienes.objects.all():
        if bien.id_departamentos:
            asignacion, created = AsignacionDeBienes.objects.get_or_create(
                id_bienes=bien,
                id_departamentos=bien.id_departamentos,
                defaults={'cantidad_asignada': 1, 'fecha_de_asignacion': bien.fecha_de_registro}
            )
            
            stock, created = Stock.objects.get_or_create(bien_id=bien)
            if stock.cantidad_asignada != asignacion.cantidad_asignada:
                stock.cantidad_asignada = asignacion.cantidad_asignada
                stock.cantidad_disponible = max(0, stock.cantidad_total - stock.cantidad_asignada)
                stock.save()
                logger.info(f"Stock actualizado para Bien ID {bien.id_bienes}: Asignado = {stock.cantidad_asignada}, Disponible = {stock.cantidad_disponible}")

    logger.info("Sincronización completada")


def actualizar_ubicacion_bien(bien, departamento, usuario):
    bien.departamento = departamento
    bien.usuario_asignado = usuario
    bien.save()
    logger.info(f"Ubicación actualizada para el bien {bien.nombre}: Departamento {departamento.nombre}")




logger = logging.getLogger(__name__)

@login_required
def crear_solicitud(request):
    tipos_solicitud = TiposDeSolicitud.objects.all()

    # Registrar los tipos de solicitudes existentes
    logger.info("Tipos de solicitudes registradas:")
    for tipo in tipos_solicitud:
        logger.info(f"ID: {tipo.id_tipos_de_solicitud} - Nombre: {tipo.nombre} - Descripción: {tipo.descripcion}")

    context = {
        'tipos_solicitud': tipos_solicitud
    }
    return render(request, 'crear_solicitud.html', context)


@login_required
def registro_usuario(request):
    if request.method == 'POST':
        form = RegistroUsuarioForm(request.POST)
        logger.debug(f"Datos recibidos en POST: {request.POST}")

        if form.is_valid():
            try:
                usuario = form.save(commit=False)
                usuario.username = form.cleaned_data['cedula']
                usuario.set_password(form.cleaned_data['contrasena'])
                usuario.is_active = True
                usuario.estado = 'activo'

                # Asegurarse de que solo uno esté establecido
                if form.cleaned_data.get('id_unidadOrganizacional'):
                    usuario.id_departamentos = None
                elif form.cleaned_data.get('id_departamentos'):
                    usuario.id_unidadOrganizacional = None

                usuario.save()
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'message': 'Usuario registrado exitosamente',
                        'redirect_url': reverse('lista_usuarios')
                    })
                
                messages.success(request, 'Usuario registrado exitosamente')
                return redirect('lista_usuarios')
            except Exception as e:
                logger.error(f"Error al guardar usuario: {str(e)}")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': str(e),
                        'errors': {'__all__': [str(e)]}
                    }, status=400)
                raise
        else:
            logger.error(f"Errores de validación del formulario: {form.errors}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': 'Por favor corrija los errores en el formulario',
                    'errors': form.errors
                }, status=400)
    else:
        form = RegistroUsuarioForm()
    
    return render(request, 'registro_usuario.html', {
        'form': form,
        'unidades_organizacionales': UnidadOrganizacional.objects.all(),
        'departamentos': Departamentos.objects.all(),
        'roles': RolDelUsuario.objects.all()
    })

from django.views.generic import ListView, View
from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.utils import timezone

class CambiarEstadoUsuarioView(UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.id_rol_del_usuario.nombre_rol == 'ADMIN_BIENES'

    def post(self, request, pk):
        try:
            usuario = get_object_or_404(Usuario, pk=pk)
            accion = request.POST.get('accion')

            # Verificar si el usuario intenta modificarse a sí mismo
            if usuario == request.user:
                return JsonResponse({
                    'success': False,
                    'error': 'No puedes modificar tu propio estado'
                })

            # Verificar bienes asignados para eliminación
            if accion == 'eliminar':
                if usuario.get_bienes_count() > 0:
                    return JsonResponse({
                        'success': False,
                        'error': 'No se puede eliminar el usuario porque tiene bienes asignados'
                    })

            # Procesar la acción correspondiente
            if accion == 'bloquear':
                usuario.estado = 'bloqueado'
                usuario.fecha_bloqueo = timezone.now()
                mensaje = f'Usuario {usuario.get_full_name()} bloqueado exitosamente'
                
                HistorialUsuario.objects.create(
                    usuario=usuario,
                    accion='bloqueo',
                    realizado_por=request.user,
                    detalles='Usuario bloqueado por administrador'
                )

            elif accion == 'desbloquear':
                usuario.estado = 'activo'
                usuario.fecha_bloqueo = None
                mensaje = f'Usuario {usuario.get_full_name()} desbloqueado exitosamente'
                
                HistorialUsuario.objects.create(
                    usuario=usuario,
                    accion='desbloqueo',
                    realizado_por=request.user,
                    detalles='Usuario desbloqueado por administrador'
                )

            elif accion == 'eliminar':
                departamento_anterior = usuario.id_departamentos
                
                # Desvincular del departamento
                usuario.id_departamentos = None
                usuario.estado = 'eliminado'
                usuario.is_active = False
                usuario.fecha_eliminacion = timezone.now()
                
                # Limpiar otros campos si es necesario
                usuario.bienes_asignados.clear()  # Limpiar relación many-to-many con bienes
                
                mensaje = f'Usuario {usuario.get_full_name()} eliminado exitosamente'
                
                # Registrar en el historial con el detalle del departamento anterior
                HistorialUsuario.objects.create(
                    usuario=usuario,
                    accion='eliminacion',
                    realizado_por=request.user,
                    detalles=f'Usuario eliminado por administrador. Departamento anterior: {departamento_anterior}'
                )

                # Crear notificación para administradores
                admins = Usuario.objects.filter(
                    id_rol_del_usuario__nombre_rol='ADMIN_BIENES',
                    estado='activo'
                ).exclude(pk=request.user.pk)

                for admin in admins:
                    Notificacion.objects.create(
                        usuario=admin,
                        mensaje=f'El usuario {usuario.get_full_name()} ha sido eliminado del sistema por {request.user.get_full_name()}',
                        fecha=timezone.now()
                    )

            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Acción no válida'
                })

            usuario.save()

            return JsonResponse({
                'success': True,
                'mensaje': mensaje,
                'nuevo_estado': usuario.estado,
                'tiene_bienes': usuario.get_bienes_count() > 0,
                'departamento': str(usuario.id_departamentos) if usuario.id_departamentos else 'Sin departamento'
            })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Error al procesar la solicitud: {str(e)}'
            })

    def handle_no_permission(self):
        return JsonResponse({
            'error': 'No tienes permiso para realizar esta acción'
        }, status=403)



class ListaUsuariosView(UserPassesTestMixin, ListView):
    model = Usuario
    template_name = 'admin_bienes/lista_usuarios.html'
    context_object_name = 'usuarios'

    def test_func(self):
        return self.request.user.id_rol_del_usuario.nombre_rol == 'ADMIN_BIENES'

    def get_queryset(self):
        return Usuario.objects.select_related(
            'id_rol_del_usuario',
            'id_departamentos',
            'id_departamentos__UnidadOrganizacional'  # Añadido para acceder a la unidad
        ).prefetch_related(
            # Prefetch para bienes del departamento
            Prefetch(
                'id_departamentos__asignaciondebienes_set',
                queryset=AsignacionDeBienes.objects.filter(
                    Q(fecha_fin_temporal__isnull=True) |
                    Q(fecha_fin_temporal__gt=timezone.now())
                ).select_related('id_bienes'),
                to_attr='bienes_asignados_actuales'
            ),
            # Prefetch para bienes de la unidad
            Prefetch(
                'id_departamentos__UnidadOrganizacional__asignaciondebienes_set',
                queryset=AsignacionDeBienes.objects.filter(
                    Q(fecha_fin_temporal__isnull=True) |
                    Q(fecha_fin_temporal__gt=timezone.now())
                ).select_related('id_bienes'),
                to_attr='bienes_unidad_actuales'
            )
        ).annotate(
            bienes_count=Count(
                Case(
                    # Contar bienes del departamento
                    When(
                        Q(id_departamentos__asignaciondebienes__id_bienes__condicion='Operativo') &
                        (Q(id_departamentos__asignaciondebienes__fecha_fin_temporal__isnull=True) |
                         Q(id_departamentos__asignaciondebienes__fecha_fin_temporal__gt=timezone.now())),
                        then='id_departamentos__asignaciondebienes__id_bienes'
                    ),
                    # Contar bienes de la unidad
                    When(
                        Q(id_departamentos__UnidadOrganizacional__asignaciondebienes__id_bienes__condicion='Operativo') &
                        (Q(id_departamentos__UnidadOrganizacional__asignaciondebienes__fecha_fin_temporal__isnull=True) |
                         Q(id_departamentos__UnidadOrganizacional__asignaciondebienes__fecha_fin_temporal__gt=timezone.now())),
                        then='id_departamentos__UnidadOrganizacional__asignaciondebienes__id_bienes'
                    ),
                ),
                distinct=True
            )
        ).order_by('nombres')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for usuario in context['usuarios']:
            bienes_departamento = []
            bienes_unidad = []
            
            # Obtener bienes asignados al departamento del usuario
            if hasattr(usuario.id_departamentos, 'bienes_asignados_actuales'):
                bienes_departamento = usuario.id_departamentos.bienes_asignados_actuales

            # Obtener bienes asignados a la unidad del usuario
            if (usuario.id_departamentos and 
                usuario.id_departamentos.UnidadOrganizacional and 
                hasattr(usuario.id_departamentos.UnidadOrganizacional, 'bienes_unidad_actuales')):
                bienes_unidad = usuario.id_departamentos.UnidadOrganizacional.bienes_unidad_actuales

            # Combinar los bienes y calcular totales
            todos_los_bienes = bienes_departamento + bienes_unidad
            
            usuario.bienes_detalle = {
                'total': len(todos_los_bienes),
                'operativos': len([
                    b for b in todos_los_bienes 
                    if b.id_bienes.condicion == 'Operativo'
                ])
            }

        return context
    
    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para acceder a esta página.")
        return redirect('home')
        
class RestablecerContrasenaView(UserPassesTestMixin, FormView):
    template_name = 'admin_bienes/restablecer_contrasena.html'
    form_class = RestablecerContrasenaForm
    success_url = reverse_lazy('lista_usuarios')

    def test_func(self):
        return self.request.user.id_rol_del_usuario.nombre_rol == 'ADMIN_BIENES'

    def form_valid(self, form):
        usuario = get_object_or_404(Usuario, pk=self.kwargs['pk'])
        nueva_contrasena = form.cleaned_data['nueva_contrasena']
        usuario.set_password(nueva_contrasena)
        usuario.save()
        messages.success(self.request, f"Contraseña restablecida para {usuario.get_full_name()}")
        return super().form_valid(form)

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para realizar esta acción.")
        return redirect('home')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        usuario = get_object_or_404(Usuario, pk=self.kwargs['pk'])
        context['usuario'] = usuario
        return context

@login_required
def get_bienes_usuario(request, usuario_id):
    try:
        usuario = Usuario.objects.get(pk=usuario_id)
        bienes = usuario.get_bienes_asignados()
        
        bienes_data = []
        for bien in bienes:
            ultima_asignacion = bien.asignaciondebienes_set.order_by('-fecha_de_asignacion').first()
            
            # Comprobar traslados temporales activos
            traslado_temporal = AsignacionDeBienes.objects.filter(
                id_bienes=bien,
                fecha_fin_temporal__gt=timezone.now()
            ).order_by('-fecha_de_asignacion').first()
            
            estado_traslado = None
            if traslado_temporal:
                if traslado_temporal.id_departamentos:
                    if traslado_temporal.id_departamentos == usuario.id_departamentos:
                        estado_traslado = f"Prestado desde {traslado_temporal.id_bienes.get_departamento_actual()}"
                    else:
                        estado_traslado = f"Prestado a {traslado_temporal.id_departamentos}"
                else:
                    if traslado_temporal.id_UnidadOrganizacional == usuario.id_unidadOrganizacional:
                        estado_traslado = f"Prestado desde {traslado_temporal.id_bienes.get_unidad_actual()}"
                    else:
                        estado_traslado = f"Prestado a {traslado_temporal.id_UnidadOrganizacional}"

            bien_data = {
                'id': bien.id_bienes,
                'numero_de_identificacion': bien.numero_de_identificacion,
                'nombre': bien.nombre,
                'fecha_asignacion': ultima_asignacion.fecha_de_asignacion.strftime('%d/%m/%Y') if ultima_asignacion else None,
                'estado': estado_traslado if estado_traslado else bien.estado
            }
            bienes_data.append(bien_data)

        return JsonResponse({
            'success': True,
            'bienes': bienes_data
        })
    except Usuario.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Usuario no encontrado'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


class AsignarRolesView(UserPassesTestMixin, UpdateView):
    model = Usuario
    template_name = 'admin_bienes/asignar_roles.html'
    form_class = AsignarRolForm
    success_url = reverse_lazy('lista_usuarios')

    def test_func(self):
        return self.request.user.id_rol_del_usuario.nombre_rol == 'ADMIN_BIENES'

    def form_valid(self, form):
        messages.success(self.request, f"Rol actualizado para {self.object.get_full_name()}")
        return super().form_valid(form)

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para realizar esta acción.")
        return redirect('home')
    


def es_admin_bienes(user):
    return user.is_authenticated and user.id_rol_del_usuario.nombre_rol == 'ADMIN_BIENES'

@user_passes_test(es_admin_bienes)
def gestion_usuarios(request):
    return render(request, 'admin_bienes/gestion_usuarios.html')


@login_required
def listar_departamentos(request):
    # Excluir los departamentos de Mantenimiento y Resguardo
    departamentos = Departamentos.objects.select_related('UnidadOrganizacional').exclude(
        Q(nombre_departamento__in=['Bienes en Mantenimiento', 'Bienes en Resguardo']) |
        Q(codigo_departamento__in=['MANT', 'RESG'])
    ).order_by('UnidadOrganizacional__nombre', 'nombre_departamento')

    # Agregar logging para debug
    logger.info("=== Departamentos filtrados ===")
    for dept in departamentos:
        logger.info(f"ID: {dept.id_departamentos}, "
                   f"Código: {dept.codigo_departamento}, "
                   f"Nombre: {dept.nombre_departamento}, "
                   f"Unidad: {dept.UnidadOrganizacional.nombre if dept.UnidadOrganizacional else 'N/A'}")

    context = {
        'departamentos': departamentos,
        'total_departamentos': departamentos.count()
    }
    return render(request, 'departamentos/listar.html', context)

@login_required
def agregar_departamento(request):
   if request.method == 'POST':
       form = DepartamentoForm(request.POST)
       if form.is_valid():
           departamento = form.save()
           messages.success(request, 'Departamento registrado exitosamente.')
           return redirect('listar_departamentos')
   else:
       form = DepartamentoForm()
   
   return render(request, 'departamentos/agregar.html', {
       'form': form,
       'unidades': UnidadOrganizacional.objects.all()
   })

@login_required
def editar_departamento(request, id_departamento):
   departamento = get_object_or_404(Departamentos, id_departamentos=id_departamento)
   
   if request.method == 'POST':
       form = DepartamentoForm(request.POST, instance=departamento)
       if form.is_valid():
           form.save()
           messages.success(request, 'Departamento actualizado exitosamente.')
           return redirect('listar_departamentos')
   else:
       form = DepartamentoForm(instance=departamento)
   
   return render(request, 'departamentos/editar.html', {
       'form': form,
       'departamento': departamento,
       'unidades': UnidadOrganizacional.objects.all()
   })

@login_required
def eliminar_departamento(request, id_departamento):
    departamento = get_object_or_404(Departamentos, id_departamentos=id_departamento)
    
    if request.method == 'POST':
        try:
            departamento.delete()
            messages.success(request, 'Departamento eliminado exitosamente.')
            return redirect('listar_departamentos')
        except Exception as e:
            messages.error(request, 'No se puede eliminar el departamento porque tiene registros asociados.')
            return redirect('listar_departamentos')
    
    return render(request, 'departamentos/eliminar_departamento.html', {
        'departamento': departamento
    })

# Agregar vista para cargar departamentos por AJAX
from django.http import JsonResponse

def get_departamentos_por_gerencia(request):
    gerencia_id = request.GET.get('gerencia_id')
    departamentos = []
    
    if gerencia_id:
        departamentos = list(Departamentos.objects.filter(
            gerencia_id=gerencia_id
        ).values('id_departamentos', 'nombre_departamento'))
        
    return JsonResponse({'departamentos': departamentos})

    


@login_required
def inventario_activo(request):
    user = request.user
    departamento = user.id_departamentos
    
    bienes_activos = Bienes.objects.filter(
        id_departamentos=departamento,
        stock__cantidad_total__gt=0
    ).select_related('stock')

    context = {
        'bienes_activos': bienes_activos,
        'departamento': departamento,
    }
    return render(request, 'inventario_activo.html', context)



class BienesViewSet(viewsets.ModelViewSet):
    queryset = Bienes.objects.all()
    serializer_class = BienesSerializer

class StockViewSet(viewsets.ModelViewSet):
    queryset = Stock.objects.all()
    serializer_class = StockSerializer


@login_required
def detalle_solicitud(request, solicitud_id):
    solicitud = get_object_or_404(Solicitudes, id_solicitudes=solicitud_id)
    
    # Verifica si el usuario tiene permiso para ver esta solicitud
    if request.user.id_rol_del_usuario.nombre_rol != 'ADMIN_BIENES' and solicitud.usuario_id != request.user:
        messages.error(request, 'No tienes permiso para ver esta solicitud.')
        return redirect('lista_solicitudes')
    
    return render(request, 'detalle_solicitud.html', {'solicitud': solicitud})






logger = logging.getLogger(__name__)

@login_required
def solicitud_desincorporacion(request):
    try:
        # Verificación inicial del usuario
        logger.debug("=== INICIO DE LA SOLICITUD ===")
        logger.debug(f"Usuario: {request.user.username}")
        logger.debug(f"Departamento del usuario: {request.user.id_departamentos}")
        logger.debug(f"Unidad Organizacional del usuario: {request.user.id_unidadOrganizacional}")

        # Verificar si el usuario tiene departamento o unidad organizacional
        if not request.user.id_departamentos and not request.user.id_unidadOrganizacional:
            mensaje = 'El usuario debe pertenecer a un departamento o unidad organizacional'
            logger.warning(f"Usuario {request.user.username}: {mensaje}")
            messages.error(request, mensaje)
            return redirect('lista_solicitudes')

        # Obtener bienes en traslado temporal
        bienes_en_traslado = AsignacionDeBienes.objects.filter(
            fecha_fin_temporal__isnull=False,
            fecha_fin_temporal__gt=timezone.now()
        ).values('id_bienes')

        # Obtener bienes con solicitudes de desincorporación pendientes
        bienes_con_solicitud_pendiente = Solicitudes.objects.filter(
            id_tipos_de_solicitud__nombre='Desincorporación',
            estado_solicitud='pendiente'
        ).values('bien_id')

        # Obtener el histórico de eventos para identificar el último estado
        ultimo_evento_subquery = HistorialBienes.objects.filter(
            bien_id=OuterRef('pk')
        ).order_by('-fecha_evento').values('id_tipos_de_evento__nombre')[:1]

        # Obtener stock actual
        stock_subquery = Stock.objects.filter(
            bien_id=OuterRef('pk')
        ).values('cantidad_asignada')[:1]

        if request.user.id_departamentos:
            bienes_disponibles = Bienes.objects.filter(
                asignaciondebienes__id_departamentos=request.user.id_departamentos,
                asignaciondebienes__fecha_fin_temporal__isnull=True
            ).exclude(
                Q(id_bienes__in=bienes_en_traslado) |
                Q(id_bienes__in=bienes_con_solicitud_pendiente)
            ).annotate(
                ultima_asignacion=Max('asignaciondebienes__fecha_de_asignacion'),
                ultimo_evento=Subquery(ultimo_evento_subquery),
                cantidad_asignada=Coalesce(Subquery(stock_subquery), 0)
            ).filter(
                Q(asignaciondebienes__fecha_de_asignacion=F('ultima_asignacion')) &
                Q(cantidad_asignada__gt=0)
            ).exclude(
                Q(ultimo_evento__in=[
                    'DESINCORPORACION', 
                    'MANTENIMIENTO', 
                    'TRASLADO_TEMPORAL', 
                    'PRESTAMO', 
                    'RESGUARDO'
                ])
            ).distinct()
        elif request.user.id_unidadOrganizacional:
            bienes_disponibles = Bienes.objects.filter(
                asignaciondebienes__id_UnidadOrganizacional=request.user.id_unidadOrganizacional,
                asignaciondebienes__fecha_fin_temporal__isnull=True
            ).exclude(
                Q(id_bienes__in=bienes_en_traslado) |
                Q(id_bienes__in=bienes_con_solicitud_pendiente)
            ).annotate(
                ultima_asignacion=Max('asignaciondebienes__fecha_de_asignacion'),
                ultimo_evento=Subquery(ultimo_evento_subquery),
                cantidad_asignada=Coalesce(Subquery(stock_subquery), 0)
            ).filter(
                Q(asignaciondebienes__fecha_de_asignacion=F('ultima_asignacion')) &
                Q(cantidad_asignada__gt=0)
            ).exclude(
                Q(ultimo_evento__in=[
                    'DESINCORPORACION', 
                    'MANTENIMIENTO', 
                    'TRASLADO_TEMPORAL', 
                    'PRESTAMO', 
                    'RESGUARDO'
                ])
            ).distinct()
        else:
            bienes_disponibles = Bienes.objects.none()

        if request.method == 'POST':
            form = DesincorporacionForm(request.POST, user=request.user)
            logger.debug(f"Formulario recibido: {request.POST}")
            
            if form.is_valid():
                try:
                    with transaction.atomic():
                        bien = form.cleaned_data['bien']
                        
                        # Verificación adicional de traslado temporal
                        if AsignacionDeBienes.objects.filter(
                            id_bienes=bien,
                            fecha_fin_temporal__isnull=False,
                            fecha_fin_temporal__gt=timezone.now()
                        ).exists():
                            raise ValidationError("Este bien está actualmente en traslado temporal y no puede ser desincorporado")

                        # Crear la solicitud
                        solicitud = Solicitudes()
                        solicitud.bien_id = bien
                        solicitud.descripcion = form.cleaned_data['motivo']
                        solicitud.usuario_id = request.user
                        solicitud.cantidad_solicitada = 1
                        
                        # Obtener o crear tipo de solicitud
                        tipo_solicitud, _ = TiposDeSolicitud.objects.get_or_create(
                            nombre='Desincorporación',
                            defaults={'descripcion': 'Solicitud de desincorporación de bienes'}
                        )
                        solicitud.id_tipos_de_solicitud = tipo_solicitud
                        solicitud.estado_solicitud = 'pendiente'
                        
                        # Establecer campos de destino como None
                        solicitud.UnidadOrganizacional_destino = None
                        solicitud.departamento_destino = None
                        
                        # Asignar origen de la solicitud
                        if request.user.id_departamentos:
                            solicitud.departamento_solicitante = request.user.id_departamentos
                            solicitud.UnidadOrganizacional_solicitante = None
                        else:
                            solicitud.UnidadOrganizacional_solicitante = request.user.id_unidadOrganizacional
                            solicitud.departamento_solicitante = None

                        # Validar y guardar
                        solicitud.full_clean()
                        solicitud.save()
                        logger.info(f"Solicitud guardada con ID: {solicitud.id_solicitudes}")

                        # Crear entrada en el historial
                        tipo_evento, _ = TiposDeEvento.objects.get_or_create(
                            nombre="SOLICITUD_DESINCORPORACION",
                            defaults={'descripcion': 'Solicitud de desincorporación iniciada'}
                        )
                        
                        # Obtener asignación actual del bien
                        asignacion_actual = bien.asignaciondebienes_set.order_by('-fecha_de_asignacion').first()
                        
                        historial = HistorialBienes.objects.create(
                            bien_id=bien,
                            fecha_evento=timezone.now(),
                            id_tipos_de_evento=tipo_evento,
                            descripcion=f"Solicitud de desincorporación iniciada. Motivo: {solicitud.descripcion}",
                            cantidad_afectada=1,
                            usuario_id=request.user,
                            departamento_origen=(
                                asignacion_actual.id_departamentos if asignacion_actual else None
                            ),
                            UnidadOrganizacional_origen=(
                                asignacion_actual.id_UnidadOrganizacional if asignacion_actual else None
                            ),
                            departamento_destino=None,
                            UnidadOrganizacional_destino=None
                        )

                        # Notificar a los administradores
                        admin_users = Usuario.objects.filter(
                            Q(id_rol_del_usuario__nombre_rol='ADMIN_BIENES') | 
                            Q(is_superuser=True)
                        ).distinct()

                        origen = None
                        if asignacion_actual:
                            if asignacion_actual.id_departamentos:
                                origen = asignacion_actual.id_departamentos.nombre_departamento
                            else:
                                origen = asignacion_actual.id_UnidadOrganizacional.nombre
                        
                        # Crear notificaciones para admins
                        for admin in admin_users:
                            Notificacion.objects.create(
                                usuario=admin,
                                solicitud=solicitud,
                                mensaje=(
                                    f"[ADMIN] Nueva solicitud de desincorporación\n"
                                    f"Creada por: {request.user.get_full_name()}\n"
                                    f"Bien: {bien.nombre} ({bien.numero_de_identificacion})\n"
                                    f"Origen: {origen}\n"
                                    f"ID Solicitud: {solicitud.id_solicitudes}"
                                )
                            )

                        # Notificación para el usuario solicitante
                        Notificacion.objects.create(
                            usuario=request.user,
                            solicitud=solicitud,
                            mensaje=(
                                f"Tu solicitud de desincorporación ha sido creada exitosamente.\n"
                                f"Bien: {bien.nombre} ({bien.numero_de_identificacion})\n"
                                f"ID Solicitud: {solicitud.id_solicitudes}\n"
                                f"Se te notificará cuando sea procesada."
                            )
                        )

                        messages.success(
                            request,
                            f'Solicitud de desincorporación creada con éxito. ID: {solicitud.id_solicitudes}'
                        )

                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return JsonResponse({
                                'success': True,
                                'message': 'Solicitud de desincorporación creada con éxito.',
                                'redirect_url': reverse('lista_solicitudes')
                            })
                        return redirect('lista_solicitudes')

                except ValidationError as e:
                    logger.error(f"Error de validación: {str(e)}")
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': False,
                            'message': str(e),
                            'errors': {'__all__': [str(e)]}
                        }, status=400)
                    messages.error(request, str(e))
                except Exception as e:
                    logger.error(f"Error inesperado: {str(e)}", exc_info=True)
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': False,
                            'message': f'Error al crear la solicitud: {str(e)}'
                        }, status=500)
                    messages.error(request, f'Error al crear la solicitud: {str(e)}')
            else:
                logger.error(f"Errores de validación del formulario: {form.errors}")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': 'Por favor, corrija los errores en el formulario.',
                        'errors': form.errors
                    }, status=400)
        else:
            form = DesincorporacionForm(user=request.user)
            form.fields['bien'].queryset = bienes_disponibles

        return render(request, 'solicitud_desincorporacion.html', {
            'form': form,
            'bienes_disponibles': bienes_disponibles
        })

    except Exception as e:
        logger.error(f"Error general en la vista: {str(e)}", exc_info=True)
        messages.error(request, "Ha ocurrido un error al procesar la solicitud")
        return redirect('lista_solicitudes')


@login_required
@user_passes_test(es_admin_bienes)
def procesar_desincorporacion(request, solicitud_id):
    solicitud = get_object_or_404(
        Solicitudes.objects.select_related(
            'bien_id',
            'usuario_id',
            'departamento_solicitante',
            'UnidadOrganizacional_solicitante',
            'id_tipos_de_solicitud'
        ),
        id_solicitudes=solicitud_id,
        id_tipos_de_solicitud__nombre='Desincorporación'
    )
    
    if request.method == 'POST':
        form = ProcesarDesincorporacionForm(request.POST)
        if form.is_valid():
            action = request.POST.get('action')
            if action == 'aprobar':
                try:
                    with transaction.atomic():
                        # Marcar la solicitud como aprobada
                        solicitud.estado_solicitud = 'aprobada'
                        solicitud.save()

                        bien = solicitud.bien_id
                        cantidad_solicitada = solicitud.cantidad_solicitada or 1
                        
                        if bien:
                            # Actualizar stock
                            stock = Stock.objects.get(bien_id=bien)
                            if stock.cantidad_asignada >= cantidad_solicitada:
                                stock.cantidad_asignada -= cantidad_solicitada
                                stock.cantidad_resguardada += cantidad_solicitada
                                stock.save()

                                logger.info(f"Stock actualizado - ID: {stock.id_stock}")
                                logger.info(f"Cantidad asignada: {stock.cantidad_asignada}")
                                logger.info(f"Cantidad en resguardo: {stock.cantidad_resguardada}")
                                
                                # Eliminar o actualizar la asignación existente
                                try:
                                    if solicitud.departamento_solicitante:
                                        asignacion = AsignacionDeBienes.objects.get(
                                            id_bienes=bien,
                                            id_departamentos=solicitud.departamento_solicitante,
                                            id_UnidadOrganizacional=None
                                        )
                                        logger.info(f"Encontrada asignación de departamento: {asignacion.id_asignacion_bienes}")
                                    elif solicitud.UnidadOrganizacional_solicitante:
                                        asignacion = AsignacionDeBienes.objects.get(
                                            id_bienes=bien,
                                            id_UnidadOrganizacional=solicitud.UnidadOrganizacional_solicitante,
                                            id_departamentos=None
                                        )
                                        logger.info(f"Encontrada asignación de unidad organizacional: {asignacion.id_asignacion_bienes}")
                                    
                                    # Eliminar o actualizar la asignación
                                    if asignacion.cantidad_asignada <= cantidad_solicitada:
                                        logger.info(f"Eliminando asignación: {asignacion.id_asignacion_bienes}")
                                        asignacion.delete()
                                    else:
                                        asignacion.cantidad_asignada -= cantidad_solicitada
                                        asignacion.save()
                                        logger.info(f"Actualizada asignación: {asignacion.id_asignacion_bienes}")
                                
                                except AsignacionDeBienes.DoesNotExist:
                                    logger.warning("No se encontró asignación para el bien")
                                
                                # Obtener o crear departamento de resguardo
                                depto_resguardo, created = Departamentos.objects.get_or_create(
                                    nombre_departamento="Bienes en Resguardo",
                                    defaults={
                                        'codigo_departamento': 'RESG',
                                        'descripcion': 'Departamento para bienes en resguardo'
                                    }
                                )

                                logger.info(f"Departamento de resguardo: {depto_resguardo.id_departamentos}")
                                
                                # Crear nueva asignación en resguardo
                                nueva_asignacion = AsignacionDeBienes.objects.create(
                                    id_bienes=bien,
                                    id_departamentos=depto_resguardo,
                                    id_UnidadOrganizacional=None,
                                    cantidad_asignada=cantidad_solicitada,
                                    fecha_de_asignacion=timezone.now()
                                )

                                logger.info(f"Nueva asignación creada: {nueva_asignacion.id_asignacion_bienes}")
                                
                                # Registrar eventos en el historial
                                tipo_evento_resguardo, _ = TiposDeEvento.objects.get_or_create(
                                    nombre="RESGUARDO",
                                    defaults={'descripcion': 'Movimiento a resguardo'}
                                )
                                
                                historial_resguardo = HistorialBienes.objects.create(
                                    bien_id=bien,
                                    fecha_evento=timezone.now(),
                                    id_tipos_de_evento=tipo_evento_resguardo,
                                    descripcion=f"Bien movido a resguardo para desincorporación. Cantidad: {cantidad_solicitada}. Motivo: {solicitud.descripcion}",
                                    cantidad_afectada=cantidad_solicitada,
                                    usuario_id=request.user,
                                    departamento_origen=solicitud.departamento_solicitante,
                                    UnidadOrganizacional_origen=solicitud.UnidadOrganizacional_solicitante,
                                    departamento_destino=depto_resguardo,
                                    UnidadOrganizacional_destino=None
                                )

                                logger.info(f"Historial de resguardo creado: {historial_resguardo.id}")
                                
                                tipo_evento_aprobacion, _ = TiposDeEvento.objects.get_or_create(
                                    nombre="APROBACION_DESINCORPORACION",
                                    defaults={'descripcion': 'Aprobación de desincorporación'}
                                )
                                
                                historial_aprobacion = HistorialBienes.objects.create(
                                    bien_id=bien,
                                    fecha_evento=timezone.now(),
                                    id_tipos_de_evento=tipo_evento_aprobacion,
                                    descripcion=f"Solicitud de desincorporación aprobada. Cantidad: {cantidad_solicitada}",
                                    cantidad_afectada=cantidad_solicitada,
                                    usuario_id=request.user,
                                    departamento_origen=solicitud.departamento_solicitante,
                                    UnidadOrganizacional_origen=solicitud.UnidadOrganizacional_solicitante,
                                    departamento_destino=depto_resguardo,
                                    UnidadOrganizacional_destino=None
                                )

                                logger.info(f"Historial de aprobación creado: {historial_aprobacion.id}")
                                
                                # Registrar el movimiento
                                movimiento = MovimientosBienes.objects.create(
                                    bien_id=bien,
                                    # Si viene de departamento
                                    departamento_solicitante_id=solicitud.departamento_solicitante if solicitud.departamento_solicitante else None,
                                    UnidadOrganizacional_solicitante=solicitud.UnidadOrganizacional_solicitante if not solicitud.departamento_solicitante else None,
                                    # Destino es siempre el departamento de resguardo
                                    departamento_destino_id=depto_resguardo,
                                    UnidadOrganizacional_destino=None,
                                    fecha_movimiento=timezone.now().date(),
                                    fecha_entrega=timezone.now().date(),
                                    tipo_movimiento='Resguardo para Desincorporación',
                                    cantidad=cantidad_solicitada,
                                    usuario_id=request.user,
                                    estado_solicitud='aprobada',
                                    descripcion=solicitud.descripcion
                                )

                                logger.info(f"Movimiento creado: {movimiento.id}")

                                # Notificar al usuario
                                origen = (
                                    solicitud.departamento_solicitante.nombre_departamento 
                                    if solicitud.departamento_solicitante 
                                    else solicitud.UnidadOrganizacional_solicitante.nombre
                                )
                                
                                notificacion = Notificacion.objects.create(
                                    usuario=solicitud.usuario_id,
                                    solicitud=solicitud,
                                    mensaje=f"Su solicitud de desincorporación para el bien '{bien.nombre}' de {origen} ha sido aprobada."
                                )

                                logger.info(f"Notificación creada: {notificacion.id}")
                                
                                messages.success(request, f'Solicitud de desincorporación aprobada. {cantidad_solicitada} unidad(es) del bien han sido movidas a resguardo.')
                            else:
                                messages.error(request, 'No hay suficientes bienes asignados para procesar esta solicitud.')
                        else:
                            messages.error(request, 'No se encontró el bien asociado a esta solicitud.')
                    
                except Exception as e:
                    logger.error(f"Error al procesar la solicitud de desincorporación: {str(e)}", exc_info=True)
                    messages.error(request, f'Ocurrió un error al procesar la solicitud: {str(e)}')
            
            elif action == 'rechazar':
                motivo_rechazo = form.cleaned_data['motivo_rechazo']
                if not motivo_rechazo:
                    messages.error(request, 'Debe proporcionar un motivo para rechazar la solicitud.')
                    return render(request, 'procesar_desincorporacion.html', {'solicitud': solicitud, 'form': form})
                
                try:
                    with transaction.atomic():
                        solicitud.estado_solicitud = 'rechazada'
                        solicitud.motivo_rechazo = motivo_rechazo
                        solicitud.save()
                        
                        # Registrar en HistorialBienes para el rechazo
                        tipo_evento_rechazo, _ = TiposDeEvento.objects.get_or_create(
                            nombre="RECHAZO_DESINCORPORACION",
                            defaults={'descripcion': 'Rechazo de solicitud de desincorporación'}
                        )
                        
                        historial = HistorialBienes.objects.create(
                            bien_id=solicitud.bien_id,
                            fecha_evento=timezone.now(),
                            id_tipos_de_evento=tipo_evento_rechazo,
                            descripcion=f"Solicitud de desincorporación rechazada. Motivo: {motivo_rechazo}",
                            cantidad_afectada=solicitud.cantidad_solicitada or 1,
                            usuario_id=request.user,
                            departamento_origen=solicitud.departamento_solicitante,
                            UnidadOrganizacional_origen=solicitud.UnidadOrganizacional_solicitante,
                            departamento_destino=None,
                            UnidadOrganizacional_destino=None
                        )

                        logger.info(f"Historial de rechazo creado: {historial.id}")
                        
                        origen = (
                            solicitud.departamento_solicitante.nombre_departamento 
                            if solicitud.departamento_solicitante 
                            else solicitud.UnidadOrganizacional_solicitante.nombre
                        )
                        
                        # Crear notificación para el usuario
                        notificacion = Notificacion.objects.create(
                            usuario=solicitud.usuario_id,
                            solicitud=solicitud,
                            mensaje=f"Su solicitud de desincorporación para el bien '{solicitud.bien_id.nombre}' de {origen} ha sido rechazada. Motivo: {motivo_rechazo}"
                        )

                        logger.info(f"Notificación de rechazo creada: {notificacion.id}")
                        
                        messages.info(request, 'Solicitud de desincorporación rechazada.')
                
                except Exception as e:
                    logger.error(f"Error al rechazar la solicitud: {str(e)}", exc_info=True)
                    messages.error(request, f'Ocurrió un error al rechazar la solicitud: {str(e)}')
            
            return redirect('lista_solicitudes')
    else:
        form = ProcesarDesincorporacionForm()

    context = {
        'solicitud': solicitud,
        'form': form,
    }
    return render(request, 'procesar_desincorporacion.html', context)

    

@login_required
def bienes_usuario(request):
    fecha_actual = timezone.now().date()
    
    # Subconsulta para obtener el último estado del historial
    ultimo_estado_historial = HistorialBienes.objects.filter(
        bien_id=OuterRef('id_bienes'),
    ).order_by('-fecha_evento').values(
        'id_tipos_de_evento__nombre',
        'descripcion',
        'departamento_destino__nombre_departamento',
        'departamento_origen__nombre_departamento',
        'UnidadOrganizacional_destino__nombre',
        'UnidadOrganizacional_origen__nombre'
    )[:1]

    # Query base para las asignaciones
    asignaciones = AsignacionDeBienes.objects.select_related(
        'id_bienes',
        'id_bienes__stock',
        'id_departamentos',
        'id_UnidadOrganizacional'
    )

    # Determinar tipo de ubicación y filtrar
    if request.user.id_departamentos:
        asignaciones = asignaciones.filter(id_departamentos=request.user.id_departamentos)
        ubicacion_actual = request.user.id_departamentos
        es_departamento = True
    elif request.user.id_unidadOrganizacional:
        asignaciones = asignaciones.filter(id_UnidadOrganizacional=request.user.id_unidadOrganizacional)
        ubicacion_actual = request.user.id_unidadOrganizacional
        es_departamento = False
    else:
        messages.error(request, "El usuario no tiene una ubicación asignada.")
        return redirect('index')

    # Anotar las asignaciones con la información del historial
    asignaciones = asignaciones.annotate(
        ultimo_estado=Subquery(
            ultimo_estado_historial.values('id_tipos_de_evento__nombre')[:1]
        ),
        departamento_destino_nombre=Subquery(
            ultimo_estado_historial.values('departamento_destino__nombre_departamento')[:1]
        ),
        departamento_origen_nombre=Subquery(
            ultimo_estado_historial.values('departamento_origen__nombre_departamento')[:1]
        ),
        unidad_destino_nombre=Subquery(
            ultimo_estado_historial.values('UnidadOrganizacional_destino__nombre')[:1]
        ),
        unidad_origen_nombre=Subquery(
            ultimo_estado_historial.values('UnidadOrganizacional_origen__nombre')[:1]
        ),
        descripcion_evento=Subquery(
            ultimo_estado_historial.values('descripcion')[:1]
        ),
        estado_calculado=Case(
            # Traslado Temporal para Departamento
            When(
                Q(ultimo_estado='TRASLADO_TEMPORAL') & Q(id_departamentos__isnull=False),
                then=Case(
                    When(
                        departamento_destino_nombre=F('id_departamentos__nombre_departamento'),
                        then=Concat(
                            Value('Prestado desde '),
                            F('departamento_origen_nombre'),
                            output_field=CharField()
                        )
                    ),
                    When(
                        departamento_origen_nombre=F('id_departamentos__nombre_departamento'),
                        then=Concat(
                            Value('Prestado a '),
                            F('departamento_destino_nombre'),
                            output_field=CharField()
                        )
                    ),
                    default=Value('Traslado Temporal'),
                    output_field=CharField(),
                )
            ),
            # Traslado Temporal para Unidad Organizacional
            When(
                Q(ultimo_estado='TRASLADO_TEMPORAL') & Q(id_UnidadOrganizacional__isnull=False),
                then=Case(
                    When(
                        unidad_destino_nombre=F('id_UnidadOrganizacional__nombre'),
                        then=Concat(
                            Value('Prestado desde '),
                            F('unidad_origen_nombre'),
                            output_field=CharField()
                        )
                    ),
                    When(
                        unidad_origen_nombre=F('id_UnidadOrganizacional__nombre'),
                        then=Concat(
                            Value('Prestado a '),
                            F('unidad_destino_nombre'),
                            output_field=CharField()
                        )
                    ),
                    default=Value('Traslado Temporal'),
                    output_field=CharField(),
                )
            ),
            When(ultimo_estado='DESINCORPORACION', then=Value('Desincorporado')),
            When(id_bienes__stock__cantidad_resguardada__gt=0, then=Value('En Resguardo')),
            When(id_bienes__stock__cantidad_en_mantenimiento__gt=0, then=Value('En Mantenimiento')),
            When(id_bienes__stock__cantidad_asignada__gt=0, then=Value('Asignado')),
            When(id_bienes__stock__cantidad_disponible__gt=0, then=Value('Disponible')),
            default=Value('Asignado'),
            output_field=CharField(),
        )
    ).exclude(
        id_bienes__stock__cantidad_resguardada__gt=0
    )

    context = {
        'ubicacion': ubicacion_actual,
        'ubicacion_tipo': 'Departamento' if es_departamento else 'Unidad Organizacional',
        'bienes_asignados': asignaciones
    }
    
    return render(request, 'bienes_usuarios.html', context)

@login_required
@user_passes_test(lambda u: u.id_rol_del_usuario.nombre_rol == 'ADMIN_BIENES')
def bienes_admin(request):
    bienes = Bienes.objects.select_related('stock').all()
    bienes_filtrados = []

    for bien in bienes:
        total_asignado = AsignacionDeBienes.objects.filter(id_bienes=bien).aggregate(Sum('cantidad_asignada'))['cantidad_asignada__sum'] or 0
        
        if total_asignado == 0 or bien.stock.cantidad_resguardada > 0:
            bienes_filtrados.append({
                'bien': bien,
                'total_asignado': total_asignado,
            })

    context = {
        'bienes': bienes_filtrados
    }
    return render(request, 'bienes_admin.html', context)



def es_admin_bienes(user):
    return user.id_rol_del_usuario and user.id_rol_del_usuario.nombre_rol == 'ADMIN_BIENES'



@login_required
@user_passes_test(es_admin_bienes)
def bienes_resguardados(request):
    logger.info(f"Vista bienes_resguardados accedida por usuario: {request.user}")
    logger.debug(f"Método de la solicitud: {request.method}")
    logger.debug(f"Datos POST: {request.POST}")

    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        bien_id = request.POST.get('bien_id')
        accion = request.POST.get('accion')
        
        logger.info(f"Acción solicitada: {accion} para bien_id: {bien_id}")
        
        try:
            with transaction.atomic():
                bien = Bienes.objects.get(id_bienes=bien_id)
                stock = Stock.objects.get(bien_id=bien)
                
                logger.debug(f"Bien encontrado: {bien.nombre}, Stock actual: Resguardado={stock.cantidad_resguardada}")
                
                if accion == 'desincorporar':
                    valor_desincorporacion = request.POST.get('valor_desincorporacion')
                    
                    if not valor_desincorporacion:
                        return JsonResponse({
                            'success': False,
                            'message': 'El valor de desincorporación es requerido.'
                        })
                    
                    if stock.cantidad_resguardada > 0:
                        # Actualizar stock
                        stock.cantidad_resguardada -= 1
                        stock.cantidad_desincorporada += 1
                        stock.save()
                        
                        # Eliminar todas las asignaciones existentes
                        AsignacionDeBienes.objects.filter(id_bienes=bien).delete()
                        
                        # Actualizar el bien
                        bien.desincorporacion = valor_desincorporacion
                        bien.save()
                        
                        # Registrar evento de desincorporación
                        tipo_evento, _ = TiposDeEvento.objects.get_or_create(
                            nombre="DESINCORPORACION",
                            defaults={'descripcion': 'Desincorporación de bienes'}
                        )
                        
                        # Crear registro en historial con departamentos en null
                        HistorialBienes.objects.create(
                            bien_id=bien,
                            fecha_evento=timezone.now(),
                            id_tipos_de_evento=tipo_evento,
                            descripcion=f"Bien desincorporado desde resguardo con valor de {valor_desincorporacion} Bs",
                            cantidad_afectada=1,
                            usuario_id=request.user,
                            departamento_origen=None,
                            departamento_destino=None,
                            UnidadOrganizacional_origen=None,
                            UnidadOrganizacional_destino=None
                        )
                        
                        logger.info(f"Bien {bien.nombre} desincorporado con valor {valor_desincorporacion} Bs y desvinculado de todos los departamentos")
                        return JsonResponse({
                            'success': True,
                            'message': f'El bien {bien.nombre} ha sido desincorporado exitosamente.',
                            'valor': valor_desincorporacion
                        })
                    else:
                        return JsonResponse({
                            'success': False,
                            'message': 'No hay unidades resguardadas para desincorporar.'
                        })
                
                elif accion == 'devolver':
                    if stock.cantidad_resguardada > 0:
                        # Buscar la última ubicación válida en el historial
                        ultima_ubicacion = HistorialBienes.objects.filter(
                            bien_id=bien,
                            id_tipos_de_evento__nombre__in=['ASIGNACION', 'TRASLADO_PERMANENTE']
                        ).exclude(
                            id_tipos_de_evento__nombre__in=['RESGUARDO', 'MANTENIMIENTO', 'SOLICITUD_DESINCORPORACION', 'APROBACION_DESINCORPORACION']
                        ).order_by('-fecha_evento').first()

                        if ultima_ubicacion:
                            # Actualizar stock
                            stock.cantidad_resguardada -= 1
                            stock.cantidad_asignada += 1
                            stock.save()

                            # Determinar la ubicación de destino
                            unidad_destino = ultima_ubicacion.UnidadOrganizacional_destino
                            departamento_destino = ultima_ubicacion.departamento_destino

                            # Crear o actualizar asignación
                            if unidad_destino:
                                try:
                                    asignacion = AsignacionDeBienes.objects.get(
                                        id_bienes=bien,
                                        id_UnidadOrganizacional=unidad_destino
                                    )
                                    asignacion.cantidad_asignada = F('cantidad_asignada') + 1
                                    asignacion.fecha_de_asignacion = timezone.now()
                                    asignacion.save()
                                except AsignacionDeBienes.DoesNotExist:
                                    asignacion = AsignacionDeBienes.objects.create(
                                        id_bienes=bien,
                                        id_UnidadOrganizacional=unidad_destino,
                                        cantidad_asignada=1,
                                        fecha_de_asignacion=timezone.now()
                                    )
                                ubicacion_nombre = unidad_destino.nombre
                            else:
                                try:
                                    asignacion = AsignacionDeBienes.objects.get(
                                        id_bienes=bien,
                                        id_departamentos=departamento_destino
                                    )
                                    asignacion.cantidad_asignada = F('cantidad_asignada') + 1
                                    asignacion.fecha_de_asignacion = timezone.now()
                                    asignacion.save()
                                except AsignacionDeBienes.DoesNotExist:
                                    asignacion = AsignacionDeBienes.objects.create(
                                        id_bienes=bien,
                                        id_departamentos=departamento_destino,
                                        cantidad_asignada=1,
                                        fecha_de_asignacion=timezone.now()
                                    )
                                ubicacion_nombre = departamento_destino.nombre_departamento

                            # Registrar en historial
                            tipo_evento, _ = TiposDeEvento.objects.get_or_create(
                                nombre="DEVOLUCION",
                                defaults={'descripcion': 'Devolución desde resguardo'}
                            )
                            
                            HistorialBienes.objects.create(
                                bien_id=bien,
                                fecha_evento=timezone.now(),
                                id_tipos_de_evento=tipo_evento,
                                descripcion=f"Bien devuelto desde resguardo a {ubicacion_nombre}",
                                cantidad_afectada=1,
                                usuario_id=request.user,
                                UnidadOrganizacional_destino=unidad_destino,
                                departamento_destino=departamento_destino
                            )
                            
                            logger.info(f"Bien {bien.nombre} devuelto exitosamente a {ubicacion_nombre}")
                            return JsonResponse({
                                'success': True,
                                'message': f'El bien ha sido devuelto exitosamente a {ubicacion_nombre}'
                            })
                        else:
                            return JsonResponse({
                                'success': False,
                                'message': 'No se encontró una ubicación válida para la devolución'
                            })
                    else:
                        return JsonResponse({
                            'success': False,
                            'message': 'No hay unidades resguardadas para devolver.'
                        })
                else:
                    return JsonResponse({
                        'success': False,
                        'message': 'Acción no reconocida.'
                    })

        except Bienes.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'El bien seleccionado no existe.'
            })
        except Stock.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'No se encontró el stock para este bien.'
            })
        except Exception as e:
            logger.error(f"Error al procesar el bien: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'message': f'Ocurrió un error: {str(e)}'
            })

    # GET request - mostrar lista de bienes resguardados
    bienes_resguardados = Bienes.objects.filter(stock__cantidad_resguardada__gt=0).select_related('stock')
    logger.debug(f"Número de bienes resguardados encontrados: {bienes_resguardados.count()}")
    
    context = {
        'bienes_resguardados': bienes_resguardados
    }
    return render(request, 'bienes_resguardados.html', context)

@require_http_methods(["GET"])
@login_required
def obtener_departamento_destino(request, bien_id):
    try:
        bien = Bienes.objects.get(id_bienes=bien_id)
        logger.debug(f"Buscando ubicación destino para bien: {bien.nombre}")
        
        # Estados que indican cambio de ubicación válido
        ESTADOS_VALIDOS = [
            'ASIGNACION',
            'TRASLADO_PERMANENTE',
            'FIN_MANTENIMIENTO'
        ]
        
        # Estados y ubicaciones temporales a ignorar
        UBICACIONES_TEMPORALES = [
            'Bienes en Resguardo',
            'Bienes en Mantenimiento'
        ]
        
        # Obtener el historial ordenado por fecha descendente
        historial = HistorialBienes.objects.filter(
            bien_id=bien_id
        ).exclude(
            id_tipos_de_evento__nombre__in=['RESGUARDO', 'SOLICITUD_DESINCORPORACION', 'APROBACION_DESINCORPORACION']
        ).select_related(
            'id_tipos_de_evento',
            'departamento_destino',
            'UnidadOrganizacional_destino'
        ).order_by('-fecha_evento')
        
        logger.debug(f"Total de eventos encontrados: {historial.count()}")
        
        # Buscar la última ubicación válida
        for evento in historial:
            logger.debug(f"""
                Procesando evento:
                - Tipo: {evento.id_tipos_de_evento.nombre}
                - Unidad destino: {evento.UnidadOrganizacional_destino.nombre if evento.UnidadOrganizacional_destino else 'None'}
                - Depto destino: {evento.departamento_destino.nombre_departamento if evento.departamento_destino else 'None'}
                - Fecha: {evento.fecha_evento}
            """)
            
            # Verificar si es un evento válido y tiene una ubicación no temporal
            if evento.id_tipos_de_evento.nombre in ESTADOS_VALIDOS:
                # Primero verificar UnidadOrganizacional_destino
                if evento.UnidadOrganizacional_destino and \
                   evento.UnidadOrganizacional_destino.nombre not in UBICACIONES_TEMPORALES:
                    return JsonResponse({
                        'success': True,
                        'departamento_nombre': evento.UnidadOrganizacional_destino.nombre,
                        'fecha_asignacion': evento.fecha_evento.strftime('%d/%m/%Y')
                    })
                
                # Luego verificar departamento_destino
                if evento.departamento_destino and \
                   evento.departamento_destino.nombre_departamento not in UBICACIONES_TEMPORALES:
                    return JsonResponse({
                        'success': True,
                        'departamento_nombre': evento.departamento_destino.nombre_departamento,
                        'fecha_asignacion': evento.fecha_evento.strftime('%d/%m/%Y')
                    })
        
        return JsonResponse({
            'success': False,
            'message': 'No se encontró una ubicación de asignación válida para este bien.'
        })
            
    except Exception as e:
        logger.error(f"Error al obtener ubicación destino: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': 'Error al obtener la información de la ubicación.'
        })


@login_required
def crear_solicitud_permanente(request):
    if request.method == 'POST':
        form = SolicitudPermanenteForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    solicitud = form.save(commit=False)
                    solicitud.usuario_id = request.user
                    
                    # Asignar ubicación según el tipo de usuario
                    if request.user.id_departamentos:
                        solicitud.departamento_solicitante = request.user.id_departamentos
                        solicitud.UnidadOrganizacional_solicitante = None
                        origen = f"departamento {request.user.id_departamentos.nombre_departamento}"
                    elif request.user.id_unidadOrganizacional:
                        solicitud.UnidadOrganizacional_solicitante = request.user.id_unidadOrganizacional
                        solicitud.departamento_solicitante = None
                        origen = f"unidad organizacional {request.user.id_unidadOrganizacional.nombre}"
                    else:
                        raise ValidationError("El usuario debe pertenecer a un departamento o unidad organizacional")
                    
                    tipo_solicitud = TiposDeSolicitud.objects.get_or_create(
                        nombre='Traslado Permanente',
                        defaults={'descripcion': 'Solicitud de traslado permanente de bien'}
                    )[0]
                    
                    solicitud.id_tipos_de_solicitud = tipo_solicitud
                    solicitud.estado_solicitud = 'pendiente'
                    solicitud.save()

                    # Notificar a administradores
                    admins = Usuario.objects.filter(
                        Q(id_rol_del_usuario__nombre_rol='ADMIN_BIENES') | 
                        Q(is_superuser=True)
                    ).distinct()

                    for admin in admins:
                        Notificacion.objects.create(
                            usuario=admin,
                            solicitud=solicitud,
                            mensaje=(
                                f"[ADMIN] Nueva solicitud de traslado permanente creada por "
                                f"{request.user.get_full_name()} desde {origen}\n"
                                f"ID: {solicitud.id_solicitudes}\n"
                                f"Descripción: {solicitud.descripcion}"
                            )
                        )

                    # Notificar al usuario
                    Notificacion.objects.create(
                        usuario=request.user,
                        solicitud=solicitud,
                        mensaje="Su solicitud de traslado permanente ha sido creada exitosamente."
                    )

                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': True,
                            'message': 'Solicitud de traslado permanente creada con éxito.',
                            'redirect_url': reverse('lista_solicitudes')
                        })

                    messages.success(request, 'Solicitud de traslado permanente creada con éxito.')
                    return redirect('lista_solicitudes')

            except ValidationError as e:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': str(e)
                    }, status=400)
                messages.error(request, str(e))
            except Exception as e:
                logger.error(f"Error al crear solicitud permanente: {str(e)}", exc_info=True)
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': f'Error al crear la solicitud: {str(e)}'
                    }, status=500)
                messages.error(request, f'Error al crear la solicitud: {str(e)}')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': 'Por favor corrija los errores en el formulario',
                    'errors': form.errors
                }, status=400)
    else:
        form = SolicitudPermanenteForm()
    
    return render(request, 'crear_solicitud_permanente.html', {'form': form})




def es_admin_bienes(user):
    return user.id_rol_del_usuario.nombre_rol == 'ADMIN_BIENES'



@login_required
@user_passes_test(es_admin_bienes)
def procesar_solicitud_permanente(request, solicitud_id):
    logger.debug(f"\n{'='*50}\nInicio de procesamiento de solicitud {solicitud_id}")
    
    tipo_evento, _ = TiposDeEvento.objects.get_or_create(
        nombre='TRASLADO_PERMANENTE',
        defaults={'descripcion': 'Traslado permanente de bien'}
    )
    
    solicitud = get_object_or_404(
        Solicitudes.objects.select_related(
            'bien_id',
            'usuario_id',
            'departamento_solicitante',
            'UnidadOrganizacional_solicitante'
        ), 
        id_solicitudes=solicitud_id, 
        id_tipos_de_solicitud__nombre='Traslado Permanente'
    )
    
    logger.debug(f"Solicitud encontrada: {solicitud.id_solicitudes}")
    logger.debug(f"Unidad solicitante: {solicitud.UnidadOrganizacional_solicitante}")
    logger.debug(f"Departamento solicitante: {solicitud.departamento_solicitante}")

    # Construir QuerySet base para bienes disponibles
    bienes_disponibles = Bienes.objects.filter(
        condicion='Operativo',
        asignaciondebienes__fecha_fin_temporal__isnull=True,
        asignaciondebienes__cantidad_asignada__gt=0
    ).select_related(
        'stock'
    ).prefetch_related(
        'asignaciondebienes_set',
        'asignaciondebienes_set__id_departamentos',
        'asignaciondebienes_set__id_UnidadOrganizacional',
        'asignaciondebienes_set__id_departamentos__UnidadOrganizacional'
    )

    # Filtrar según el tipo de solicitud
    if solicitud.UnidadOrganizacional_solicitante:
        bienes_disponibles = bienes_disponibles.exclude(
            asignaciondebienes__id_UnidadOrganizacional=solicitud.UnidadOrganizacional_solicitante
        )
        logger.debug(f"Filtrando bienes de la unidad: {solicitud.UnidadOrganizacional_solicitante.nombre}")
    elif solicitud.departamento_solicitante:
        bienes_disponibles = bienes_disponibles.exclude(
            asignaciondebienes__id_departamentos=solicitud.departamento_solicitante
        )
        logger.debug(f"Filtrando bienes del departamento: {solicitud.departamento_solicitante.nombre_departamento}")

    # Excluir bienes en mantenimiento si existe el departamento
    try:
        depto_mantenimiento = Departamentos.objects.get(nombre_departamento='Bienes en Mantenimiento')
        bienes_disponibles = bienes_disponibles.exclude(
            asignaciondebienes__id_departamentos=depto_mantenimiento
        )
    except Departamentos.DoesNotExist:
        pass

    bienes_disponibles = bienes_disponibles.distinct()

    if request.method == 'POST':
        action = request.POST.get('action')
        logger.debug(f"Acción recibida: {action}")
        
        if action == 'aprobar':
            logger.debug("Procesando aprobación")
            form = ProcesarSolicitudPermanenteForm(request.POST, instance=solicitud)
            logger.debug(f"Form data: {request.POST}")
            
            if form.is_valid():
                try:
                    with transaction.atomic():
                        bien = form.cleaned_data['bien_id']
                        logger.debug(f"Bien seleccionado: {bien.id_bienes}")
                        
                        # Obtener la asignación actual
                        asignacion_actual = AsignacionDeBienes.objects.filter(
                            id_bienes=bien,
                            fecha_fin_temporal__isnull=True
                        ).first()

                        if not asignacion_actual:
                            raise ValueError("El bien no tiene una asignación actual válida.")

                        logger.debug(f"Asignación actual encontrada: {asignacion_actual.id_asignacion_bienes}")

                        # Crear nueva asignación para el destino
                        nueva_asignacion = AsignacionDeBienes.objects.create(
                            id_bienes=bien,
                            id_departamentos=solicitud.departamento_solicitante,
                            id_UnidadOrganizacional=solicitud.UnidadOrganizacional_solicitante,
                            cantidad_asignada=1,
                            fecha_de_asignacion=timezone.now()
                        )
                        logger.debug(f"Nueva asignación creada: {nueva_asignacion.id_asignacion_bienes}")

                        # Actualizar o eliminar la asignación actual
                        if asignacion_actual.cantidad_asignada > 1:
                            asignacion_actual.cantidad_asignada -= 1
                            asignacion_actual.save()
                        else:
                            asignacion_actual.delete()

                        # Registrar en historial
                        origen_texto = None
                        if asignacion_actual.id_departamentos:
                            origen_texto = f"departamento {asignacion_actual.id_departamentos.nombre_departamento}"
                        elif asignacion_actual.id_UnidadOrganizacional:
                            origen_texto = f"unidad {asignacion_actual.id_UnidadOrganizacional.nombre}"

                        destino_texto = None
                        if solicitud.departamento_solicitante:
                            destino_texto = f"departamento {solicitud.departamento_solicitante.nombre_departamento}"
                        elif solicitud.UnidadOrganizacional_solicitante:
                            destino_texto = f"unidad {solicitud.UnidadOrganizacional_solicitante.nombre}"

                        HistorialBienes.objects.create(
                            bien_id=bien,
                            fecha_evento=timezone.now(),
                            id_tipos_de_evento=tipo_evento,
                            descripcion=f"Traslado permanente desde {origen_texto} hacia {destino_texto}",
                            cantidad_afectada=1,
                            usuario_id=request.user,
                            departamento_origen=asignacion_actual.id_departamentos,
                            UnidadOrganizacional_origen=asignacion_actual.id_UnidadOrganizacional,
                            departamento_destino=solicitud.departamento_solicitante,
                            UnidadOrganizacional_destino=solicitud.UnidadOrganizacional_solicitante
                        )

                        # Actualizar stock
                        stock = Stock.objects.get(bien_id=bien)
                        stock.cantidad_asignada = AsignacionDeBienes.objects.filter(
                            id_bienes=bien,
                            fecha_fin_temporal__isnull=True
                        ).aggregate(total=Sum('cantidad_asignada'))['total'] or 0
                        stock.save()

                        # Actualizar solicitud
                        solicitud.estado_solicitud = 'aprobada'
                        solicitud.bien_id = bien
                        solicitud.cantidad_solicitada = 1
                        solicitud.save()

                        # Crear notificación
                        Notificacion.objects.create(
                            usuario=solicitud.usuario_id,
                            solicitud=solicitud,
                            mensaje=f"Su solicitud de traslado permanente para {bien.nombre} desde {origen_texto} hacia {destino_texto} ha sido aprobada."
                        )

                        messages.success(request, 'Solicitud de traslado permanente aprobada con éxito.')
                        return redirect('lista_solicitudes')

                except ValueError as e:
                    logger.error(f"Error de validación: {str(e)}")
                    messages.error(request, str(e))
                except Exception as e:
                    logger.error(f"Error al procesar la aprobación: {str(e)}", exc_info=True)
                    messages.error(request, f'Error al procesar la solicitud: {str(e)}')
            else:
                logger.debug(f"Form errors: {form.errors}")
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")

        elif action == 'rechazar':
            motivo_rechazo = request.POST.get('motivo_rechazo')
            if not motivo_rechazo:
                messages.error(request, 'Debe proporcionar un motivo para rechazar la solicitud.')
                return render(request, 'procesar_solicitud_permanente.html', 
                            {'solicitud': solicitud, 'form': ProcesarSolicitudPermanenteForm()})

            try:
                with transaction.atomic():
                    solicitud.estado_solicitud = 'rechazada'
                    solicitud.motivo_rechazo = motivo_rechazo
                    solicitud.save()

                    Notificacion.objects.create(
                        usuario=solicitud.usuario_id,
                        solicitud=solicitud,
                        mensaje=f"Su solicitud de traslado permanente ha sido rechazada. Motivo: {motivo_rechazo}"
                    )

                    messages.success(request, 'Solicitud de traslado permanente rechazada.')
                    return redirect('lista_solicitudes')

            except Exception as e:
                logger.error(f"Error al rechazar la solicitud: {str(e)}", exc_info=True)
                messages.error(request, f'Error al rechazar la solicitud: {str(e)}')
                return redirect('lista_solicitudes')

    form = ProcesarSolicitudPermanenteForm(instance=solicitud)
    form.fields['bien_id'].queryset = bienes_disponibles

    context = {
        'form': form,
        'solicitud': solicitud,
        'bienes_count': bienes_disponibles.count(),
    }
    return render(request, 'procesar_solicitud_permanente.html', context)



@login_required
def crear_solicitud_temporal(request):
    if request.method == 'POST':
        form = CrearSolicitudTemporalForm(
            request.POST, 
            user=request.user
        )
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Obtener o crear el tipo de solicitud
                    tipo_solicitud = TiposDeSolicitud.objects.get_or_create(
                        nombre='Traslado Temporal',
                        defaults={'descripcion': 'Solicitud de traslado temporal de bien'}
                    )[0]
                    
                    solicitud = form.save(commit=False)
                    solicitud.id_tipos_de_solicitud = tipo_solicitud
                    solicitud.estado_solicitud = 'pendiente'
                    
                    # Log para depuración
                    logger.debug(f"Descripción antes de guardar: {solicitud.descripcion}")
                    logger.debug(f"Usuario: {solicitud.usuario_id}")
                    logger.debug(f"Departamento: {solicitud.departamento_solicitante}")
                    logger.debug(f"Unidad Org.: {solicitud.UnidadOrganizacional_solicitante}")
                    
                    solicitud.save()
                    logger.info(f"Solicitud guardada con ID: {solicitud.id_solicitudes}")

                    # Crear notificaciones
                    origen = (
                        f"departamento {request.user.id_departamentos.nombre_departamento}"
                        if request.user.id_departamentos
                        else f"unidad organizacional {request.user.id_unidadOrganizacional.nombre}"
                    )

                    # Notificar a administradores
                    admin_users = Usuario.objects.filter(
                        Q(id_rol_del_usuario__nombre_rol='ADMIN_BIENES') | 
                        Q(is_superuser=True)
                    ).distinct()

                    for admin in admin_users:
                        Notificacion.objects.create(
                            usuario=admin,
                            solicitud=solicitud,
                            mensaje=(
                                f"[ADMIN] Nueva solicitud de traslado temporal creada por "
                                f"{request.user.get_full_name()} desde {origen}\n"
                                f"ID: {solicitud.id_solicitudes}\n"
                                f"Descripción: {solicitud.descripcion}"
                            )
                        )

                    # Notificar al usuario
                    Notificacion.objects.create(
                        usuario=request.user,
                        solicitud=solicitud,
                        mensaje="Su solicitud de traslado temporal ha sido creada exitosamente. Se le notificará cuando sea procesada."
                    )

                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': True,
                            'message': 'Solicitud de traslado temporal creada con éxito.',
                            'redirect_url': reverse('lista_solicitudes')
                        })

                    messages.success(request, 'Solicitud de traslado temporal creada con éxito.')
                    return redirect('lista_solicitudes')

            except ValidationError as e:
                logger.error(f"Error de validación: {str(e)}")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': str(e),
                        'errors': e.message_dict
                    }, status=400)
                messages.error(request, str(e))
            except Exception as e:
                logger.error(f"Error al crear solicitud temporal: {str(e)}", exc_info=True)
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': f'Error al crear la solicitud: {str(e)}'
                    }, status=500)
                messages.error(request, f'Error al crear la solicitud: {str(e)}')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': 'Por favor, corrija los errores en el formulario.',
                    'errors': form.errors
                }, status=400)
    else:
        form = CrearSolicitudTemporalForm(user=request.user)
    
    return render(request, 'crear_solicitud_temporal.html', {'form': form})


def get_bien_info(request, bien_id):
    bien = get_object_or_404(Bienes, id_bienes=bien_id)
    
    # Obtener tipo de ubicación y su ID
    departamento_id = request.GET.get('departamento_id')
    unidad_id = request.GET.get('unidad_id')
    
    # Buscar asignación según el tipo de ubicación
    if departamento_id:
        asignacion = AsignacionDeBienes.objects.filter(
            id_bienes=bien, 
            id_departamentos=departamento_id
        ).first()
    elif unidad_id:
        asignacion = AsignacionDeBienes.objects.filter(
            id_bienes=bien, 
            id_UnidadOrganizacional=unidad_id
        ).first()
    else:
        asignacion = None
    
    try:
        stock = Stock.objects.get(bien_id=bien)
        cantidad_disponible = stock.cantidad_disponible
    except Stock.DoesNotExist:
        cantidad_disponible = 0

    data = {
        'bien_id': bien.id_bienes,
        'bien_nombre': bien.nombre,
        'cantidad_asignada': asignacion.cantidad_asignada if asignacion else 0,
        'cantidad_disponible': cantidad_disponible
    }

    # Agregar información adicional según el tipo de ubicación
    if asignacion:
        if asignacion.id_departamentos:
            data.update({
                'ubicacion_tipo': 'departamento',
                'ubicacion_nombre': asignacion.id_departamentos.nombre_departamento
            })
        elif asignacion.id_UnidadOrganizacional:
            data.update({
                'ubicacion_tipo': 'unidad',
                'ubicacion_nombre': asignacion.id_UnidadOrganizacional.nombre
            })

    return JsonResponse(data)


@login_required
def ver_mi_perfil(request):
    usuario = request.user
    
    if request.method == 'POST':
        try:
            # Obtener los datos del formulario
            nombres = request.POST.get('nombres', '').strip()
            apellidos = request.POST.get('apellidos', '').strip()
            email = request.POST.get('email', '').strip()
            telefono = request.POST.get('telefono', '').strip()

            # Validar que los campos requeridos no estén vacíos
            if not nombres or not apellidos or not email:
                return JsonResponse({
                    'success': False,
                    'error': 'Todos los campos son requeridos',
                    'errors': {
                        'nombres': 'Este campo es requerido' if not nombres else None,
                        'apellidos': 'Este campo es requerido' if not apellidos else None,
                        'email': 'Este campo es requerido' if not email else None
                    }
                })

            # Verificar si el email ya existe (excluyendo el usuario actual)
            if (Usuario.objects.exclude(id_usuario=usuario.id_usuario)
                            .filter(email=email).exists()):
                return JsonResponse({
                    'success': False,
                    'error': 'El email ya está en uso',
                    'errors': {
                        'email': 'Este correo electrónico ya está registrado'
                    }
                })

            # Actualizar los datos del usuario
            usuario.nombres = nombres
            usuario.apellidos = apellidos
            usuario.email = email
            usuario.telefono = telefono
            usuario.save()

            # Devolver respuesta exitosa
            return JsonResponse({
                'success': True,
                'message': 'Perfil actualizado exitosamente',
                'data': {
                    'nombres': usuario.nombres,
                    'apellidos': usuario.apellidos,
                    'email': usuario.email,
                    'telefono': usuario.telefono if usuario.telefono else ''
                }
            })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': 'Error al actualizar el perfil: ' + str(e)
            })

    # Si es GET, mostrar el formulario
    return render(request, 'ver_mi_perfil.html', {'usuario': usuario})

# aplicacion/views.py
from django.views.generic import ListView, DeleteView
from django.urls import reverse_lazy
from aplicacion.models import TiposDeSolicitud

# Vista para listar las solicitudes
class TiposDeSolicitudListView(ListView):
    model = TiposDeSolicitud
    template_name = 'tipos_de_solicitud_list.html'
    context_object_name = 'solicitudes'

# Vista para eliminar una solicitud
class TiposDeSolicitudDeleteView(DeleteView):
    model = TiposDeSolicitud
    template_name = 'tipos_de_solicitud_confirm_delete.html'
    success_url = reverse_lazy('tipos-de-solicitud-list')


from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.contrib import messages
from django.urls import reverse
from .models import Bienes, HistorialBienes, TiposDeEvento
from .document_service import DocumentService

def es_admin_bienes(user):
    return user.id_rol_del_usuario.nombre_rol == 'ADMIN_BIENES'

@login_required
@user_passes_test(es_admin_bienes)
def historial_bien(request, bien_id):
    bien = get_object_or_404(Bienes, id_bienes=bien_id)
    historial_list = HistorialBienes.objects.filter(bien_id=bien).select_related(
        'id_tipos_de_evento',
        'departamento_origen',
        'departamento_destino',
        'UnidadOrganizacional_origen',
        'UnidadOrganizacional_destino'
    ).order_by('-fecha_evento')

    tipos_con_pdf = [
        'TRASLADO_TEMPORAL',          # Como está en la BD
        'TRASLADO_PERMANENTE',        # Como está en la BD
        'Desincorporación',           # Como está en la BD
        'MANTENIMIENTO',              # Como está en la BD
        'FIN_MANTENIMIENTO',          # Como está en la BD
        'ASIGNACION',                 # Como está en la BD
        'RESGUARDO'                   # Como está en la BD
    ]

    # Agregamos print para debug
    print("\nTipos con PDF disponibles:", tipos_con_pdf)

    for evento in historial_list:
        tipo_evento = evento.id_tipos_de_evento.nombre
        print(f"\nProcesando evento ID: {evento.id}")
        print(f"Tipo de evento: '{tipo_evento}'")
        print(f"¿Está en tipos_con_pdf?: {tipo_evento in tipos_con_pdf}")
        
        if tipo_evento in tipos_con_pdf:
            evento.pdf_url = reverse('historial_bien_pdf', args=[evento.id])
            evento.tiene_pdf = DescripcionPDF.objects.filter(historial=evento).exists()
            print(f"PDF URL asignada: {evento.pdf_url}")
        else:
            evento.pdf_url = None
            evento.tiene_pdf = False

    paginator = Paginator(historial_list, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'bien': bien,
        'page_obj': page_obj,
        'tipos_con_pdf': tipos_con_pdf,
    }
    return render(request, 'historial_bien.html', context)

@login_required
@user_passes_test(es_admin_bienes)
def historial_bien_pdf(request, historial_id):
    try:
        # Obtener el historial
        historial = HistorialBienes.objects.select_related(
            'bien_id',
            'id_tipos_de_evento',
            'departamento_origen',
            'departamento_destino',
            'UnidadOrganizacional_origen',
            'UnidadOrganizacional_destino',
            'usuario_id'
        ).get(id=historial_id)

        # Agregar prints para debug
        print(f"\nGenerando PDF para historial ID: {historial_id}")
        print(f"Tipo de evento: {historial.id_tipos_de_evento.nombre}")
        
        # Verificar si ya existe una descripción PDF
        descripcion_pdf = DescripcionPDF.objects.filter(historial=historial).first()
        print(f"¿Existe descripción PDF?: {descripcion_pdf is not None}")

        # Crear el generador de documentos
        generator = DocumentService()
        
        # Mapeo actualizado de tipos de evento a métodos del generador
        tipo_evento_mapping = {
            'TRASLADO_TEMPORAL': generator._generar_traslado_temporal,
            'TRASLADO_PERMANENTE': generator._generar_traslado_permanente,
            'Desincorporación': generator._generar_desincorporacion,
            'MANTENIMIENTO': generator._generar_mantenimiento,
            'FIN_MANTENIMIENTO': generator._generar_fin_mantenimiento,
            'ASIGNACION': generator._generar_asignacion,
            'RESGUARDO': generator._generar_resguardo
        }

        # Obtener el método correspondiente
        generate_method = tipo_evento_mapping.get(historial.id_tipos_de_evento.nombre)
        print(f"Método de generación encontrado: {generate_method.__name__ if generate_method else 'None'}")

        if generate_method:
            try:
                response = generate_method(historial)
                print("PDF generado exitosamente")
                return response
            except Exception as e:
                print(f"Error generando PDF: {str(e)}")
                messages.error(request, f'Error generando PDF: {str(e)}')
                return redirect('historial_bien', bien_id=historial.bien_id.id_bienes)
        else:
            print(f"No se encontró método para el tipo de evento: {historial.id_tipos_de_evento.nombre}")
            messages.warning(request, 'No hay plantilla de documento para este tipo de evento')
            return redirect('historial_bien', bien_id=historial.bien_id.id_bienes)

    except HistorialBienes.DoesNotExist:
        print("No se encontró el registro de historial")
        messages.error(request, 'No se encontró el registro de historial')
        return redirect('index')
    except Exception as e:
        print(f"Error general: {str(e)}")
        messages.error(request, f'Error al generar documento: {str(e)}')
        if historial and historial.bien_id:
            return redirect('historial_bien', bien_id=historial.bien_id.id_bienes)
        return redirect('index')
        


class BienListView(LoginRequiredMixin, ListView):
    model = Bienes
    template_name = 'bien_list.html'
    context_object_name = 'bienes'

    def get_queryset(self):
        queryset = Bienes.objects.all()

        # Obtener el último evento de fin de mantenimiento
        ultimo_fin_mantenimiento = HistorialBienes.objects.filter(
            bien_id=OuterRef('pk'),
            id_tipos_de_evento__nombre='FIN_MANTENIMIENTO'
        ).order_by('-fecha_evento')

        # Obtener el último evento de mantenimiento
        ultimo_mantenimiento = HistorialBienes.objects.filter(
            bien_id=OuterRef('pk'),
            id_tipos_de_evento__nombre='MANTENIMIENTO'
        ).order_by('-fecha_evento')

        # Subconsulta para obtener la asignación más reciente
        ultima_asignacion = AsignacionDeBienes.objects.filter(
            id_bienes=OuterRef('pk')
        ).order_by('-fecha_de_asignacion')

        # Obtener el último evento de historial
        ultimo_evento = HistorialBienes.objects.filter(
            bien_id=OuterRef('pk')
        ).order_by('-fecha_evento').values('id_tipos_de_evento__nombre')[:1]

        # Subconsulta para stock
        stock = Stock.objects.filter(bien_id=OuterRef('pk'))

        # Primero anotamos las fechas y el último evento
        queryset = queryset.annotate(
            ultimo_fin_mantenimiento_fecha=Subquery(
                ultimo_fin_mantenimiento.values('fecha_evento')[:1]
            ),
            ultimo_mantenimiento_fecha=Subquery(
                ultimo_mantenimiento.values('fecha_evento')[:1]
            ),
            ultimo_evento_nombre=Subquery(
                ultimo_evento,
                output_field=CharField()
            )
        )

        # Luego anotamos las cantidades
        queryset = queryset.annotate(
            cantidad_asignada=Coalesce(Subquery(stock.values('cantidad_asignada')[:1]), Value(0)),
            cantidad_disponible=Coalesce(Subquery(stock.values('cantidad_disponible')[:1]), Value(0)),
            cantidad_resguardada=Coalesce(Subquery(stock.values('cantidad_resguardada')[:1]), Value(0)),
            cantidad_desincorporada=Coalesce(Subquery(stock.values('cantidad_desincorporada')[:1]), Value(0)),
            cantidad_en_mantenimiento=Coalesce(Subquery(stock.values('cantidad_en_mantenimiento')[:1]), Value(0))
        )

        # Ahora podemos anotar el estado de desincorporación
        queryset = queryset.annotate(
            esta_desincorporado=Case(
                When(
                    Q(ultimo_evento_nombre='DESINCORPORACION') | Q(cantidad_desincorporada__gt=0),
                    then=Value(True)
                ),
                default=Value(False),
                output_field=BooleanField(),
            )
        )

        # Finalmente anotamos el nombre del departamento y el estado calculado
        queryset = queryset.annotate(
            departamento_nombre=Case(
                When(
                    Q(esta_desincorporado=True),
                    then=Value('No asignado')
                ),
                When(
                    Q(ultimo_fin_mantenimiento_fecha__gt=F('ultimo_mantenimiento_fecha')),
                    then=Coalesce(
                        Subquery(
                            ultimo_fin_mantenimiento.values('departamento_destino__nombre_departamento')[:1]
                        ),
                        Subquery(
                            ultimo_fin_mantenimiento.values('UnidadOrganizacional_destino__nombre')[:1]
                        )
                    )
                ),
                default=Coalesce(
                    Subquery(ultima_asignacion.values('id_departamentos__nombre_departamento')[:1]),
                    Subquery(ultima_asignacion.values('id_UnidadOrganizacional__nombre')[:1]),
                    Value('No asignado')
                ),
                output_field=CharField(),
            ),
            estado_calculado=Case(
                When(Q(esta_desincorporado=True), 
                     then=Value('desincorporado')),
                When(Q(ultimo_evento_nombre='TRASLADO_TEMPORAL'), 
                     then=Value('traslado_temporal')),
                When(
                    Q(departamento_nombre='Bienes en Mantenimiento') |
                    (Q(ultimo_evento_nombre='MANTENIMIENTO') & ~Q(ultimo_fin_mantenimiento_fecha__gt=F('ultimo_mantenimiento_fecha'))), 
                    then=Value('mantenimiento')
                ),
                When(
                    Q(departamento_nombre='Bienes en resguardo') |
                    Q(ultimo_evento_nombre='RESGUARDO') | 
                    Q(cantidad_resguardada__gt=0), 
                    then=Value('resguardado')
                ),
                When(
                    Q(ultimo_fin_mantenimiento_fecha__gt=F('ultimo_mantenimiento_fecha')) |
                    Q(ultimo_evento_nombre='ASIGNACION') | 
                    Q(cantidad_asignada__gt=0), 
                    then=Value('asignado')
                ),
                When(cantidad_disponible__gt=0, 
                     then=Value('disponible')),
                default=Value('desconocido'),
                output_field=CharField(),
            )
        )

        # Aplicar filtros
        filtros = Q()

        # Filtro por departamento
        departamento_id = self.request.GET.get('departamento')
        if departamento_id:
            filtros &= Q(departamento_id=departamento_id)

        # Filtro por tipo de bien
        tipo_bien_id = self.request.GET.get('tipo_bien')
        if tipo_bien_id:
            filtros &= Q(tipo_bien_id=tipo_bien_id)

        # Filtro por estado
        estado = self.request.GET.get('estatus')
        if estado:
            filtros &= Q(estado_calculado=estado)

        # Filtro por fechas
        fecha_desde = self.request.GET.get('fecha_desde')
        fecha_hasta = self.request.GET.get('fecha_hasta')

        if fecha_desde:
            try:
                fecha_desde = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
                filtros &= Q(fecha_de_registro__gte=fecha_desde)
            except (ValueError, TypeError):
                pass

        if fecha_hasta:
            try:
                fecha_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
                filtros &= Q(fecha_de_registro__lte=fecha_hasta)
            except (ValueError, TypeError):
                pass

        return queryset.filter(filtros).distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'departamentos': Departamentos.objects.all(),
            'tipos_bien': TipoBien.objects.all().order_by('nombre'),
            'today': timezone.now().date(),
            'filtros_activos': {
                'departamento': self.request.GET.get('departamento'),
                'tipo_bien': self.request.GET.get('tipo_bien'),
                'estatus': self.request.GET.get('estatus'),
                'fecha_desde': self.request.GET.get('fecha_desde'),
                'fecha_hasta': self.request.GET.get('fecha_hasta'),
            },
            'estados_disponibles': [
                {'valor': 'disponible', 'nombre': 'Disponible'},
                {'valor': 'asignado', 'nombre': 'Asignado'},
                {'valor': 'resguardado', 'nombre': 'Resguardado'},
                {'valor': 'mantenimiento', 'nombre': 'En Mantenimiento'},
                {'valor': 'desincorporado', 'nombre': 'Desincorporado'},
                {'valor': 'traslado_temporal', 'nombre': 'Traslado Temporal'}
            ]
        })
        return context
    
logger = logging.getLogger(__name__)

def inicializar_tipos_evento():
    for tipo, _ in TiposDeEvento.TIPOS_EVENTO:
        TiposDeEvento.objects.get_or_create(
            nombre=tipo,
            defaults={'descripcion': f'Descripción para {tipo}'}
        )

def es_admin_bienes(user):
    return user.id_rol_del_usuario.nombre_rol == 'ADMIN_BIENES'



logger = logging.getLogger(__name__)

@login_required
@user_passes_test(es_admin_bienes)
def procesar_solicitud_temporal(request, solicitud_id):
    # Asegurarse de que los tipos de evento estén inicializados
    tipo_evento, _ = TiposDeEvento.objects.get_or_create(
        nombre='TRASLADO_TEMPORAL',
        defaults={'descripcion': 'Traslado temporal de bien'}
    )

    # Obtener la solicitud
    solicitud = get_object_or_404(
        Solicitudes.objects.select_related(
            'bien_id',
            'usuario_id',
            'departamento_solicitante',
            'UnidadOrganizacional_solicitante',
            'id_tipos_de_solicitud'
        ), 
        id_solicitudes=solicitud_id, 
        id_tipos_de_solicitud__nombre='Traslado Temporal'
    )
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'rechazar':
            motivo_rechazo = request.POST.get('motivo_rechazo')
            if not motivo_rechazo:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': 'Debe proporcionar un motivo para rechazar la solicitud.'
                    }, status=400)
                messages.error(request, 'Debe proporcionar un motivo para rechazar la solicitud.')
                return render(request, 'procesar_solicitud_temporal.html', 
                            {'solicitud': solicitud, 'form': ProcesarSolicitudTemporalForm()})

            try:
                with transaction.atomic():
                    bien = solicitud.bien_id
                    solicitud.estado_solicitud = 'rechazada'
                    solicitud.motivo_rechazo = motivo_rechazo
                    solicitud.save()

                    if bien:
                        tipo_evento_rechazo, _ = TiposDeEvento.objects.get_or_create(
                            nombre="RECHAZO_TRASLADO_TEMPORAL",
                            defaults={'descripcion': 'Rechazo de solicitud de traslado temporal'}
                        )

                        # Obtener origen para el historial
                        origen = (solicitud.departamento_solicitante 
                                if solicitud.departamento_solicitante 
                                else solicitud.UnidadOrganizacional_solicitante)
                        
                        HistorialBienes.objects.create(
                            bien_id=bien,
                            fecha_evento=timezone.now(),
                            id_tipos_de_evento=tipo_evento_rechazo,
                            descripcion=f"Solicitud de traslado temporal rechazada. Motivo: {motivo_rechazo}",
                            cantidad_afectada=1,
                            usuario_id=request.user,
                            departamento_origen=solicitud.departamento_solicitante,
                            UnidadOrganizacional_origen=solicitud.UnidadOrganizacional_solicitante,
                            departamento_destino=None,
                            UnidadOrganizacional_destino=None
                        )

                        origen_texto = (
                            f"departamento {solicitud.departamento_solicitante.nombre_departamento}"
                            if solicitud.departamento_solicitante
                            else f"unidad organizacional {solicitud.UnidadOrganizacional_solicitante.nombre}"
                        )
                        
                        mensaje_notificacion = (
                            f"Su solicitud de traslado temporal para el bien '{bien.nombre}' "
                            f"desde {origen_texto} ha sido rechazada. Motivo: {motivo_rechazo}"
                        )
                    else:
                        mensaje_notificacion = (
                            f"Su solicitud de traslado temporal ha sido rechazada. "
                            f"Motivo: {motivo_rechazo}"
                        )

                    # Crear notificación
                    Notificacion.objects.create(
                        usuario=solicitud.usuario_id,
                        solicitud=solicitud,
                        mensaje=mensaje_notificacion
                    )

                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': True,
                            'message': 'Solicitud rechazada exitosamente.',
                            'redirect_url': reverse('lista_solicitudes')
                        })
                    
                    messages.success(request, 'Solicitud de traslado temporal rechazada.')
                    return redirect('lista_solicitudes')

            except Exception as e:
                logger.error(f"Error al rechazar la solicitud: {str(e)}", exc_info=True)
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': f'Error al rechazar la solicitud: {str(e)}'
                    }, status=500)
                messages.error(request, f'Error al rechazar la solicitud: {str(e)}')
                return redirect('lista_solicitudes')

        form = ProcesarSolicitudTemporalForm(request.POST, instance=solicitud)
        if action == 'aprobar' and form.is_valid():
            try:
                with transaction.atomic():
                    bien = form.cleaned_data['bien_id']
                    
                    # Verificar si el bien está en el departamento de resguardo
                    asignacion_actual = AsignacionDeBienes.objects.filter(
                        id_bienes=bien
                    ).order_by('-fecha_de_asignacion').first()
                    
                    if asignacion_actual and asignacion_actual.id_departamentos and \
                       asignacion_actual.id_departamentos.nombre_departamento == 'Bienes en resguardo':
                        raise ValueError("Este bien no está disponible para traslado temporal ya que se encuentra en resguardo.")
                    
                    fecha_inicio = form.cleaned_data['fecha_inicio']
                    fecha_fin = form.cleaned_data['fecha_fin']
                    
                    # Obtener origen y destino
                    origen_depto = asignacion_actual.id_departamentos
                    origen_unidad = asignacion_actual.id_UnidadOrganizacional
                    destino_depto = solicitud.departamento_solicitante
                    destino_unidad = solicitud.UnidadOrganizacional_solicitante

                    # Validar que no sea la misma ubicación
                    if (origen_depto == destino_depto) or (origen_unidad == destino_unidad):
                        raise ValueError("No se puede trasladar un bien a su misma ubicación.")
                    
                    # Crear nueva asignación temporal
                    nueva_asignacion = AsignacionDeBienes.objects.create(
                        id_bienes=bien,
                        id_departamentos=destino_depto,
                        id_UnidadOrganizacional=destino_unidad,
                        cantidad_asignada=1,
                        fecha_de_asignacion=fecha_inicio,
                        fecha_fin_temporal=fecha_fin
                    )
                    
                    # Actualizar stock
                    stock = Stock.objects.get(bien_id=bien)
                    stock.cantidad_asignada -= 1
                    stock.cantidad_prestada += 1
                    stock.save()
                    
                    # Obtener textos para mensajes
                    origen_texto = (
                        f"departamento {origen_depto.nombre_departamento}"
                        if origen_depto
                        else f"unidad organizacional {origen_unidad.nombre}"
                    )
                    
                    destino_texto = (
                        f"departamento {destino_depto.nombre_departamento}"
                        if destino_depto
                        else f"unidad organizacional {destino_unidad.nombre}"
                    )
                    
                    # Registrar en historial
                    HistorialBienes.objects.create(
                        bien_id=bien,
                        fecha_evento=timezone.now(),
                        id_tipos_de_evento=tipo_evento,
                        descripcion=f"Traslado temporal desde {origen_texto} hacia {destino_texto} del {fecha_inicio} al {fecha_fin}",
                        cantidad_afectada=1,
                        usuario_id=request.user,
                        departamento_origen=origen_depto,
                        UnidadOrganizacional_origen=origen_unidad,
                        departamento_destino=destino_depto,
                        UnidadOrganizacional_destino=destino_unidad
                    )
                    
                    # Actualizar solicitud
                    solicitud.estado_solicitud = 'aprobada'
                    solicitud.save()
                    
                    # Notificar al usuario
                    Notificacion.objects.create(
                        usuario=solicitud.usuario_id,
                        solicitud=solicitud,
                        mensaje=f"Su solicitud de traslado temporal del bien '{bien.nombre}' "
                               f"desde {origen_texto} hacia {destino_texto} ha sido aprobada."
                    )

                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': True,
                            'message': 'Solicitud de traslado temporal aprobada con éxito.',
                            'redirect_url': reverse('lista_solicitudes')
                        })
                    
                    messages.success(request, 'Solicitud de traslado temporal aprobada con éxito.')
                    return redirect('lista_solicitudes')
                
            except ValueError as e:
                logger.error(f"Error de validación: {str(e)}")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': str(e)
                    }, status=400)
                messages.error(request, str(e))
            except Exception as e:
                logger.error(f"Error al procesar la solicitud: {str(e)}", exc_info=True)
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': f'Error al procesar la solicitud: {str(e)}'
                    }, status=500)
                messages.error(request, f'Error al procesar la solicitud: {str(e)}')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': 'Por favor, corrija los errores en el formulario.',
                    'errors': form.errors
                }, status=400)

    else:
        class FilteredProcesarSolicitudTemporalForm(ProcesarSolicitudTemporalForm):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                # Excluir bienes que están en el departamento de resguardo
                bienes_en_resguardo = AsignacionDeBienes.objects.filter(
                    id_bienes__id_bienes__in=Bienes.objects.all(),  # Usamos id_bienes en lugar de id
                    id_departamentos__nombre_departamento='Bienes en resguardo'
                ).values_list('id_bienes__id_bienes', flat=True)  # Usamos id_bienes dos veces para acceder al ID correcto
                
                self.fields['bien_id'].queryset = self.fields['bien_id'].queryset.exclude(
                    id_bienes__in=bienes_en_resguardo  # Usamos id_bienes en lugar de id
                )

        form = FilteredProcesarSolicitudTemporalForm(instance=solicitud)

    context = {
        'form': form,
        'solicitud': solicitud,
    }
    return render(request, 'procesar_solicitud_temporal.html', context)

def listar_bienes_en_traslado_temporal(request):
    hoy = timezone.now().date()
    bienes_en_traslado = AsignacionDeBienes.objects.filter(
        fecha_fin_temporal__isnull=False
    ).select_related('id_bienes', 'id_departamentos')
    
    for asignacion in bienes_en_traslado:
        # El botón se activa solo si la fecha de fin ha llegado o pasado
        asignacion.puede_finalizar = asignacion.fecha_fin_temporal <= hoy

    context = {
        'bienes_en_traslado': bienes_en_traslado,
        'fecha_actual': hoy,
    }
    return render(request, 'listar_bienes_en_traslado_temporal.html', context)

@login_required
@user_passes_test(es_admin_bienes)
def finalizar_traslado_temporal(request, asignacion_id):
    asignacion = get_object_or_404(
        AsignacionDeBienes, 
        id_asignacion_bienes=asignacion_id, 
        fecha_fin_temporal__isnull=False
    )
    
    # Verificar si ya se puede finalizar el traslado
    hoy = timezone.now().date()
    if asignacion.fecha_fin_temporal > hoy:
        messages.error(request, 'No se puede finalizar el traslado antes de la fecha de fin programada.')
        return redirect('listar_bienes_en_traslado_temporal')
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                bien = asignacion.id_bienes
                cantidad = asignacion.cantidad_asignada
                departamento_temporal = asignacion.id_departamentos
                departamento_original = bien.get_departamento_actual()

                logger.info(f"Iniciando finalización de traslado temporal - Bien: {bien}, "
                          f"Cantidad: {cantidad}, "
                          f"Desde: {departamento_temporal}, "
                          f"Hacia: {departamento_original}")

                # 1. Actualizar el stock: mover de prestado a asignado
                stock = Stock.objects.select_for_update().get(bien_id=bien)
                stock.cantidad_prestada -= cantidad  # Reducir la cantidad prestada
                stock.cantidad_asignada += cantidad  # Aumentar la cantidad asignada
                stock.save()

                logger.info(f"Stock actualizado - Total: {stock.cantidad_total}, "
                          f"Asignado: {stock.cantidad_asignada}, "
                          f"Prestado: {stock.cantidad_prestada}")

                # 2. Eliminar la asignación temporal
                asignacion.delete()
                logger.info(f"Asignación temporal eliminada")

                # 3. Crear o actualizar la asignación en el departamento original
                asignacion_original, created = AsignacionDeBienes.objects.get_or_create(
                    id_bienes=bien,
                    id_departamentos=departamento_original,
                    fecha_fin_temporal__isnull=True,  # Asignación permanente
                    defaults={
                        'cantidad_asignada': cantidad,
                        'fecha_de_asignacion': timezone.now()
                    }
                )
                
                if not created:
                    # Si ya existía una asignación, actualizar la fecha
                    asignacion_original.fecha_de_asignacion = timezone.now()
                    asignacion_original.save()

                logger.info(f"Asignación en departamento original {'creada' if created else 'actualizada'}")

                # 4. Registrar en el historial
                tipo_evento, _ = TiposDeEvento.objects.get_or_create(
                    nombre='FIN_TRASLADO_TEMPORAL',
                    defaults={'descripcion': 'Fin de traslado temporal de bien'}
                )
                
                HistorialBienes.objects.create(
                    bien_id=bien,
                    fecha_evento=timezone.now(),
                    id_tipos_de_evento=tipo_evento,
                    descripcion=f"Fin de traslado temporal desde {departamento_temporal} a {departamento_original}",
                    cantidad_afectada=cantidad,
                    usuario_id=request.user,
                    departamento_origen=departamento_temporal,
                    departamento_destino=departamento_original
                )

                logger.info("Historial registrado")
                messages.success(request, 'Traslado temporal finalizado con éxito. '
                               f'El bien ha vuelto al departamento {departamento_original}.')

                # Verificación final
                verificacion_stock = Stock.objects.get(bien_id=bien)
                logger.info(f"Verificación final - Stock total: {verificacion_stock.cantidad_total}, "
                          f"Asignado: {verificacion_stock.cantidad_asignada}, "
                          f"Prestado: {verificacion_stock.cantidad_prestada}")

        except Exception as e:
            logger.error(f"Error al finalizar el traslado temporal: {str(e)}", exc_info=True)
            messages.error(request, f'Ocurrió un error al finalizar el traslado temporal: {str(e)}')
            return redirect('listar_bienes_en_traslado_temporal')

    return redirect('listar_bienes_en_traslado_temporal')



@require_GET
def cantidad_disponible(request, bien_id):
    try:
        bien = Bienes.objects.get(id_bienes=bien_id)
        asignacion = AsignacionDeBienes.objects.filter(id_bienes=bien).order_by('-fecha_de_asignacion').first()
        
        if asignacion:
            return JsonResponse({
                'cantidad_asignada': asignacion.cantidad_asignada,
                'departamento': asignacion.id_departamentos.nombre_departamento
            })
        else:
            return JsonResponse({'error': 'Este bien no está asignado a ningún departamento'}, status=400)
    except Bienes.DoesNotExist:
        return JsonResponse({'error': 'Bien no encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    

@login_required
def crear_solicitud_nuevo_bien(request):
    # Verificar que el usuario tenga una ubicación asignada
    if not request.user.id_departamentos and not request.user.id_unidadOrganizacional:
        messages.error(request, 'Debe pertenecer a un departamento o unidad organizacional para crear solicitudes.')
        return redirect('lista_solicitudes')

    if request.method == 'POST':
        form = SolicitudNuevoBienForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    solicitud = form.save(commit=False)
                    solicitud.usuario_id = request.user
                    
                    # Asignar ubicación según el tipo de usuario
                    if request.user.id_departamentos:
                        solicitud.departamento_solicitante = request.user.id_departamentos
                        solicitud.UnidadOrganizacional_solicitante = None
                        origen = f"departamento {request.user.id_departamentos.nombre_departamento}"
                    else:
                        solicitud.UnidadOrganizacional_solicitante = request.user.id_unidadOrganizacional
                        solicitud.departamento_solicitante = None
                        origen = f"unidad organizacional {request.user.id_unidadOrganizacional.nombre}"
                    
                    # Obtener o crear el tipo de solicitud
                    tipo_solicitud, _ = TiposDeSolicitud.objects.get_or_create(
                        nombre='Nuevo bien',
                        defaults={'descripcion': 'Solicitud de nuevo bien'}
                    )
                    
                    solicitud.id_tipos_de_solicitud = tipo_solicitud
                    solicitud.estado_solicitud = 'pendiente'
                    solicitud.save()

                    # Crear notificaciones para los administradores
                    admin_users = Usuario.objects.filter(
                        Q(id_rol_del_usuario__nombre_rol='ADMIN_BIENES') | 
                        Q(is_superuser=True)
                    ).distinct()

                    for admin in admin_users:
                        Notificacion.objects.create(
                            usuario=admin,
                            solicitud=solicitud,
                            mensaje=f"[ADMIN] Nueva solicitud de bien creada por {request.user.get_full_name()} del {origen}"
                        )

                    # Notificar al usuario solicitante
                    Notificacion.objects.create(
                        usuario=request.user,
                        solicitud=solicitud,
                        mensaje=f"Su solicitud de nuevo bien ha sido creada exitosamente. Se le notificará cuando sea procesada."
                    )

                    messages.success(request, 'Solicitud de nuevo bien creada con éxito.')
                    
                    # Responder según el tipo de solicitud
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': True,
                            'message': 'Solicitud de nuevo bien creada con éxito.',
                            'redirect_url': reverse('lista_solicitudes')
                        })
                    return redirect('lista_solicitudes')

            except ValidationError as e:
                logger.error(f"Error de validación: {str(e)}")
                error_message = str(e)
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': error_message,
                        'errors': {'__all__': [error_message]}
                    }, status=400)
                messages.error(request, error_message)
            
            except Exception as e:
                logger.error(f"Error inesperado: {str(e)}", exc_info=True)
                error_message = 'Ocurrió un error al crear la solicitud.'
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': error_message
                    }, status=500)
                messages.error(request, error_message)
        
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': 'Por favor corrija los errores en el formulario',
                    'errors': form.errors
                }, status=400)
    else:
        form = SolicitudNuevoBienForm()

    return render(request, 'crear_solicitud_nuevo_bien.html', {'form': form})



@login_required
@user_passes_test(es_admin_bienes)
def procesar_solicitud_nuevo_bien(request, solicitud_id):
    tipo_evento_asignacion, _ = TiposDeEvento.objects.get_or_create(
        nombre='ASIGNACION',
        defaults={'descripcion': 'Asignación inicial de bien'}
    )
    
    solicitud = get_object_or_404(
        Solicitudes, 
        id_solicitudes=solicitud_id,
        id_tipos_de_solicitud__nombre='Nuevo bien'
    )
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'rechazar':
            motivo_rechazo = request.POST.get('motivo_rechazo')
            if not motivo_rechazo:
                messages.error(request, 'Debe proporcionar un motivo para rechazar la solicitud.')
                return render(request, 'procesar_solicitud_nuevo_bien.html', {
                    'form': ProcesarNuevoBienForm(instance=solicitud),
                    'solicitud': solicitud
                })
            
            try:
                with transaction.atomic():
                    solicitud.estado_solicitud = 'rechazada'
                    solicitud.motivo_rechazo = motivo_rechazo
                    solicitud.save()
                    
                    # Registrar en el historial si ya hay un bien asociado
                    if solicitud.bien_id:
                        tipo_evento_rechazo, _ = TiposDeEvento.objects.get_or_create(
                            nombre="RECHAZO_ASIGNACION",
                            defaults={'descripcion': 'Rechazo de solicitud de asignación de bien'}
                        )
                        
                        HistorialBienes.objects.create(
                            bien_id=solicitud.bien_id,
                            fecha_evento=timezone.now(),
                            id_tipos_de_evento=tipo_evento_rechazo,
                            descripcion=f"Solicitud de asignación rechazada. Motivo: {motivo_rechazo}",
                            cantidad_afectada=1,
                            usuario_id=request.user,
                            departamento_origen=None,
                            departamento_destino=solicitud.departamento_solicitante,
                            UnidadOrganizacional_origen=None,
                            UnidadOrganizacional_destino=solicitud.UnidadOrganizacional_solicitante
                        )
                    
                    # Obtener origen para el mensaje
                    origen = (
                        f"departamento {solicitud.departamento_solicitante.nombre_departamento}"
                        if solicitud.departamento_solicitante
                        else f"unidad organizacional {solicitud.UnidadOrganizacional_solicitante.nombre}"
                    )
                    
                    # Notificar al usuario del rechazo
                    Notificacion.objects.create(
                        usuario=solicitud.usuario_id,
                        solicitud=solicitud,
                        mensaje=f'Su solicitud de nuevo bien para {origen} ha sido rechazada. Motivo: {motivo_rechazo}'
                    )
                    
                    messages.info(request, 'Solicitud de nuevo bien rechazada.')
                    return redirect('lista_solicitudes')
            except Exception as e:
                messages.error(request, f'Error al rechazar la solicitud: {str(e)}')
                return render(request, 'procesar_solicitud_nuevo_bien.html', {
                    'form': ProcesarNuevoBienForm(instance=solicitud),
                    'solicitud': solicitud
                })
        
        # Procesar aprobación
        form = ProcesarNuevoBienForm(request.POST, instance=solicitud)
        if form.is_valid():
            try:
                with transaction.atomic():
                    bien = form.cleaned_data['bien_id']
                    fecha_asignacion = timezone.now().date()
                    
                    # Crear nueva asignación según el tipo de solicitante
                    AsignacionDeBienes.objects.create(
                        id_bienes=bien,
                        id_departamentos=solicitud.departamento_solicitante,
                        id_UnidadOrganizacional=solicitud.UnidadOrganizacional_solicitante,
                        cantidad_asignada=1,
                        fecha_de_asignacion=fecha_asignacion
                    )
                    
                    # Actualizar el stock
                    stock = Stock.objects.get(bien_id=bien)
                    stock.cantidad_asignada += 1
                    stock.cantidad_disponible -= 1
                    stock.save()
                    
                    # Obtener destino para el mensaje
                    destino = (
                        f"departamento {solicitud.departamento_solicitante.nombre_departamento}"
                        if solicitud.departamento_solicitante
                        else f"unidad organizacional {solicitud.UnidadOrganizacional_solicitante.nombre}"
                    )
                    
                    # Registrar en el historial
                    HistorialBienes.objects.create(
                        bien_id=bien,
                        fecha_evento=timezone.now(),
                        id_tipos_de_evento=tipo_evento_asignacion,
                        descripcion=f"Asignación inicial del bien al {destino}",
                        cantidad_afectada=1,
                        usuario_id=request.user,
                        departamento_origen=None,
                        departamento_destino=solicitud.departamento_solicitante,
                        UnidadOrganizacional_origen=None,
                        UnidadOrganizacional_destino=solicitud.UnidadOrganizacional_solicitante
                    )
                    
                    solicitud.bien_id = bien
                    solicitud.estado_solicitud = 'aprobada'
                    solicitud.save()
                    
                    # Notificar al usuario
                    Notificacion.objects.create(
                        usuario=solicitud.usuario_id,
                        solicitud=solicitud,
                        mensaje=f'Su solicitud de bien para {destino} ha sido aprobada. Se le ha asignado: {bien.nombre}'
                    )
                    
                    messages.success(request, f'Solicitud de nuevo bien aprobada con éxito. Se ha asignado el bien a {destino}.')
                    return redirect('lista_solicitudes')
            except Exception as e:
                messages.error(request, f'Error al procesar la solicitud: {str(e)}')
                return render(request, 'procesar_solicitud_nuevo_bien.html', {
                    'form': form,
                    'solicitud': solicitud
                })
        else:
            for field in form.errors:
                messages.error(request, f'{field}: {form.errors[field]}')
    else:
        form = ProcesarNuevoBienForm(instance=solicitud)
    
    return render(request, 'procesar_solicitud_nuevo_bien.html', {
        'form': form,
        'solicitud': solicitud
    })



@login_required
def crear_tipo_bien(request):
    if request.method == 'POST':
        form = TipoBienForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tipo de bien creado exitosamente')
            return redirect('inventario_por_tipo')
    else:
        form = TipoBienForm()
    
    return render(request, 'inventario/tipo_bien/form.html', {
        'form': form,
        'titulo': 'Crear Tipo de Bien'
    })

@login_required
def editar_tipo_bien(request, pk):
    tipo_bien = get_object_or_404(TipoBien, pk=pk)
    
    if request.method == 'POST':
        form = TipoBienForm(request.POST, instance=tipo_bien)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tipo de bien actualizado exitosamente')
            return redirect('inventario_por_tipo')
    else:
        form = TipoBienForm(instance=tipo_bien)
    
    return render(request, 'inventario/tipo_bien/form.html', {
        'form': form,
        'titulo': 'Editar Tipo de Bien'
    })



@login_required
def detalle_tipo_bien(request, pk):
    tipo_bien = get_object_or_404(TipoBien, pk=pk)
    
    # Obtener el último evento de fin de mantenimiento
    ultimo_fin_mantenimiento = HistorialBienes.objects.filter(
        bien_id=OuterRef('pk'),
        id_tipos_de_evento__nombre='FIN_MANTENIMIENTO'
    ).order_by('-fecha_evento')

    # Obtener el último evento de mantenimiento
    ultimo_mantenimiento = HistorialBienes.objects.filter(
        bien_id=OuterRef('pk'),
        id_tipos_de_evento__nombre='MANTENIMIENTO'
    ).order_by('-fecha_evento')

    # Subconsulta para obtener la asignación más reciente
    ultima_asignacion = AsignacionDeBienes.objects.filter(
        id_bienes=OuterRef('pk')
    ).order_by('-fecha_de_asignacion')

    # Obtener el último evento de historial
    ultimo_evento = HistorialBienes.objects.filter(
        bien_id=OuterRef('pk')
    ).order_by('-fecha_evento').values('id_tipos_de_evento__nombre')[:1]

    # Subconsulta para stock
    stock = Stock.objects.filter(bien_id=OuterRef('pk'))

    # Obtener los bienes con todas las anotaciones necesarias
    bienes = Bienes.objects.filter(tipo_bien=tipo_bien).annotate(
        ultimo_fin_mantenimiento_fecha=Subquery(
            ultimo_fin_mantenimiento.values('fecha_evento')[:1]
        ),
        ultimo_mantenimiento_fecha=Subquery(
            ultimo_mantenimiento.values('fecha_evento')[:1]
        ),
        ultimo_evento_nombre=Subquery(
            ultimo_evento,
            output_field=CharField()
        ),
        cantidad_asignada=Coalesce(Subquery(stock.values('cantidad_asignada')[:1]), Value(0)),
        cantidad_disponible=Coalesce(Subquery(stock.values('cantidad_disponible')[:1]), Value(0)),
        cantidad_resguardada=Coalesce(Subquery(stock.values('cantidad_resguardada')[:1]), Value(0)),
        cantidad_en_mantenimiento=Coalesce(Subquery(stock.values('cantidad_en_mantenimiento')[:1]), Value(0)),
        cantidad_desincorporada=Coalesce(Subquery(stock.values('cantidad_desincorporada')[:1]), Value(0)),
        esta_desincorporado=Case(
            When(
                Q(ultimo_evento_nombre='DESINCORPORACION') | Q(cantidad_desincorporada__gt=0),
                then=Value(True)
            ),
            default=Value(False),
            output_field=BooleanField(),
        ),
        departamento_nombre=Case(
            When(
                Q(esta_desincorporado=True),
                then=Value('No asignado')
            ),
            When(
                Q(ultimo_fin_mantenimiento_fecha__gt=F('ultimo_mantenimiento_fecha')),
                then=Coalesce(
                    Subquery(
                        ultimo_fin_mantenimiento.values('departamento_destino__nombre_departamento')[:1]
                    ),
                    Subquery(
                        ultimo_fin_mantenimiento.values('UnidadOrganizacional_destino__nombre')[:1]
                    )
                )
            ),
            default=Coalesce(
                Subquery(ultima_asignacion.values('id_departamentos__nombre_departamento')[:1]),
                Subquery(ultima_asignacion.values('id_UnidadOrganizacional__nombre')[:1]),
                Value('No asignado')
            ),
            output_field=CharField(),
        ),
        estado_calculado=Case(
            When(Q(esta_desincorporado=True), 
                 then=Value('desincorporado')),
            When(Q(ultimo_evento_nombre='TRASLADO_TEMPORAL'), 
                 then=Value('traslado_temporal')),
            When(
                Q(departamento_nombre='Bienes en Mantenimiento') |
                (Q(ultimo_evento_nombre='MANTENIMIENTO') & ~Q(ultimo_fin_mantenimiento_fecha__gt=F('ultimo_mantenimiento_fecha'))), 
                then=Value('mantenimiento')
            ),
            When(
                Q(departamento_nombre='Bienes en resguardo') |
                Q(ultimo_evento_nombre='RESGUARDO') | 
                Q(cantidad_resguardada__gt=0), 
                then=Value('resguardado')
            ),
            When(
                Q(ultimo_fin_mantenimiento_fecha__gt=F('ultimo_mantenimiento_fecha')) |
                Q(ultimo_evento_nombre='ASIGNACION') | 
                Q(cantidad_asignada__gt=0), 
                then=Value('asignado')
            ),
            When(cantidad_disponible__gt=0, 
                 then=Value('disponible')),
            default=Value('desconocido'),
            output_field=CharField(),
        )
    ).select_related('stock', 'tipo_bien')

    # Calcular estadísticas de stock
    stock_stats = Stock.objects.filter(
        bien_id__tipo_bien=tipo_bien
    ).aggregate(
        total_disponible=Count('bien_id', filter=Q(cantidad_disponible__gt=0)),
        total_asignado=Count('bien_id', filter=Q(cantidad_asignada__gt=0)),
        total_resguardado=Count('bien_id', filter=Q(cantidad_resguardada__gt=0)),
        total_mantenimiento=Count('bien_id', filter=Q(cantidad_en_mantenimiento__gt=0))
    )

    stock_actual = {
        'total': bienes.count(),
        'disponible': stock_stats['total_disponible'] or 0,
        'asignados': stock_stats['total_asignado'] or 0,
        'resguardados': stock_stats['total_resguardado'] or 0,
        'mantenimiento': stock_stats['total_mantenimiento'] or 0
    }

    context = {
        'titulo': f'Detalle de {tipo_bien.nombre}',
        'tipo_bien': tipo_bien,
        'bienes': bienes,
        'stock_actual': stock_actual
    }

    return render(request, 'inventario/tipo_bien/detalle.html', context)

def inventario_por_tipo(request):
    tipos_bien = TipoBien.objects.annotate(
        total_bienes=Count('bienes'),
        disponibles=Sum('bienes__stock__cantidad_disponible'),
        asignados=Sum('bienes__stock__cantidad_asignada'),
        en_prestamo=Sum('bienes__stock__cantidad_prestada'),
        en_mantenimiento=Sum('bienes__stock__cantidad_en_mantenimiento'),
        desincorporados=Sum('bienes__stock__cantidad_desincorporada'),
        resguardados=Sum('bienes__stock__cantidad_resguardada')
    ).order_by('nombre')
    
    return render(request, 'inventario/tipo_bien/inventario.html', {
        'tipos_bien': tipos_bien
    })

def api_notificaciones(request):
    unread_count = Notificacion.objects.filter(
        usuario=request.user,
        leida=False
    ).count()
    
    return JsonResponse({
        'has_unread': unread_count > 0,
        'unread_count': unread_count
    })




@login_required
@user_passes_test(es_admin_bienes)
def bienes_desincorporados(request):
    try:
        # Obtener todos los eventos de desincorporación
        desincorporaciones = HistorialBienes.objects.filter(
            id_tipos_de_evento__nombre='DESINCORPORACION'
        ).select_related(
            'bien_id',
            'usuario_id',
            'id_tipos_de_evento'
        ).order_by('-fecha_evento')

        bienes_con_info = []
        bienes_procesados = set()

        for historial in desincorporaciones:
            # Solo tomar el registro más reciente de cada bien
            if historial.bien_id.id_bienes not in bienes_procesados:
                valor = historial.descripcion.split("valor de")[1].split("Bs")[0].strip() \
                    if "valor de" in historial.descripcion.lower() else None

                bienes_con_info.append({
                    'bien': historial.bien_id,
                    'fecha_desincorporacion': historial.fecha_evento,
                    'usuario_responsable': historial.usuario_id,
                    'motivo': historial.descripcion,
                    'cantidad': historial.cantidad_afectada,
                    'valor_desincorporacion': valor
                })
                bienes_procesados.add(historial.bien_id.id_bienes)

        context = {
            'bienes_desincorporados': bienes_con_info,
            'total_desincorporados': len(bienes_con_info)
        }

        return render(request, 'bienes_desincorporados.html', context)

    except Exception as e:
        logger.error(f"Error en bienes_desincorporados: {str(e)}", exc_info=True)
        context = {
            'error': 'Ocurrió un error al cargar los bienes desincorporados.',
            'bienes_desincorporados': [],
            'total_desincorporados': 0
        }
        return render(request, 'bienes_desincorporados.html', context)



class GrupoListView(LoginRequiredMixin, ListView):
    model = Grupo
    template_name = 'grupo_list.html'
    context_object_name = 'grupos'
    ordering = ['codigo']

    def get_queryset(self):
        queryset = super().get_queryset()
        # Añadimos el campo formateado para la búsqueda
        queryset = queryset.annotate(
            codigo_formatted=LPad('codigo', 2, Value('0'))
        )
        
        search_query = self.request.GET.get('search', '')
        if search_query:
            # Si el término de búsqueda es numérico, lo formateamos
            if search_query.isdigit():
                search_query_formatted = search_query.zfill(2)
                queryset = queryset.filter(
                    Q(codigo_formatted__icontains=search_query_formatted) |
                    Q(nombre__icontains=search_query) |
                    Q(descripcion__icontains=search_query)
                )
            else:
                queryset = queryset.filter(
                    Q(nombre__icontains=search_query) |
                    Q(descripcion__icontains=search_query)
                )
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        return context




class GrupoCreateView(LoginRequiredMixin, CreateView):
    model = Grupo
    form_class = GrupoForm
    template_name = 'grupo_form.html'
    success_url = reverse_lazy('grupo-list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Grupo creado exitosamente.')
        return response

class GrupoUpdateView(LoginRequiredMixin, UpdateView):
    model = Grupo
    form_class = GrupoForm
    template_name = 'grupo_form.html'
    success_url = reverse_lazy('grupo-list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Grupo actualizado exitosamente.')
        return response

class GrupoDeleteView(LoginRequiredMixin, DeleteView):
    model = Grupo
    template_name = 'grupo_confirm_delete.html'
    success_url = reverse_lazy('grupo-list')

    def delete(self, request, *args, **kwargs):
        response = super().delete(request, *args, **kwargs)
        messages.success(self.request, 'Grupo eliminado exitosamente.')
        return response

# CRUD para Subgrupo
class SubgrupoListView(LoginRequiredMixin, ListView):
    model = Subgrupo
    template_name = 'subgrupo_list.html'
    context_object_name = 'subgrupos'
    
    def get_queryset(self):
        queryset = super().get_queryset()
        search_query = self.request.GET.get('search', '')
        
        if search_query:
            if search_query.isdigit():
                search_query_formatted = search_query.zfill(2)
                queryset = queryset.filter(
                    Q(codigo=search_query_formatted) |
                    Q(nombre__icontains=search_query) |
                    Q(descripcion__icontains=search_query)
                )
            else:
                queryset = queryset.filter(
                    Q(nombre__icontains=search_query) |
                    Q(descripcion__icontains=search_query)
                )
        return queryset

class SubgrupoCreateView(LoginRequiredMixin, CreateView):
    model = Subgrupo
    form_class = SubgrupoForm
    template_name = 'subgrupo_form.html'
    success_url = reverse_lazy('subgrupo_list')

    def form_valid(self, form):
        messages.success(self.request, 'Subgrupo creado exitosamente.')
        return super().form_valid(form)

class SubgrupoUpdateView(LoginRequiredMixin, UpdateView):
    model = Subgrupo
    form_class = SubgrupoForm
    template_name = 'subgrupo_form.html'
    success_url = reverse_lazy('subgrupo_list')

    def form_valid(self, form):
        messages.success(self.request, 'Subgrupo actualizado exitosamente.')
        return super().form_valid(form)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if self.object and self.object.codigo:
            form.initial['codigo'] = self.object.codigo.zfill(2)
        return form

class SubgrupoDeleteView(LoginRequiredMixin, DeleteView):
    model = Subgrupo
    template_name = 'subgrupo_confirm_delete.html'
    success_url = reverse_lazy('subgrupo_list')

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Subgrupo eliminado exitosamente.')
        return super().delete(request, *args, **kwargs)

        
# CRUD para SeccionSubgrupo
class SeccionSubgrupoListView(ListView):
    model = SeccionSubgrupo
    template_name = 'seccionsubgrupo_list.html'

class SeccionSubgrupoCreateView(CreateView):
    model = SeccionSubgrupo
    form_class = SeccionSubgrupoForm
    template_name = 'seccionsubgrupo_form.html'
    success_url = reverse_lazy('seccionsubgrupo_list')

class SeccionSubgrupoUpdateView(UpdateView):
    model = SeccionSubgrupo
    form_class = SeccionSubgrupoForm
    template_name = 'seccionsubgrupo_form.html'
    success_url = reverse_lazy('seccionsubgrupo_list')

class SeccionSubgrupoDeleteView(DeleteView):
    model = SeccionSubgrupo
    template_name = 'seccionsubgrupo_confirm_delete.html'
    success_url = reverse_lazy('seccionsubgrupo_list')





logger = logging.getLogger(__name__)

class BienUpdateView(LoginRequiredMixin, UpdateView):
    model = Bienes
    form_class = BienForm
    template_name = 'bien_edit_form.html'
    success_url = reverse_lazy('bien_list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if self.object:
            # Almacenar estado inicial para comparación
            self._initial_state = {
                'nombre': self.object.nombre,
                'numero_de_identificacion': self.object.numero_de_identificacion,
                'incorporacion': self.object.incorporacion,
                'desincorporacion': self.object.desincorporacion,
                'condicion': self.object.condicion,
                'observacion': self.object.observacion,
                'id_grupo': self.object.id_grupo,
                'id_subgrupo': self.object.id_subgrupo,
                'id_seccion_subgrupo': self.object.id_seccion_subgrupo,
                'id_concepto_de_movimiento': self.object.id_concepto_de_movimiento,
                'tipo_bien': self.object.tipo_bien,
            }
            
            if self.object.id_grupo:
                form.fields['id_subgrupo'].queryset = Subgrupo.objects.filter(
                    id_grupo=self.object.id_grupo
                ).order_by('nombre')
            else:
                form.fields['id_subgrupo'].queryset = Subgrupo.objects.none()
            
            if self.object.id_subgrupo:
                form.fields['id_seccion_subgrupo'].queryset = SeccionSubgrupo.objects.filter(
                    id_subgrupo=self.object.id_subgrupo
                ).order_by('nombre')
            else:
                form.fields['id_seccion_subgrupo'].queryset = SeccionSubgrupo.objects.none()

            if self.object.id_subgrupo:
                form.initial['id_subgrupo'] = self.object.id_subgrupo.pk
            if self.object.id_seccion_subgrupo:
                form.initial['id_seccion_subgrupo'] = self.object.id_seccion_subgrupo.pk
                
        return form

    def get_changes_description(self, form):
        changes = []
        new_state = form.cleaned_data

        # Helper functions
        def get_display_value(instance, model_class):
            if instance is None:
                return "No asignado"
            if isinstance(instance, model_class):
                if model_class == ConceptoDeMovimiento:
                    return f"{instance.codigo} - {instance.nombre}"
                elif model_class == Grupo:
                    return f"{instance.codigo} - {instance.nombre}"
                elif model_class == Subgrupo:
                    return f"{instance.codigo} - {instance.nombre}"
                elif model_class == TipoBien:
                    return str(instance)
            return str(instance)

        def has_changed(old_obj, new_obj, model_class):
            if not old_obj and not new_obj:
                return False
            if not old_obj or not new_obj:
                return True
            if isinstance(old_obj, model_class) and isinstance(new_obj, model_class):
                return old_obj.pk != new_obj.pk
            return old_obj != new_obj

        field_map = {
            'nombre': ('Nombre', None),
            'numero_de_identificacion': ('Número de identificación', None),
            'incorporacion': ('Incorporación', None),
            'desincorporacion': ('Desincorporación', None),
            'condicion': ('Condición', None),
            'observacion': ('Observación', None),
            'id_grupo': ('Grupo', Grupo),
            'id_subgrupo': ('Subgrupo', Subgrupo),
            'id_seccion_subgrupo': ('Sección', SeccionSubgrupo),
            'id_concepto_de_movimiento': ('Concepto de movimiento', ConceptoDeMovimiento),
            'tipo_bien': ('Tipo de bien', TipoBien)
        }

        for field, (display_name, model_class) in field_map.items():
            old_value = self._initial_state.get(field)
            new_value = new_state.get(field)

            if field not in new_state:
                continue

            if model_class and has_changed(old_value, new_value, model_class):
                old_display = get_display_value(old_value, model_class)
                new_display = get_display_value(new_value, model_class)
                changes.append(f"{display_name}: {old_display} → {new_display}")
            elif not model_class and old_value != new_value:
                changes.append(f"{display_name}: {old_value} → {new_value}")

        return changes

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['descripcion_formset'] = DescripcionFormSet(
                self.request.POST, 
                instance=self.object,
                prefix='descripcion'
            )
            context['especificacion_formset'] = EspecificacionFormSet(
                self.request.POST, 
                instance=self.object,
                prefix='especificacion'
            )
        else:
            context['descripcion_formset'] = DescripcionFormSet(
                instance=self.object,
                prefix='descripcion'
            )
            context['especificacion_formset'] = EspecificacionFormSet(
                instance=self.object,
                prefix='especificacion'
            )
        return context

    def form_valid(self, form):
        try:
            with transaction.atomic():
                # Obtener cambios antes de guardar
                changes = self.get_changes_description(form)
                
                # Guardar el bien principal
                self.object = form.save()
                
                # Procesar formsets
                context = self.get_context_data()
                descripcion_formset = context['descripcion_formset']
                especificacion_formset = context['especificacion_formset']

                if descripcion_formset.is_valid() and especificacion_formset.is_valid():
                    if descripcion_formset.has_changed():
                        descripcion_formset.save()
                    if especificacion_formset.has_changed():
                        especificacion_formset.save()
                
                if changes:  # Solo crear entrada en historial si hay cambios reales
                    # Obtener o crear el stock
                    stock, _ = Stock.objects.get_or_create(
                        bien_id=self.object,
                        defaults={'cantidad_total': 1, 'cantidad_disponible': 1}
                    )

                    # Registrar el evento
                    tipo_evento, _ = TiposDeEvento.objects.get_or_create(
                        nombre="EDICION_BIEN",
                        defaults={'descripcion': 'Edición de bien'}
                    )

                    descripcion_evento = f"Edición del bien: {self.object.nombre}"
                    descripcion_evento += "\nCambios realizados:\n" + "\n".join(f"- {change}" for change in changes)

                    HistorialBienes.objects.create(
                        bien_id=self.object,
                        fecha_evento=timezone.now(),
                        id_tipos_de_evento=tipo_evento,
                        descripcion=descripcion_evento,
                        usuario_id=self.request.user,
                        cantidad_afectada=stock.cantidad_total
                    )

                return JsonResponse({
                    'success': True,
                    'redirect_url': self.get_success_url(),
                    'message': "Los cambios se guardaron correctamente."
                })

        except Exception as e:
            logger.error(f"Error al guardar el bien: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': f"Ocurrió un error al guardar los cambios: {str(e)}"
            }, status=500)

    def form_invalid(self, form):
        context = self.get_context_data()
        descripcion_formset = context['descripcion_formset']
        especificacion_formset = context['especificacion_formset']
        
        all_errors = {
            'form_errors': form.errors
        }

        if descripcion_formset.has_changed():
            if not descripcion_formset.is_valid():
                all_errors['descripcion_errors'] = [
                    error for error in descripcion_formset.errors if error
                ]

        if especificacion_formset.has_changed():
            if not especificacion_formset.is_valid():
                all_errors['especificacion_errors'] = [
                    error for error in especificacion_formset.errors if error
                ]
        
        return JsonResponse({
            'success': False,
            'errors': all_errors
        }, status=400)



def verificar_numero_identificacion(request):
    numero = request.GET.get('numero')
    id_bien = request.GET.get('id_bien')
    
    if not numero:
        return JsonResponse({
            'valid': False,
            'message': 'El número de identificación es requerido.'
        })
    
    if not numero.isdigit():
        return JsonResponse({
            'valid': False,
            'message': 'El número debe contener solo dígitos.'
        })
    
    # Consultar si existe el número
    query = Bienes.objects.filter(numero_de_identificacion=numero)
    
    # Si estamos editando, excluir el bien actual
    if id_bien:
        query = query.exclude(pk=id_bien)
    
    existe = query.exists()
    if existe:
        bien = query.first()
        return JsonResponse({
            'valid': False,
            'message': f'Este número ya está en uso por el bien: {bien.nombre}'
        })
    
    return JsonResponse({
        'valid': True,
        'message': 'Número de identificación disponible.'
    })



logger = logging.getLogger(__name__)

@login_required
@user_passes_test(es_admin_bienes)
def pdf_bm1(request):
    department_id = request.GET.get('department_id')
    unidad_id = request.GET.get('unidad_id')
    include_deps = request.GET.get('include_deps') == 'true'
    
    meses_espanol = {
        1: 'ENERO', 2: 'FEBRERO', 3: 'MARZO', 4: 'ABRIL',
        5: 'MAYO', 6: 'JUNIO', 7: 'JULIO', 8: 'AGOSTO',
        9: 'SEPTIEMBRE', 10: 'OCTUBRE', 11: 'NOVIEMBRE', 12: 'DICIEMBRE'
    }
    
    fecha_actual = timezone.now()
    fecha_formateada = f"{meses_espanol[fecha_actual.month]} {fecha_actual.year}"

    def convert_to_float(value):
        if not value or value == '0':
            return 0.0
        try:
            value = value.replace('.', '').replace(',', '.')
            return float(value)
        except (ValueError, AttributeError):
            return 0.0

    def get_unidad_info(unidad, include_departamentos=True):
        info = {
            'tipo': 'unidad',
            'ubicacion': unidad,
            'nombre': unidad.nombre,
            'bienes': [],
            'departamentos': [],
            'total_incorporacion': 0,
            'total_desincorporacion': 0
        }
        
        # Bienes directos de la unidad
        asignaciones_unidad = AsignacionDeBienes.objects.filter(
            id_UnidadOrganizacional=unidad
        ).select_related(
            'id_bienes',
            'id_bienes__id_grupo',
            'id_bienes__id_subgrupo',
            'id_bienes__id_seccion_subgrupo',
            'id_bienes__id_concepto_de_movimiento'
        ).prefetch_related('id_bienes__especificacion_set')
        
        info['bienes'] = [asig.id_bienes for asig in asignaciones_unidad]
        info['total_incorporacion'] = sum(convert_to_float(bien.incorporacion) for bien in info['bienes'])
        info['total_desincorporacion'] = sum(convert_to_float(bien.desincorporacion) for bien in info['bienes'])

        if include_departamentos:
            # Agregar departamentos
            departamentos = Departamentos.objects.filter(UnidadOrganizacional=unidad)
            for dept in departamentos:
                dept_asignaciones = AsignacionDeBienes.objects.filter(
                    id_departamentos=dept
                ).select_related(
                    'id_bienes',
                    'id_bienes__id_grupo',
                    'id_bienes__id_subgrupo',
                    'id_bienes__id_seccion_subgrupo',
                    'id_bienes__id_concepto_de_movimiento'
                ).prefetch_related('id_bienes__especificacion_set')
                
                dept_bienes = [asig.id_bienes for asig in dept_asignaciones]
                if dept_bienes:
                    dept_info = {
                        'tipo': 'departamento',
                        'ubicacion': dept,
                        'nombre': dept.nombre_departamento,
                        'bienes': dept_bienes,
                        'total_incorporacion': sum(convert_to_float(bien.incorporacion) for bien in dept_bienes),
                        'total_desincorporacion': sum(convert_to_float(bien.desincorporacion) for bien in dept_bienes)
                    }
                    info['departamentos'].append(dept_info)
                    if include_deps:  # Solo sumar totales si se incluyen departamentos
                        info['total_incorporacion'] += dept_info['total_incorporacion']
                        info['total_desincorporacion'] += dept_info['total_desincorporacion']

        return info

    def flatten_ubicaciones(ubicaciones):
        flat_list = []
        for ubicacion in ubicaciones:
            # Agregar la unidad primero
            if ubicacion['bienes']:  # Solo agregar si tiene bienes
                flat_list.append({
                    'tipo': ubicacion['tipo'],
                    'nombre': ubicacion['nombre'],
                    'bienes': ubicacion['bienes'],
                    'total_incorporacion': sum(convert_to_float(bien.incorporacion) for bien in ubicacion['bienes'])
                })
            
            # Agregar los departamentos
            if 'departamentos' in ubicacion:
                for dept in ubicacion['departamentos']:
                    if dept['bienes']:  # Solo agregar si tiene bienes
                        flat_list.append({
                            'tipo': 'departamento',
                            'nombre': dept['nombre'],
                            'bienes': dept['bienes'],
                            'total_incorporacion': sum(convert_to_float(bien.incorporacion) for bien in dept['bienes'])
                        })
        
        return flat_list

    ubicaciones_info = []
    total_incorporacion = 0
    total_desincorporacion = 0

    if unidad_id and unidad_id != 'todos':
        # Filtrar por unidad
        unidad = get_object_or_404(UnidadOrganizacional, id_unidad=unidad_id)
        unidad_info = get_unidad_info(unidad, include_departamentos=include_deps)
        ubicaciones_info = flatten_ubicaciones([unidad_info]) if include_deps else [unidad_info]
        total_incorporacion = unidad_info['total_incorporacion']
        total_desincorporacion = unidad_info['total_desincorporacion']
        
    elif department_id and department_id != 'todos':
        # Filtrar por departamento específico
        departamento = get_object_or_404(Departamentos, id_departamentos=department_id)
        dept_asignaciones = AsignacionDeBienes.objects.filter(
            id_departamentos=departamento
        ).select_related(
            'id_bienes',
            'id_bienes__id_grupo',
            'id_bienes__id_subgrupo',
            'id_bienes__id_seccion_subgrupo',
            'id_bienes__id_concepto_de_movimiento'
        ).prefetch_related('id_bienes__especificacion_set')
        
        dept_bienes = [asig.id_bienes for asig in dept_asignaciones]
        
        if dept_bienes:
            dept_info = {
                'tipo': 'departamento',
                'ubicacion': departamento,
                'nombre': departamento.nombre_departamento,
                'bienes': dept_bienes,
                'departamentos': [],  # Sin sub-departamentos
                'total_incorporacion': sum(convert_to_float(bien.incorporacion) for bien in dept_bienes),
                'total_desincorporacion': sum(convert_to_float(bien.desincorporacion) for bien in dept_bienes)
            }
            ubicaciones_info = [dept_info]
            total_incorporacion = dept_info['total_incorporacion']
            total_desincorporacion = dept_info['total_desincorporacion']
    else:
        # Mostrar todas las unidades con sus departamentos
        unidades = UnidadOrganizacional.objects.all()
        for unidad in unidades:
            unidad_info = get_unidad_info(unidad, include_departamentos=True)
            if unidad_info['bienes'] or unidad_info['departamentos']:
                ubicaciones_info.extend(flatten_ubicaciones([unidad_info]))
                total_incorporacion += unidad_info['total_incorporacion']
                total_desincorporacion += unidad_info['total_desincorporacion']

    # Cargar logos
    try:
        logo_esomep_path = os.path.join(settings.STATICFILES_DIRS[0], 'imagenes', 'logoesomep.png')
        logo_portuguesa_path = os.path.join(settings.STATICFILES_DIRS[0], 'imagenes', 'logoportuguesa.png')
        
        with open(logo_esomep_path, 'rb') as f:
            logo_esomep_base64 = base64.b64encode(f.read()).decode()
        with open(logo_portuguesa_path, 'rb') as f:
            logo_portuguesa_base64 = base64.b64encode(f.read()).decode()
    except Exception as e:
        logger.error(f"Error cargando logos: {e}")
        logo_esomep_base64 = ""
        logo_portuguesa_base64 = ""

    context = {
        'ubicaciones_info': ubicaciones_info,
        'fecha': fecha_actual,
        'fecha_periodo': fecha_formateada,
        'total_incorporacion': total_incorporacion,
        'total_desincorporacion': total_desincorporacion,
        'logo_esomep_base64': logo_esomep_base64,
        'logo_portuguesa_base64': logo_portuguesa_base64,
        'es_reporte_completo': not (department_id or unidad_id) or department_id == 'todos' or unidad_id == 'todos'
    }

    html_string = render_to_string('bm1.html', context)
    html = HTML(string=html_string)
    pdf = html.write_pdf()

    response = HttpResponse(pdf, content_type='application/pdf')
    filename = "BM1_Inventario"
    
    if ubicaciones_info:
        if unidad_id and unidad_id != 'todos':
            if include_deps:
                filename += f"_Unidad_y_Deps_{ubicaciones_info[0]['nombre'].replace(' ', '_')}"
            else:
                filename += f"_Solo_Unidad_{ubicaciones_info[0]['nombre'].replace(' ', '_')}"
        elif department_id and department_id != 'todos':
            filename += f"_Departamento_{ubicaciones_info[0]['nombre'].replace(' ', '_')}"
        else:
            filename += "_Completo"
    else:
        filename += "_Sin_Bienes"
    
    filename += ".pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response



@login_required
@user_passes_test(es_admin_bienes)
def menu_reportes(request):
    # Subquery para unidades con usuarios
    unidades_con_usuarios = UnidadOrganizacional.objects.filter(
        Exists(
            Usuario.objects.filter(
                id_unidadOrganizacional=OuterRef('pk'),
                estado='activo'
            )
        )
    ).order_by('nombre')

    # Subquery para departamentos con usuarios
    departamentos_con_usuarios = Departamentos.objects.filter(
        Exists(
            Usuario.objects.filter(
                id_departamentos=OuterRef('pk'),
                estado='activo'
            )
        )
    ).select_related('UnidadOrganizacional').order_by(
        'UnidadOrganizacional__nombre',
        'nombre_departamento'
    )

    context = {
        'departamentos': departamentos_con_usuarios,
        'unidades': unidades_con_usuarios,
    }
    
    return render(request, 'menu_reportes.html', context)

@login_required
@user_passes_test(es_admin_bienes)
def get_departments(request):
    departments = Departamentos.objects.all().order_by('nombre_departamento')
    return JsonResponse({'departments': list(departments.values('id_departamentos', 'nombre_departamento'))})

@login_required
@user_passes_test(es_admin_bienes)
def get_locations(request):
    unidades = UnidadOrganizacional.objects.all().order_by('nombre')
    departamentos = Departamentos.objects.all().select_related('UnidadOrganizacional').order_by('nombre_departamento')
    
    return JsonResponse({
        'unidades': list(unidades.values('id_unidad', 'nombre')),
        'departamentos': list(departamentos.values(
            'id_departamentos', 
            'nombre_departamento',
            'UnidadOrganizacional__id_unidad',
            'UnidadOrganizacional__nombre'
        ))
    })




@login_required
@user_passes_test(es_admin_bienes)
def pdf_bm2(request):
    try:
        def convert_to_float(value):
            if not value:
                return '0,00'
            try:
                float_value = float(str(value).replace('.', '').replace(',', '.'))
                return f"{float_value:,.2f}".replace(',', '@').replace('.', ',').replace('@', '.')
            except (ValueError, AttributeError):
                return '0,00'

        # Obtener parámetros de la solicitud
        department_id = request.GET.get('department_id')
        unidad_id = request.GET.get('unidad_id')
        include_deps = request.GET.get('include_deps') == 'true'
        fecha_inicio = request.GET.get('fecha_inicio')
        fecha_fin = request.GET.get('fecha_fin')

        if not fecha_inicio or not fecha_fin:
            messages.error(request, 'Las fechas son requeridas')
            return redirect('menu_reportes')

        # Procesar fechas
        fecha_inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
        fecha_fin = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
        fecha_fin = fecha_fin.replace(
            day=calendar.monthrange(fecha_fin.year, fecha_fin.month)[1]
        )

        # Query base para movimientos
        base_movimientos = HistorialBienes.objects.select_related(
            'bien_id',
            'bien_id__id_grupo',
            'bien_id__id_subgrupo',
            'bien_id__id_seccion_subgrupo',
            'bien_id__id_concepto_de_movimiento',
            'id_tipos_de_evento',
            'departamento_origen',
            'departamento_destino',
            'UnidadOrganizacional_origen',
            'UnidadOrganizacional_destino',
            'departamento_destino__UnidadOrganizacional',
            'usuario_id'
        ).filter(
            fecha_evento__range=(fecha_inicio, fecha_fin),
            id_tipos_de_evento__nombre__in=[
                'INCORPORACION', 
                'ASIGNACION', 
                'DESINCORPORACION',
                'APROBACION_DESINCORPORACION'
            ]
        )

        # Aplicar filtros según el tipo seleccionado
        if unidad_id and unidad_id != 'todos':
            unidad = get_object_or_404(UnidadOrganizacional, id_unidad=unidad_id)
            if include_deps:
                base_movimientos = base_movimientos.filter(
                    Q(UnidadOrganizacional_origen=unidad) |
                    Q(UnidadOrganizacional_destino=unidad) |
                    Q(departamento_origen__UnidadOrganizacional=unidad) |
                    Q(departamento_destino__UnidadOrganizacional=unidad)
                )
            else:
                base_movimientos = base_movimientos.filter(
                    Q(UnidadOrganizacional_origen=unidad) |
                    Q(UnidadOrganizacional_destino=unidad)
                )
        elif department_id and department_id != 'todos':
            departamento = get_object_or_404(Departamentos, id_departamentos=department_id)
            base_movimientos = base_movimientos.filter(
                Q(departamento_origen=departamento) |
                Q(departamento_destino=departamento)
            )

        # Ordenar movimientos
        movimientos = base_movimientos.order_by(
            'UnidadOrganizacional_destino__nombre',
            'departamento_destino__nombre_departamento',
            'fecha_evento'
        )

        # Preparar datos agrupados
        unidades_data = {}
        total_incorporaciones = 0
        total_desincorporaciones = 0

        for mov in movimientos:
            # Determinar la unidad relevante
            if mov.id_tipos_de_evento.nombre in ['DESINCORPORACION', 'APROBACION_DESINCORPORACION']:
                unidad = mov.UnidadOrganizacional_origen or (
                    mov.departamento_origen.UnidadOrganizacional if mov.departamento_origen else None
                )
            else:
                unidad = mov.UnidadOrganizacional_destino or (
                    mov.departamento_destino.UnidadOrganizacional if mov.departamento_destino else None
                )

            if unidad:
                if unidad not in unidades_data:
                    unidades_data[unidad] = {
                        'nombre': unidad.nombre,
                        'movimientos_directos': [],
                        'departamentos': {},
                        'total_incorporaciones': 0,
                        'total_desincorporaciones': 0
                    }

                # Procesar valor del bien
                mov.bien_id.incorporacion = mov.bien_id.incorporacion if mov.bien_id.incorporacion else '0'
                mov.bien_id.desincorporacion = mov.bien_id.desincorporacion if mov.bien_id.desincorporacion else '0'
                valor_inc = convert_to_float(mov.bien_id.incorporacion)
                valor_des = convert_to_float(mov.bien_id.desincorporacion)

                # Determinar el departamento relevante
                if mov.id_tipos_de_evento.nombre in ['DESINCORPORACION', 'APROBACION_DESINCORPORACION']:
                    dept = mov.departamento_origen
                else:
                    dept = mov.departamento_destino

                if dept:
                    if dept not in unidades_data[unidad]['departamentos']:
                        unidades_data[unidad]['departamentos'][dept] = {
                            'nombre': dept.nombre_departamento,
                            'movimientos': [],
                            'total_incorporaciones': 0,
                            'total_desincorporaciones': 0
                        }
                    
                    unidades_data[unidad]['departamentos'][dept]['movimientos'].append(mov)
                    
                    # Actualizar totales del departamento
                    if mov.id_tipos_de_evento.nombre in ['DESINCORPORACION', 'APROBACION_DESINCORPORACION']:
                        valor_float = float(valor_des.replace('.', '').replace(',', '.'))
                        unidades_data[unidad]['departamentos'][dept]['total_desincorporaciones'] += valor_float
                        total_desincorporaciones += valor_float
                    else:
                        valor_float = float(valor_inc.replace('.', '').replace(',', '.'))
                        unidades_data[unidad]['departamentos'][dept]['total_incorporaciones'] += valor_float
                        total_incorporaciones += valor_float
                else:
                    unidades_data[unidad]['movimientos_directos'].append(mov)
                    # Actualizar totales de la unidad
                    if mov.id_tipos_de_evento.nombre in ['DESINCORPORACION', 'APROBACION_DESINCORPORACION']:
                        valor_float = float(valor_des.replace('.', '').replace(',', '.'))
                        unidades_data[unidad]['total_desincorporaciones'] += valor_float
                        total_desincorporaciones += valor_float
                    else:
                        valor_float = float(valor_inc.replace('.', '').replace(',', '.'))
                        unidades_data[unidad]['total_incorporaciones'] += valor_float
                        total_incorporaciones += valor_float

        # Convertir totales a formato de moneda
        for unidad in unidades_data.values():
            unidad['total_incorporaciones'] = convert_to_float(unidad['total_incorporaciones'])
            unidad['total_desincorporaciones'] = convert_to_float(unidad['total_desincorporaciones'])
            for dept in unidad['departamentos'].values():
                dept['total_incorporaciones'] = convert_to_float(dept['total_incorporaciones'])
                dept['total_desincorporaciones'] = convert_to_float(dept['total_desincorporaciones'])

        # Cargar logos
        try:
            logo_esomep_path = os.path.join(settings.STATICFILES_DIRS[0], 'imagenes', 'logoesomep.png')
            logo_portuguesa_path = os.path.join(settings.STATICFILES_DIRS[0], 'imagenes', 'logoportuguesa.png')
            
            with open(logo_portuguesa_path, 'rb') as f:
                logo_portuguesa_base64 = base64.b64encode(f.read()).decode()
            with open(logo_esomep_path, 'rb') as f:
                logo_esomep_base64 = base64.b64encode(f.read()).decode()
        except Exception as e:
            logger.error(f"Error cargando logos: {e}")
            logo_portuguesa_base64 = ""
            logo_esomep_base64 = ""

        context = {
            'unidades_data': unidades_data,
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'total_incorporaciones': convert_to_float(total_incorporaciones),
            'total_desincorporaciones': convert_to_float(total_desincorporaciones),
            'logo_esomep_base64': logo_esomep_base64,
            'logo_portuguesa_base64': logo_portuguesa_base64,
            'año_actual': timezone.now().year
        }

        # Generar PDF
        html_string = render_to_string('bm2.html', context)
        html = HTML(string=html_string)
        pdf = html.write_pdf()

        # Generar nombre del archivo
        filename = f"BM2_Movimientos_{fecha_inicio.strftime('%Y%m%d')}_{fecha_fin.strftime('%Y%m%d')}"
        
        if unidad_id and unidad_id != 'todos':
            unidad = get_object_or_404(UnidadOrganizacional, id_unidad=unidad_id)
            if include_deps:
                filename += f"_Unidad_y_Deps_{unidad.nombre.replace(' ', '_')}"
            else:
                filename += f"_Solo_Unidad_{unidad.nombre.replace(' ', '_')}"
        elif department_id and department_id != 'todos':
            departamento = get_object_or_404(Departamentos, id_departamentos=department_id)
            filename += f"_Departamento_{departamento.nombre_departamento.replace(' ', '_')}"
        else:
            filename += "_Completo"
        
        filename += ".pdf"
        
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response

    except Exception as e:
        logger.error(f"Error generando reporte BM2: {str(e)}", exc_info=True)
        messages.error(request, f'Error generando el reporte: {str(e)}')
        return redirect('menu_reportes')

@login_required
def crear_solicitud_mantenimiento(request):
    # Verificar que el usuario tenga una ubicación asignada
    if not request.user.id_departamentos and not request.user.id_unidadOrganizacional:
        messages.error(request, 'Debe pertenecer a un departamento o unidad organizacional para crear solicitudes.')
        return redirect('lista_solicitudes')

    if request.method == 'POST':
        form = CrearSolicitudMantenimientoForm(
            user=request.user,  # Cambiado de departamento a user
            data=request.POST
        )
        if form.is_valid():
            try:
                with transaction.atomic():
                    solicitud = form.save(commit=False)
                    solicitud.usuario_id = request.user
                    
                    # Asignar ubicación según el tipo de usuario
                    if request.user.id_departamentos:
                        solicitud.departamento_solicitante = request.user.id_departamentos
                        solicitud.UnidadOrganizacional_solicitante = None
                        origen = f"departamento {request.user.id_departamentos.nombre_departamento}"
                    else:
                        solicitud.UnidadOrganizacional_solicitante = request.user.id_unidadOrganizacional
                        solicitud.departamento_solicitante = None
                        origen = f"unidad organizacional {request.user.id_unidadOrganizacional.nombre}"
                    
                    # Obtener o crear el tipo de solicitud
                    tipo_solicitud, _ = TiposDeSolicitud.objects.get_or_create(
                        nombre='Mantenimiento',
                        defaults={'descripcion': 'Solicitud de mantenimiento de bien'}
                    )
                    
                    solicitud.id_tipos_de_solicitud = tipo_solicitud
                    solicitud.estado_solicitud = 'pendiente'
                    solicitud.cantidad_solicitada = 1
                    solicitud.save()

                    # Notificar a los administradores
                    admin_users = Usuario.objects.filter(
                        Q(id_rol_del_usuario__nombre_rol='ADMIN_BIENES') | 
                        Q(is_superuser=True)
                    ).distinct()

                    for admin in admin_users:
                        Notificacion.objects.create(
                            usuario=admin,
                            solicitud=solicitud,
                            mensaje=f"[ADMIN] Nueva solicitud de mantenimiento creada por {request.user.get_full_name()} desde {origen} para el bien {solicitud.bien_id.nombre}"
                        )

                    # Notificar al usuario
                    Notificacion.objects.create(
                        usuario=request.user,
                        solicitud=solicitud,
                        mensaje=f"Su solicitud de mantenimiento para el bien {solicitud.bien_id.nombre} ha sido creada exitosamente."
                    )

                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': True,
                            'message': 'Solicitud de mantenimiento creada con éxito.',
                            'redirect_url': reverse('lista_solicitudes')
                        })

                    messages.success(request, 'Solicitud de mantenimiento creada con éxito.')
                    return redirect('lista_solicitudes')

            except Exception as e:
                logger.error(f"Error al crear solicitud de mantenimiento: {str(e)}", exc_info=True)
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': f'Error al crear la solicitud: {str(e)}'
                    }, status=500)
                messages.error(request, f'Error al crear la solicitud: {str(e)}')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': 'Por favor, corrija los errores en el formulario.',
                    'errors': form.errors
                }, status=400)
    else:
        form = CrearSolicitudMantenimientoForm(user=request.user)  # Cambiado de departamento a user
    
    return render(request, 'crear_solicitud_mantenimiento.html', {'form': form})

@login_required
@user_passes_test(es_admin_bienes)
def procesar_solicitud_mantenimiento(request, solicitud_id):
    tipo_evento, _ = TiposDeEvento.objects.get_or_create(
        nombre='MANTENIMIENTO',
        defaults={'descripcion': 'Bien en mantenimiento'}
    )

    solicitud = get_object_or_404(
        Solicitudes.objects.select_related(
            'bien_id',
            'usuario_id',
            'departamento_solicitante',
            'UnidadOrganizacional_solicitante'
        ), 
        id_solicitudes=solicitud_id, 
        id_tipos_de_solicitud__nombre='Mantenimiento'
    )
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'rechazar':
            motivo_rechazo = request.POST.get('motivo_rechazo')
            if not motivo_rechazo:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': 'Debe proporcionar un motivo para rechazar la solicitud.'
                    }, status=400)
                messages.error(request, 'Debe proporcionar un motivo para rechazar la solicitud.')
                return render(request, 'procesar_solicitud_mantenimiento.html', {
                    'solicitud': solicitud,
                    'form': ProcesarSolicitudMantenimientoForm()
                })

            try:
                with transaction.atomic():
                    bien = solicitud.bien_id
                    solicitud.estado_solicitud = 'rechazada'
                    solicitud.motivo_rechazo = motivo_rechazo
                    solicitud.save()

                    # Obtener origen para los mensajes
                    origen = None
                    if solicitud.departamento_solicitante:
                        origen = f"departamento {solicitud.departamento_solicitante.nombre_departamento}"
                    elif solicitud.UnidadOrganizacional_solicitante:
                        origen = f"unidad organizacional {solicitud.UnidadOrganizacional_solicitante.nombre}"
                    else:
                        origen = "ubicación desconocida"

                    if bien:
                        HistorialBienes.objects.create(
                            bien_id=bien,
                            fecha_evento=timezone.now(),
                            id_tipos_de_evento=tipo_evento,
                            descripcion=f"Solicitud de mantenimiento rechazada desde {origen}. Motivo: {motivo_rechazo}",
                            cantidad_afectada=1,
                            usuario_id=request.user,
                            departamento_origen=solicitud.departamento_solicitante,
                            UnidadOrganizacional_origen=solicitud.UnidadOrganizacional_solicitante,
                            departamento_destino=None,
                            UnidadOrganizacional_destino=None
                        )

                        # Notificar al usuario
                        Notificacion.objects.create(
                            usuario=solicitud.usuario_id,
                            solicitud=solicitud,
                            mensaje=f"Su solicitud de mantenimiento para el bien '{bien.nombre}' desde {origen} ha sido rechazada. Motivo: {motivo_rechazo}"
                        )

                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': True,
                            'message': 'Solicitud rechazada exitosamente.',
                            'redirect_url': reverse('lista_solicitudes')
                        })
                    messages.success(request, 'Solicitud de mantenimiento rechazada.')
                    return redirect('lista_solicitudes')

            except Exception as e:
                logger.error(f"Error al rechazar la solicitud: {str(e)}", exc_info=True)
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': f'Error al rechazar la solicitud: {str(e)}'
                    }, status=500)
                messages.error(request, f'Error al rechazar la solicitud: {str(e)}')
                return redirect('lista_solicitudes')

        elif action == 'aprobar':
            try:
                with transaction.atomic():
                    bien = solicitud.bien_id
                    
                    # Verificar asignación actual
                    asignacion_actual = AsignacionDeBienes.objects.filter(
                        id_bienes=bien
                    ).order_by('-fecha_de_asignacion').first()
                    
                    if not asignacion_actual:
                        raise ValueError("El bien no tiene una asignación válida.")
                    
                    # Obtener origen para los mensajes
                    origen_texto = None
                    if asignacion_actual.id_departamentos:
                        origen_texto = f"departamento {asignacion_actual.id_departamentos.nombre_departamento}"
                        departamento_anterior = asignacion_actual.id_departamentos
                        unidad_anterior = None
                    elif asignacion_actual.id_UnidadOrganizacional:
                        origen_texto = f"unidad organizacional {asignacion_actual.id_UnidadOrganizacional.nombre}"
                        unidad_anterior = asignacion_actual.id_UnidadOrganizacional
                        departamento_anterior = None
                    else:
                        raise ValueError("El bien no tiene una ubicación válida.")
                    
                    # Actualizar el stock
                    stock, _ = Stock.objects.get_or_create(bien_id=bien)
                    stock.cantidad_asignada -= 1
                    stock.cantidad_en_mantenimiento += 1
                    stock.save()

                    logger.info(f"Stock actualizado para bien {bien.id_bienes}: asignada={stock.cantidad_asignada}, mantenimiento={stock.cantidad_en_mantenimiento}")
                    
                    # Obtener o crear departamento de mantenimiento
                    depto_mantenimiento, _ = Departamentos.objects.get_or_create(
                        nombre_departamento="Bienes en Mantenimiento",
                        defaults={
                            'codigo_departamento': 'MANT',
                            'descripcion': 'Departamento para bienes en mantenimiento'
                        }
                    )

                    logger.info(f"Departamento de mantenimiento: {depto_mantenimiento.id_departamentos}")

                    # Eliminar la asignación actual
                    asignacion_actual.delete()
                    logger.info(f"Asignación anterior eliminada para bien {bien.id_bienes}")

                    # Crear nueva asignación al departamento de mantenimiento
                    nueva_asignacion = AsignacionDeBienes.objects.create(
                        id_bienes=bien,
                        id_departamentos=depto_mantenimiento,
                        id_UnidadOrganizacional=None,
                        cantidad_asignada=1,
                        fecha_de_asignacion=timezone.now()
                    )
                    logger.info(f"Nueva asignación creada: {nueva_asignacion.id_asignacion_bienes}")
                    
                    # Registrar en el historial
                    historial = HistorialBienes.objects.create(
                        bien_id=bien,
                        fecha_evento=timezone.now(),
                        id_tipos_de_evento=tipo_evento,
                        descripcion=f"Enviado a mantenimiento desde {origen_texto}",
                        cantidad_afectada=1,
                        usuario_id=request.user,
                        departamento_origen=departamento_anterior,
                        UnidadOrganizacional_origen=unidad_anterior,
                        departamento_destino=depto_mantenimiento,
                        UnidadOrganizacional_destino=None
                    )
                    logger.info(f"Historial creado: {historial.id}")
                    
                    # Registrar movimiento
                    movimiento = MovimientosBienes.objects.create(
                        bien_id=bien,
                        departamento_solicitante_id=departamento_anterior,
                        UnidadOrganizacional_solicitante=unidad_anterior,
                        departamento_destino_id=depto_mantenimiento,
                        UnidadOrganizacional_destino=None,
                        fecha_movimiento=timezone.now().date(),
                        fecha_entrega=timezone.now().date(),
                        tipo_movimiento='Entrada a Mantenimiento',
                        cantidad=1,
                        usuario_id=request.user,
                        estado_solicitud='aprobada',
                        descripcion=f"Bien enviado a mantenimiento desde {origen_texto}"
                    )
                    logger.info(f"Movimiento registrado: {movimiento.id}")
                    
                    solicitud.estado_solicitud = 'aprobada'
                    solicitud.save()
                    
                    # Notificar al usuario
                    notificacion = Notificacion.objects.create(
                        usuario=solicitud.usuario_id,
                        solicitud=solicitud,
                        mensaje=f"Su solicitud de mantenimiento para el bien '{bien.nombre}' desde {origen_texto} ha sido aprobada."
                    )
                    logger.info(f"Notificación creada: {notificacion.id}")
                    
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': True,
                            'message': 'Solicitud de mantenimiento aprobada con éxito.',
                            'redirect_url': reverse('lista_solicitudes')
                        })
                    
                    messages.success(request, 'Solicitud de mantenimiento aprobada con éxito.')
                    return redirect('lista_solicitudes')
                
            except ValueError as e:
                logger.error(f"Error de validación: {str(e)}")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': str(e)
                    }, status=400)
                messages.error(request, str(e))
                
            except Exception as e:
                logger.error(f"Error al procesar la solicitud: {str(e)}", exc_info=True)
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': f'Error al procesar la solicitud: {str(e)}'
                    }, status=500)
                messages.error(request, f'Error al procesar la solicitud: {str(e)}')

    return render(request, 'procesar_solicitud_mantenimiento.html', {
        'solicitud': solicitud,
        'form': ProcesarSolicitudMantenimientoForm()
    })

@login_required
@user_passes_test(es_admin_bienes)
def retornar_de_mantenimiento(request, bien_id):
    try:
        with transaction.atomic():
            bien = get_object_or_404(Bienes, id_bienes=bien_id)
            
            # Verificar que el bien esté en mantenimiento
            if not bien.esta_en_mantenimiento():
                raise ValueError("Este bien no está en mantenimiento")
            
            # Obtener la asignación actual (debe ser al departamento de mantenimiento)
            asignacion_actual = get_object_or_404(
                AsignacionDeBienes,
                id_bienes=bien,
                id_departamentos__nombre_departamento="Bienes en Mantenimiento"
            )
            
            # Obtener el último historial antes del mantenimiento
            ultimo_historial = HistorialBienes.objects.filter(
                bien_id=bien,
                id_tipos_de_evento__nombre='MANTENIMIENTO'
            ).select_related(
                'departamento_origen',
                'UnidadOrganizacional_origen',
                'usuario_id'
            ).order_by('-fecha_evento').first()
            
            if not ultimo_historial:
                raise ValueError("No se encontró el historial del mantenimiento")
            
            if not (ultimo_historial.departamento_origen or ultimo_historial.UnidadOrganizacional_origen):
                raise ValueError("No se encontró una ubicación válida para devolver el bien")
            
            # Actualizar el stock
            stock = Stock.objects.select_for_update().get(bien_id=bien)
            if stock.cantidad_en_mantenimiento <= 0:
                raise ValueError("No hay unidades en mantenimiento para devolver")
                
            stock.cantidad_en_mantenimiento -= 1
            stock.cantidad_asignada += 1
            stock.save()
            
            # Eliminar la asignación al departamento de mantenimiento
            asignacion_actual.delete()
            
            # Crear nueva asignación al departamento/unidad original
            nueva_asignacion = AsignacionDeBienes.objects.create(
                id_bienes=bien,
                id_departamentos=ultimo_historial.departamento_origen,
                id_UnidadOrganizacional=ultimo_historial.UnidadOrganizacional_origen,
                cantidad_asignada=1,
                fecha_de_asignacion=timezone.now()
            )
            
            # Actualizar la ubicación actual del bien
            bien.ubicacion_actual = (
                ultimo_historial.departamento_origen or 
                ultimo_historial.UnidadOrganizacional_origen
            )
            bien.save()
            
            # Registrar en el historial
            tipo_evento, _ = TiposDeEvento.objects.get_or_create(
                nombre='FIN_MANTENIMIENTO',
                defaults={'descripcion': 'Finalización de mantenimiento'}
            )
            
            destino_texto = (
                f"departamento {ultimo_historial.departamento_origen.nombre_departamento}"
                if ultimo_historial.departamento_origen
                else f"unidad organizacional {ultimo_historial.UnidadOrganizacional_origen.nombre}"
            )
            
            HistorialBienes.objects.create(
                bien_id=bien,
                fecha_evento=timezone.now(),
                id_tipos_de_evento=tipo_evento,
                descripcion=f"Retornado de mantenimiento a {destino_texto}",
                cantidad_afectada=1,
                usuario_id=request.user,
                departamento_origen=asignacion_actual.id_departamentos,
                UnidadOrganizacional_origen=None,
                departamento_destino=ultimo_historial.departamento_origen,
                UnidadOrganizacional_destino=ultimo_historial.UnidadOrganizacional_origen
            )
            
            # Notificar al usuario original si existe
            if ultimo_historial.usuario_id:
                Notificacion.objects.create(
                    usuario=ultimo_historial.usuario_id,
                    mensaje=f"El bien '{bien.nombre}' ha retornado de mantenimiento y ha sido reasignado a {destino_texto}"
                )
            
            messages.success(
                request, 
                f'El bien {bien.nombre} ha sido retornado de mantenimiento exitosamente a {destino_texto}.'
            )
            return redirect('lista_bienes')
            
    except ValueError as e:
        messages.error(request, str(e))
    except AsignacionDeBienes.DoesNotExist:
        messages.error(request, "No se encontró la asignación al departamento de mantenimiento")
    except Exception as e:
        logger.error(f"Error al retornar bien de mantenimiento: {str(e)}", exc_info=True)
        messages.error(request, f'Error al retornar el bien de mantenimiento: {str(e)}')
    
    return redirect('lista_bienes')



@login_required
@user_passes_test(es_admin_bienes)
def bienes_en_mantenimiento(request):
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        bien_id = request.POST.get('bien_id')
        accion = request.POST.get('accion')
        
        try:
            with transaction.atomic():
                bien = Bienes.objects.get(id_bienes=bien_id)
                stock = Stock.objects.get(bien_id=bien)
                
                if accion == 'devolver':
                    # Buscar la ubicación original del bien
                    ultima_asignacion = HistorialBienes.objects.filter(
                        bien_id=bien,
                        id_tipos_de_evento__nombre='MANTENIMIENTO'
                    ).filter(
                        Q(departamento_origen__isnull=False) | 
                        Q(UnidadOrganizacional_origen__isnull=False)
                    ).order_by('-fecha_evento').first()

                    if not ultima_asignacion:
                        return JsonResponse({
                            'success': False,
                            'message': 'No se encontró la ubicación original del bien'
                        })

                    departamento_original = ultima_asignacion.departamento_origen
                    unidad_original = ultima_asignacion.UnidadOrganizacional_origen

                    if not departamento_original and not unidad_original:
                        return JsonResponse({
                            'success': False,
                            'message': 'No se encontró una ubicación válida para devolver el bien'
                        })

                    if stock.cantidad_en_mantenimiento > 0:
                        # Eliminar la asignación al departamento de mantenimiento
                        AsignacionDeBienes.objects.filter(
                            id_bienes=bien,
                            id_departamentos__nombre_departamento__icontains='mantenimiento'
                        ).delete()

                        # Actualizar el stock
                        stock.cantidad_en_mantenimiento -= 1
                        stock.cantidad_asignada += 1
                        stock.save()

                        # Crear nueva asignación al departamento original
                        nueva_asignacion = AsignacionDeBienes.objects.create(
                            id_bienes=bien,
                            id_departamentos=departamento_original,
                            id_UnidadOrganizacional=unidad_original,
                            cantidad_asignada=1,
                            fecha_de_asignacion=timezone.now()
                        )

                        # Actualizar la ubicación actual del bien
                        bien.ubicacion_actual = departamento_original or unidad_original
                        bien.save()

                        # Registrar en historial
                        tipo_evento, _ = TiposDeEvento.objects.get_or_create(
                            nombre='FIN_MANTENIMIENTO',
                            defaults={'descripcion': 'Fin de mantenimiento y devolución'}
                        )

                        # Determinar el texto de la ubicación de destino
                        destino_texto = (
                            f"departamento {departamento_original.nombre_departamento}"
                            if departamento_original
                            else f"unidad organizacional {unidad_original.nombre}"
                        )

                        historial = HistorialBienes.objects.create(
                            bien_id=bien,
                            fecha_evento=timezone.now(),
                            id_tipos_de_evento=tipo_evento,
                            descripcion=f"Bien desvinculado del mantenimiento y devuelto al {destino_texto}",
                            cantidad_afectada=1,
                            usuario_id=request.user,
                            departamento_origen=None,  # Departamento de mantenimiento
                            UnidadOrganizacional_origen=None,
                            departamento_destino=departamento_original,
                            UnidadOrganizacional_destino=unidad_original
                        )

                        # Notificar al usuario original si existe
                        if ultima_asignacion.usuario_id:
                            Notificacion.objects.create(
                                usuario=ultima_asignacion.usuario_id,
                                mensaje=f"El bien '{bien.nombre}' ha sido devuelto de mantenimiento al {destino_texto}"
                            )

                        return JsonResponse({
                            'success': True,
                            'message': f'El bien ha sido devuelto exitosamente al {destino_texto}'
                        })
                    else:
                        return JsonResponse({
                            'success': False,
                            'message': 'No hay unidades en mantenimiento para devolver'
                        })
                else:
                    return JsonResponse({
                        'success': False,
                        'message': 'Acción no reconocida'
                    })
        except Exception as e:
            logger.error(f"Error al procesar devolución de mantenimiento: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'message': f'Error al procesar la solicitud: {str(e)}'
            })
        
    bienes_mantenimiento = Bienes.objects.filter(
            stock__cantidad_en_mantenimiento__gt=0
        ).select_related(
            'stock',
            'id_concepto_de_movimiento'
        ).prefetch_related(
            Prefetch(
                'historialbienes_set',  # Cambiado de historialbien_set a historialbienes_set
                queryset=HistorialBienes.objects.filter(
                    id_tipos_de_evento__nombre='MANTENIMIENTO'
                ).select_related(
                    'departamento_origen',
                    'UnidadOrganizacional_origen'
                ).order_by('-fecha_evento'),
                to_attr='ultimo_mantenimiento'
            )
        )
    
    # Para depuración
    for bien in bienes_mantenimiento:
        logger.debug(f"Bien ID: {bien.id_bienes}")
        if hasattr(bien, 'ultimo_mantenimiento'):
            logger.debug(f"Último mantenimiento: {bien.ultimo_mantenimiento}")
    
    context = {
        'bienes_mantenimiento': bienes_mantenimiento
    }
    return render(request, 'bienes_en_mantenimiento.html', context)


from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.messages.views import SuccessMessageMixin
from .models import ConceptoDeMovimiento

class ConceptoDeMovimientoListView(ListView):
    model = ConceptoDeMovimiento
    template_name = 'concepto_list.html'
    context_object_name = 'conceptos'

    def get_queryset(self):
        queryset = ConceptoDeMovimiento.objects.all()
        search_query = self.request.GET.get('search')
        
        if search_query:
            queryset = queryset.filter(
                Q(codigo__icontains=search_query) |
                Q(nombre__icontains=search_query) |
                Q(descripcion__icontains=search_query)
            )
        
        return queryset.order_by('codigo')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        return context

class ConceptoDeMovimientoCreateView(SuccessMessageMixin, CreateView):
    model = ConceptoDeMovimiento
    form_class = ConceptoDeMovimientoForm
    template_name = 'concepto_form.html'
    success_url = reverse_lazy('concepto_list')
    success_message = "Concepto de movimiento creado exitosamente"

class ConceptoDeMovimientoUpdateView(SuccessMessageMixin, UpdateView):
    model = ConceptoDeMovimiento
    form_class = ConceptoDeMovimientoForm
    template_name = 'concepto_form.html'
    success_url = reverse_lazy('concepto_list')
    success_message = "Concepto de movimiento actualizado exitosamente"

class ConceptoDeMovimientoDeleteView(DeleteView):
    model = ConceptoDeMovimiento
    template_name = 'concepto_confirm_delete.html'
    success_url = reverse_lazy('concepto_list')


# views.py
from datetime import datetime

@login_required
@user_passes_test(es_admin_bienes)
def ficha_tecnica_pdf(request, bien_id):
    bien = get_object_or_404(Bienes, id_bienes=bien_id)
    especificaciones = Especificacion.objects.filter(id_bien=bien)
    descripciones = Descripcion.objects.filter(id_bien=bien)
    
    # Obtener la fecha actual
    fecha_actual = datetime.now().strftime("%d/%m/%Y")
    
    # Formatear la fecha de registro del bien si existe
    fecha_registro = bien.fecha_de_registro.strftime("%d/%m/%Y") if bien.fecha_de_registro else fecha_actual
    
    # Obtener los logos en base64
    logo_esomep_path = os.path.join(settings.STATICFILES_DIRS[0], 'imagenes', 'logoesomep.png')
    logo_portuguesa_path = os.path.join(settings.STATICFILES_DIRS[0], 'imagenes', 'logoportuguesa.png')

    try:
        with open(logo_portuguesa_path, 'rb') as f:
            logo_portuguesa_base64 = base64.b64encode(f.read()).decode()
        with open(logo_esomep_path, 'rb') as f:
            logo_esomep_base64 = base64.b64encode(f.read()).decode()
    except Exception as e:
        print(f"Error cargando logos: {e}")
        logo_portuguesa_base64 = ""
        logo_esomep_base64 = ""

    context = {
        'bien': bien,
        'especificaciones': especificaciones,
        'descripciones': descripciones,
        'logo_esomep_base64': logo_portuguesa_base64,
        'logo_portuguesa_base64': logo_esomep_base64,
        'fecha_actual': fecha_actual,
        'fecha_registro': fecha_registro
    }
    
    html_string = render_to_string('ficha_tecnica_pdf.html', context)
    html = HTML(string=html_string)
    pdf = html.write_pdf()
    
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Ficha_Tecnica_{bien.numero_de_identificacion}.pdf"'
    return response





@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(es_admin_bienes), name='dispatch')
class TiposDeSolicitudListView(ListView):
    model = TiposDeSolicitud
    template_name = 'tipos_solicitud/list.html'
    context_object_name = 'tipos_solicitud'
    ordering = ['nombre']

@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(es_admin_bienes), name='dispatch')
class TiposDeSolicitudCreateView(CreateView):
    model = TiposDeSolicitud
    form_class = TiposDeSolicitudForm
    template_name = 'tipos_solicitud/form.html'
    success_url = reverse_lazy('tipos_solicitud_list')

    def form_valid(self, form):
        messages.success(self.request, 'Tipo de solicitud creado exitosamente.')
        return super().form_valid(form)

@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(es_admin_bienes), name='dispatch')
class TiposDeSolicitudUpdateView(UpdateView):
    model = TiposDeSolicitud
    form_class = TiposDeSolicitudForm
    template_name = 'tipos_solicitud/form.html'
    success_url = reverse_lazy('tipos_solicitud_list')

    def form_valid(self, form):
        messages.success(self.request, 'Tipo de solicitud actualizado exitosamente.')
        return super().form_valid(form)

@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(es_admin_bienes), name='dispatch')
class TiposDeSolicitudDeleteView(DeleteView):
    model = TiposDeSolicitud
    template_name = 'tipos_solicitud/delete.html'
    success_url = reverse_lazy('tipos_solicitud_list')

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Tipo de solicitud eliminado exitosamente.')
        return super().delete(request, *args, **kwargs)




@login_required
@login_required
@user_passes_test(es_admin_bienes)
def admin_dashboard(request):
    context = {
        'total_usuarios': Usuario.objects.count(),
        'total_departamentos': Departamentos.objects.count(),
        'total_bienes': Bienes.objects.count(),
        # Agregar más estadísticas según necesites
    }
    return render(request, 'admin/dashboard.html', context)




def es_admin_bienes(user):
    return user.id_rol_del_usuario.nombre_rol == 'ADMIN_BIENES'

@login_required
@user_passes_test(es_admin_bienes)
def admin_reportes(request):
    hoy = timezone.now()
    primer_dia_mes = hoy.replace(day=1)

    # 1. Estadísticas de Bienes por Estado
    estado_bienes = Bienes.objects.annotate(
        ultimo_evento=Subquery(
            HistorialBienes.objects.filter(
                bien_id=OuterRef('pk')
            ).order_by('-fecha_evento').values('id_tipos_de_evento__nombre')[:1]
        )
    ).aggregate(
        total_operativos=Count('pk', filter=Q(condicion='Operativo')),
        total_no_operativos=Count('pk', filter=Q(condicion='No')),
        total_bienes=Count('pk')
    )

    # 2. Solicitudes Pendientes por Tipo
    solicitudes_stats = Solicitudes.objects.filter(
        estado_solicitud='pendiente'
    ).values('id_tipos_de_solicitud__nombre').annotate(
        total=Count('id_solicitudes')
    ).order_by('-total')

    # 3. Departamentos con más Bienes No Operativos
    departamentos_alertas = Departamentos.objects.annotate(
        total_bienes=Count('asignaciondebienes'),
        bienes_no_operativos=Count(
            'asignaciondebienes',
            filter=Q(asignaciondebienes__id_bienes__condicion='No')
        )
    ).filter(
        bienes_no_operativos__gt=0
    ).annotate(
        porcentaje_no_operativos=ExpressionWrapper(
            F('bienes_no_operativos') * 100.0 / F('total_bienes'),
            output_field=FloatField()
        )
    ).order_by('-porcentaje_no_operativos')[:5]

    # 4. Últimas Desincorporaciones
    ultimas_desincorporaciones = HistorialBienes.objects.filter(
        id_tipos_de_evento__nombre='DESINCORPORACION'
    ).select_related(
        'bien_id', 'departamento_origen', 'UnidadOrganizacional_origen'
    ).order_by('-fecha_evento')[:5]

    # 5. Bienes en Estados Críticos
    bienes_criticos = Bienes.objects.filter(
        Q(stock__cantidad_en_mantenimiento__gt=0) |
        Q(stock__cantidad_resguardada__gt=0)
    ).annotate(
        dias_en_estado=ExpressionWrapper(
            hoy - F('fecha_de_registro'),
            output_field=DurationField()
        )
    ).order_by('-dias_en_estado')[:5]

    # 6. Estadísticas de Mantenimiento
    stats_mantenimiento = HistorialBienes.objects.filter(
        id_tipos_de_evento__nombre='MANTENIMIENTO',
        fecha_evento__gte=primer_dia_mes
    ).aggregate(
        total_en_mantenimiento=Count('id'),
        promedio_dias=Avg(
            ExpressionWrapper(
                timezone.now() - F('fecha_evento'),
                output_field=DurationField()
            )
        )
    )

    # 7. Movimientos del Mes Actual
    movimientos_mes = MovimientosBienes.objects.filter(
        fecha_movimiento__gte=primer_dia_mes
    ).values('tipo_movimiento').annotate(
        total=Count('id')
    ).order_by('-total')

    stats = {
        # Resumen General
        'total_bienes': estado_bienes['total_bienes'],
        'bienes_operativos': estado_bienes['total_operativos'],
        'bienes_no_operativos': estado_bienes['total_no_operativos'],
        'porcentaje_operatividad': round(
            (estado_bienes['total_operativos'] / estado_bienes['total_bienes'] * 100)
            if estado_bienes['total_bienes'] > 0 else 0
        ),

        # Solicitudes y Mantenimiento
        'solicitudes_pendientes': solicitudes_stats,
        'total_mantenimiento': stats_mantenimiento['total_en_mantenimiento'],
        'promedio_dias_mantenimiento': stats_mantenimiento['promedio_dias'].days 
            if stats_mantenimiento['promedio_dias'] else 0,

        # Departamentos y Bienes Críticos
        'departamentos_alertas': departamentos_alertas,
        'bienes_criticos': bienes_criticos,
        'ultimas_desincorporaciones': ultimas_desincorporaciones,

        # Movimientos
        'movimientos_mes': movimientos_mes,
    }

    return render(request, 'admin/reportes.html', {
        'stats': stats,
        'fecha_actual': hoy,
        'page_title': 'Panel de Control de Bienes'
    })





def es_admin_bienes(user):
    return user.id_rol_del_usuario and user.id_rol_del_usuario.nombre_rol == 'ADMIN_BIENES'

@login_required
@user_passes_test(es_admin_bienes)
def pdf_assets_by_department(request, department_id=None):
    # Diccionario de meses en español
    meses_espanol = {
        1: 'ENERO', 2: 'FEBRERO', 3: 'MARZO', 4: 'ABRIL',
        5: 'MAYO', 6: 'JUNIO', 7: 'JULIO', 8: 'AGOSTO',
        9: 'SEPTIEMBRE', 10: 'OCTUBRE', 11: 'NOVIEMBRE', 12: 'DICIEMBRE'
    }
    
    try:
        # Obtener el departamento específico si se proporciona un ID
        if department_id:
            department = Departamentos.objects.get(id_departamentos=department_id)
        else:
            raise ObjectDoesNotExist

        # Obtener fecha actual
        fecha_actual = timezone.now()
        fecha_formateada = f"{meses_espanol[fecha_actual.month]} {fecha_actual.year}"

        # Obtener bienes asignados al departamento
        bienes = Bienes.objects.select_related(
            'id_grupo',
            'id_subgrupo',
            'id_seccion_subgrupo',
            'id_concepto_de_movimiento',
            'stock'
        ).prefetch_related(
            'especificacion_set',
            'asignaciondebienes_set'
        ).filter(
            asignaciondebienes__id_departamentos=department,
            asignaciondebienes__fecha_fin_temporal__isnull=True  # Solo bienes actualmente asignados
        ).distinct()

        # Calcular totales
        totales = bienes.aggregate(
            total_incorporacion=Sum('incorporacion'),
            total_desincorporacion=Sum('desincorporacion'),
            total_bienes=Count('id_bienes')
        )

        # Cargar logos
        logo_esomep_path = os.path.join(settings.STATICFILES_DIRS[0], 'imagenes', 'logoesomep.png')
        logo_portuguesa_path = os.path.join(settings.STATICFILES_DIRS[0], 'imagenes', 'logoportuguesa.png')

        try:
            with open(logo_esomep_path, 'rb') as f:
                logo_esomep_base64 = base64.b64encode(f.read()).decode()
            
            with open(logo_portuguesa_path, 'rb') as f:
                logo_portuguesa_base64 = base64.b64encode(f.read()).decode()
        except Exception as e:
            print(f"Error cargando logos: {e}")
            logo_esomep_base64 = ""
            logo_portuguesa_base64 = ""

        context = {
            'department': department,
            'bienes': bienes,
            'fecha': fecha_actual,
            'fecha_periodo': fecha_formateada,
            'total_incorporacion': totales['total_incorporacion'] or 0,
            'total_desincorporacion': totales['total_desincorporacion'] or 0,
            'total_bienes': totales['total_bienes'] or 0,
            'logo_esomep_base64': logo_esomep_base64,
            'logo_portuguesa_base64': logo_portuguesa_base64
        }

        html_string = render_to_string('department_assets_report.html', context)
        html = HTML(string=html_string)
        pdf = html.write_pdf()

        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="Inventario_{department.nombre_departamento}.pdf"'
        return response

    except ObjectDoesNotExist:
        return HttpResponse("Departamento no encontrado", status=404)
    except Exception as e:
        return HttpResponse(f"Error generando el reporte: {str(e)}", status=500)


@login_required
@require_http_methods(["POST"])
def actualizar_concepto_movimiento(request, bien_id):
    """Vista para actualizar rápidamente el concepto de movimiento de un bien"""
    bien = get_object_or_404(Bienes, id_bienes=bien_id)
    nuevo_concepto_id = request.POST.get('concepto_id')
    
    try:
        nuevo_concepto = ConceptoDeMovimiento.objects.get(id_concepto_de_movimiento=nuevo_concepto_id)
        concepto_anterior = bien.id_concepto_de_movimiento
        
        # Actualizar el concepto
        bien.id_concepto_de_movimiento = nuevo_concepto
        bien.save()
        
        # Registrar en el historial
        tipo_evento = TiposDeEvento.objects.get(nombre="CAMBIO_CONCEPTO")
        HistorialBienes.objects.create(
            bien_id=bien,
            fecha_evento=timezone.now(),
            id_tipos_de_evento=tipo_evento,
            descripcion=f"Cambio de concepto de movimiento de {concepto_anterior} a {nuevo_concepto}",
            cantidad_afectada=1,
            usuario_id=request.user
        )
        
        return JsonResponse({
            'success': True,
            'mensaje': 'Concepto actualizado correctamente',
            'nuevo_concepto': str(nuevo_concepto)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'mensaje': f'Error al actualizar el concepto: {str(e)}'
        }, status=400)

@login_required
def obtener_conceptos_movimiento(request):
    """Vista para obtener la lista de conceptos de movimiento disponibles"""
    conceptos = ConceptoDeMovimiento.objects.all().values('id_concepto_de_movimiento', 'nombre')
    return JsonResponse(list(conceptos), safe=False)




class DocumentGenerator:
    def __init__(self):
        self.logo_paths = {
            'esomep': os.path.join(settings.STATICFILES_DIRS[0], 'imagenes', 'logoesomep.png'),
            'portuguesa': os.path.join(settings.STATICFILES_DIRS[0], 'imagenes', 'logoportuguesa.png')
        }
        self.logos_base64 = self._load_logos()
        
    def _load_logos(self):
        logos = {}
        for key, path in self.logo_paths.items():
            try:
                with open(path, 'rb') as f:
                    logos[key] = base64.b64encode(f.read()).decode()
            except Exception as e:
                print(f"Error cargando logo {key}: {e}")
                logos[key] = ""
        return logos

    def _get_base_context(self):
        return {
            'logo_esomep_base64': self.logos_base64['esomep'],
            'logo_portuguesa_base64': self.logos_base64['portuguesa'],
            'fecha_actual': timezone.now().strftime("%d/%m/%Y"),
            'año_actual': timezone.now().year
        }

    def generar_acta_traslado_temporal(self, traslado):
        context = self._get_base_context()
        context.update({
            'traslado': traslado,
            'tipo_movimiento': 'TRASLADO TEMPORAL',
            'departamento_origen': traslado.departamento_origen,
            'departamento_destino': traslado.departamento_destino,
            'UnidadOrganizacional_origen': traslado.UnidadOrganizacional_origen,
            'UnidadOrganizacional_destino': traslado.UnidadOrganizacional_destino,
            'bien': traslado.bien_id,
            'motivo': traslado.descripcion,
            'origen_nombre': traslado.departamento_origen.nombre_departamento if traslado.departamento_origen else traslado.UnidadOrganizacional_origen.nombre if traslado.UnidadOrganizacional_origen else "",
            'destino_nombre': traslado.departamento_destino.nombre_departamento if traslado.departamento_destino else traslado.UnidadOrganizacional_destino.nombre if traslado.UnidadOrganizacional_destino else ""
        })
        
        return self._render_pdf('actas/traslado_temporal.html', context)

    def generar_acta_desincorporacion(self, desincorporacion):
        context = self._get_base_context()
        context.update({
            'desincorporacion': desincorporacion,
            'tipo_movimiento': 'DESINCORPORACION',
            'bien': desincorporacion.bien_id,
            'motivo_detallado': desincorporacion.descripcion,
            'valor_desincorporacion': desincorporacion.bien_id.desincorporacion,
            'departamento_origen': desincorporacion.departamento_origen,
            'UnidadOrganizacional_origen': desincorporacion.UnidadOrganizacional_origen,
            'usuario_responsable': desincorporacion.usuario_id,
            'detalles_condicion': self._get_detalles_condicion(desincorporacion.bien_id),
            'origen_nombre': desincorporacion.departamento_origen.nombre_departamento if desincorporacion.departamento_origen else desincorporacion.UnidadOrganizacional_origen.nombre if desincorporacion.UnidadOrganizacional_origen else ""
        })
        
        return self._render_pdf('actas/desincorporacion.html', context)

    def _generar_fin_mantenimiento(self, historial):
        context = self._get_base_context()
        descripcion_pdf = DescripcionPDF.objects.filter(historial=historial).first()
        detalles = descripcion_pdf.detalles_adicionales if descripcion_pdf else {}
        
        context.update({
            'tipo_movimiento': 'FIN DE MANTENIMIENTO',
            'bien': historial.bien_id,
            'departamento_destino': historial.departamento_destino,
            'UnidadOrganizacional_destino': historial.UnidadOrganizacional_destino,
            'descripcion': descripcion_pdf.descripcion if descripcion_pdf else historial.descripcion,
            'usuario_responsable': historial.usuario_id,
            'fecha_evento': historial.fecha_evento.strftime("%d/%m/%Y"),
            'tipo_mantenimiento': detalles.get('tipo_mantenimiento', ''),
            'fallas_encontradas': detalles.get('fallas_encontradas', ''),
            'solucion_aplicada': detalles.get('solucion_aplicada', ''),
            'destino_nombre': historial.departamento_destino.nombre_departamento if historial.departamento_destino else historial.UnidadOrganizacional_destino.nombre if historial.UnidadOrganizacional_destino else ""
        })
        
        return self._render_pdf('actas/fin_mantenimiento.html', context)

    def generar_acta_mantenimiento(self, mantenimiento):
        context = self._get_base_context()
        context.update({
            'mantenimiento': mantenimiento,
            'tipo_movimiento': 'ENTRADA A MANTENIMIENTO',
            'bien': mantenimiento.bien_id,
            'departamento_origen': mantenimiento.departamento_origen,
            'UnidadOrganizacional_origen': mantenimiento.UnidadOrganizacional_origen,
            'descripcion_falla': mantenimiento.descripcion,
            'usuario_responsable': mantenimiento.usuario_id,
            'fecha_entrada': mantenimiento.fecha_evento.strftime("%d/%m/%Y"),
            'origen_nombre': mantenimiento.departamento_origen.nombre_departamento if mantenimiento.departamento_origen else mantenimiento.UnidadOrganizacional_origen.nombre if mantenimiento.UnidadOrganizacional_origen else ""
        })
        
        return self._render_pdf('actas/mantenimiento.html', context)

    def generar_acta_asignacion(self, asignacion):
        context = self._get_base_context()
        context.update({
            'asignacion': asignacion,
            'tipo_movimiento': 'ASIGNACIÓN',
            'bien': asignacion.id_bienes,
            'departamento_destino': asignacion.id_departamentos,
            'UnidadOrganizacional_destino': asignacion.id_UnidadOrganizacional,
            'fecha_asignacion': asignacion.fecha_de_asignacion.strftime("%d/%m/%Y"),
            'cantidad': asignacion.cantidad_asignada,
            'especificaciones': asignacion.id_bienes.especificacion_set.all(),
            'descripciones': asignacion.id_bienes.descripcion_set.all(),
            'destino_nombre': asignacion.id_departamentos.nombre_departamento if asignacion.id_departamentos else asignacion.id_UnidadOrganizacional.nombre if asignacion.id_UnidadOrganizacional else ""
        })
        
        return self._render_pdf('actas/asignacion.html', context)

    def generar_acta_resguardo(self, resguardo):
        context = self._get_base_context()
        
        # Preparar información de origen
        origen_info = self._get_origen_info(resguardo)
        
        context.update({
            'resguardo': resguardo,
            'tipo_movimiento': 'ENTRADA A RESGUARDO',
            'bien': resguardo.bien_id,
            'departamento_origen': resguardo.departamento_origen,
            'UnidadOrganizacional_origen': resguardo.UnidadOrganizacional_origen,
            'motivo': resguardo.descripcion,
            'usuario_responsable': resguardo.usuario_id,
            'fecha_resguardo': resguardo.fecha_evento.strftime("%d/%m/%Y"),
            'unidad_origen': resguardo.UnidadOrganizacional_origen,  # Añadido para coincidir con el template
            'origen_completo': origen_info['origen_completo']
        })
        
        return self._render_pdf('actas/resguardo.html', context)

    def _get_origen_info(self, historial):
        """
        Prepara la información de origen formateada.
        """
        origen_info = {
            'origen_completo': '',
            'origen_nombre': ''
        }

        if historial.UnidadOrganizacional_origen and historial.departamento_origen:
            origen_info['origen_completo'] = (
                f"Unidad: {historial.UnidadOrganizacional_origen.nombre}\n"
                f"Departamento: {historial.departamento_origen.nombre_departamento}"
            )
            origen_info['origen_nombre'] = (
                f"{historial.UnidadOrganizacional_origen.nombre} - "
                f"{historial.departamento_origen.nombre_departamento}"
            )
        elif historial.UnidadOrganizacional_origen:
            origen_info['origen_completo'] = f"Unidad: {historial.UnidadOrganizacional_origen.nombre}"
            origen_info['origen_nombre'] = historial.UnidadOrganizacional_origen.nombre
        elif historial.departamento_origen:
            origen_info['origen_completo'] = f"Departamento: {historial.departamento_origen.nombre_departamento}"
            origen_info['origen_nombre'] = historial.departamento_origen.nombre_departamento

        return origen_info

    def _get_detalles_condicion(self, bien):
        detalles = []
        if bien.descripcion_set.exists():
            for desc in bien.descripcion_set.all():
                detalles.append({
                    'descripcion': desc.descripcion,
                    'estado': desc.estado
                })
        return detalles

    def _render_pdf(self, template_name, context):
        html_string = render_to_string(template_name, context)
        html = HTML(string=html_string)
        pdf = html.write_pdf()
        
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{context["tipo_movimiento"].lower().replace(" ", "_")}.pdf"'
        return response




class UnidadOrganizacionalListView(LoginRequiredMixin, ListView):
   model = UnidadOrganizacional
   template_name = 'unidad/unidad_list.html'
   context_object_name = 'unidades'
   paginate_by = 10
   
   def get_queryset(self):
       queryset = super().get_queryset()
       search_query = self.request.GET.get('search', '')
       if search_query:
           queryset = queryset.filter(
               Q(codigo__icontains=search_query) |
               Q(nombre__icontains=search_query) |
               Q(descripcion__icontains=search_query)
           )
       return queryset.order_by('codigo')

class UnidadOrganizacionalCreateView(LoginRequiredMixin, CreateView):
   model = UnidadOrganizacional
   form_class = UnidadOrganizacionalForm
   template_name = 'unidad/unidad_form.html'
   success_url = reverse_lazy('unidad_list')
   
   def form_valid(self, form):
       messages.success(self.request, 'Unidad organizacional creada exitosamente.')
       return super().form_valid(form)

class UnidadOrganizacionalUpdateView(LoginRequiredMixin, UpdateView):
   model = UnidadOrganizacional
   form_class = UnidadOrganizacionalForm 
   template_name = 'unidad/unidad_form.html'
   success_url = reverse_lazy('unidad_list')
   
   def form_valid(self, form):
       messages.success(self.request, 'Unidad organizacional actualizada exitosamente.')
       return super().form_valid(form)

class UnidadOrganizacionalDeleteView(LoginRequiredMixin, DeleteView):
   model = UnidadOrganizacional
   template_name = 'unidad/unidad_confirm_delete.html'
   success_url = reverse_lazy('unidad_list')
   
   def delete(self, request, *args, **kwargs):
       messages.success(request, 'Unidad organizacional eliminada exitosamente.')
       return super().delete(request, *args, **kwargs)



@login_required
@user_passes_test(es_admin_bienes)
def generar_pdf_historial(request, historial_id):
    try:
        historial = get_object_or_404(HistorialBienes, id=historial_id)
        
        # Verificar si ya existe una descripción PDF
        descripcion_pdf = DescripcionPDF.objects.filter(historial=historial).first()
        
        # Si existe descripción o es POST, generar PDF
        if descripcion_pdf or request.method == 'POST':
            generator = DocumentService()
            
            if historial.id_tipos_de_evento.nombre == 'TRASLADO_TEMPORAL':
                return generator._generar_traslado_temporal(historial)
            elif historial.id_tipos_de_evento.nombre == 'DESINCORPORACION':
                return generator._generar_desincorporacion(historial)
            elif historial.id_tipos_de_evento.nombre == 'MANTENIMIENTO':
                return generator._generar_mantenimiento(historial)
            elif historial.id_tipos_de_evento.nombre == 'FIN_MANTENIMIENTO':
                return generator._generar_fin_mantenimiento(historial)
            elif historial.id_tipos_de_evento.nombre == 'ASIGNACION':
                return generator._generar_asignacion(historial)
            elif historial.id_tipos_de_evento.nombre == 'RESGUARDO':
                return generator._generar_resguardo(historial)
            elif historial.id_tipos_de_evento.nombre == 'TRASLADO_PERMANENTE':
                return generator._generar_traslado_permanente(historial)
            else:
                messages.warning(request, 'No hay plantilla de documento para este tipo de evento')
                return redirect('historial_bien', bien_id=historial.bien_id.id_bienes)

        # Si no hay descripción, mostrar formulario
        return render(request, 'generar_pdf.html', {
            'historial': historial,
            'tipo_evento': historial.id_tipos_de_evento.nombre
        })

    except Exception as e:
        messages.error(request, f'Error al generar documento: {str(e)}')
        return redirect('historial_bien', bien_id=historial.bien_id.id_bienes if historial and historial.bien_id else None)



@login_required
@user_passes_test(es_admin_bienes)
def guardar_descripcion_pdf(request, historial_id):
    try:
        historial = get_object_or_404(HistorialBienes, id=historial_id)
        
        if request.method == 'POST':
            # Recoger los detalles según el tipo de evento
            detalles_adicionales = {}
            tipo_evento = historial.id_tipos_de_evento.nombre
            
            if tipo_evento == 'TRASLADO_TEMPORAL':
                detalles_adicionales = {
                    'motivo_traslado': request.POST.get('motivo_traslado'),
                    'tiempo_estimado': request.POST.get('tiempo_estimado')
                }
            elif tipo_evento == 'TRASLADO_PERMANENTE':
                detalles_adicionales = {
                    'motivo_traslado': request.POST.get('motivo_traslado'),
                    'observaciones': request.POST.get('observaciones', '')
                }
            elif tipo_evento == 'MANTENIMIENTO':
                detalles_adicionales = {
                    'tipo_mantenimiento': request.POST.get('tipo_mantenimiento'),
                    'fallas_encontradas': request.POST.get('fallas_encontradas'),
                    'solucion_aplicada': request.POST.get('solucion_aplicada')
                }
            elif tipo_evento == 'FIN_MANTENIMIENTO':
                detalles_adicionales = {
                    'trabajos_realizados': request.POST.get('trabajos_realizados'),
                    'estado_final': request.POST.get('estado_final'),
                    'recomendaciones': request.POST.get('recomendaciones', '')
                }
            elif tipo_evento == 'DESINCORPORACION':
                detalles_adicionales = {
                    'motivo_desincorporacion': request.POST.get('motivo_desincorporacion'),
                    'explicacion_desincorporacion': request.POST.get('explicacion_desincorporacion')
                }
            elif tipo_evento == 'RESGUARDO':
                detalles_adicionales = {
                    'motivo_resguardo': request.POST.get('motivo_resguardo'),
                    'ubicacion_resguardo': request.POST.get('ubicacion_resguardo')
                }
            
            # Guardar la descripción
            DescripcionPDF.objects.update_or_create(
                historial=historial,
                defaults={
                    'descripcion': request.POST.get('descripcion'),
                    'detalles_adicionales': detalles_adicionales
                }
            )
            
            return redirect('historial_bien_pdf', historial_id=historial_id)
            
    except HistorialBienes.DoesNotExist:
        messages.error(request, 'Registro de historial no encontrado')
    except Exception as e:
        messages.error(request, f'Error al guardar la descripción: {str(e)}')
    
    return redirect('historial_bien', bien_id=historial.bien_id.id_bienes)


class BaseNotificationListView(LoginRequiredMixin, ListView):
    model = Notificacion
    template_name = 'notificaciones/lista_notificaciones.html'
    context_object_name = 'notificaciones'
    paginate_by = 10

    def get_queryset(self):
        return Notificacion.objects.filter(usuario=self.request.user).order_by('-fecha')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['no_leidas'] = self.get_queryset().filter(leida=False).count()
        return context



def role_required(allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            
            if not request.user.id_rol_del_usuario or \
               request.user.id_rol_del_usuario.nombre_rol not in allowed_roles:
                messages.error(request, 'No tienes permiso para acceder a esta página.')
                return redirect('home')
                
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

@login_required
@role_required(['USUARIO_ESTANDAR'])
def usuario_estandar_notificaciones(request):
    notificaciones = Notificacion.objects.filter(
        usuario=request.user
    ).order_by('-fecha')
    
    paginator = Paginator(notificaciones, 10)
    page = request.GET.get('page')
    notificaciones_paginadas = paginator.get_page(page)
    
    context = {
        'notificaciones': notificaciones_paginadas,
        'no_leidas': notificaciones.filter(leida=False).count()
    }
    
    return render(request, 'notificaciones/usuario_estandar_notificaciones.html', context)

@login_required
@role_required(['ADMIN_BIENES'])
def admin_notificaciones(request):
    # Obtener solo las notificaciones del usuario actual
    notificaciones = Notificacion.objects.filter(
        usuario=request.user
    ).order_by('-fecha')
    
    # Filtros
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    leida = request.GET.get('leida')
    
    if fecha_desde:
        notificaciones = notificaciones.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        notificaciones = notificaciones.filter(fecha__lte=fecha_hasta)
    if leida in ['true', 'false']:
        notificaciones = notificaciones.filter(leida=leida == 'true')
    
    # Paginación
    paginator = Paginator(notificaciones, 8)  # Cambiado a 8 para mejor presentación
    page = request.GET.get('page')
    notificaciones_paginadas = paginator.get_page(page)
    
    context = {
        'notificaciones': notificaciones_paginadas,
        'filtros': {
            'fecha_desde': fecha_desde,
            'fecha_hasta': fecha_hasta,
            'leida': leida
        },
        'total_notificaciones': notificaciones.count(),
        'no_leidas': notificaciones.filter(leida=False).count()
    }
    
    return render(request, 'notificaciones/admin_notificaciones.html', context)

@login_required
def marcar_como_leida(request, notificacion_id):
    try:
        notificacion = get_object_or_404(Notificacion, id=notificacion_id, usuario=request.user)
        notificacion.leida = True
        notificacion.save()
        
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        
        messages.success(request, 'Notificación marcada como leída.')
        return redirect('lista_notificaciones')
        
    except Exception as e:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': str(e)})
        
        messages.error(request, f'Error al marcar la notificación: {str(e)}')
        return redirect('lista_notificaciones')

@login_required
def marcar_todas_como_leidas(request):
    try:
        Notificacion.objects.filter(usuario=request.user, leida=False).update(leida=True)
        
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
            
        messages.success(request, 'Todas las notificaciones han sido marcadas como leídas.')
    except Exception as e:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': str(e)})
            
        messages.error(request, f'Error al marcar las notificaciones: {str(e)}')
    
    return redirect('lista_notificaciones')

@login_required
def eliminar_notificacion(request, notificacion_id):
    try:
        notificacion = get_object_or_404(Notificacion, id=notificacion_id, usuario=request.user)
        notificacion.delete()
        
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
            
        messages.success(request, 'Notificación eliminada correctamente.')
    except Exception as e:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': str(e)})
            
        messages.error(request, f'Error al eliminar la notificación: {str(e)}')
    
    return redirect('lista_notificaciones')


@login_required
def get_unread_notifications_count(request):
    count = Notificacion.objects.filter(
        usuario=request.user,
        leida=False
    ).count()
    
    return JsonResponse({'count': count})

@login_required
def get_notificaciones_count(request):
    """
    Endpoint de API para obtener el conteo de notificaciones no leídas
    """
    try:
        count = Notificacion.objects.filter(
            usuario=request.user,
            leida=False
        ).count()
        
        return JsonResponse({
            'success': True,
            'has_unread': count > 0,
            'unread_count': count
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

def add_notification_context(request):
    """
    Context processor para agregar el conteo de notificaciones a todas las templates
    """
    context = {
        'has_unread_notifications': False,
        'unread_count': 0
    }
    
    if request.user.is_authenticated:
        count = Notificacion.objects.filter(
            usuario=request.user,
            leida=False
        ).count()
        context.update({
            'has_unread_notifications': count > 0,
            'unread_count': count
        })
    
    return context