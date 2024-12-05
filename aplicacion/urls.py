from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from .views import  BienListView, BienUpdateView
from .views import  ListaUsuariosView,  RestablecerContrasenaView, AsignarRolesView, BienDeleteView, StockListView
from .views import TiposDeSolicitudListView, TiposDeSolicitudDeleteView
from .views import (
    GrupoListView, GrupoCreateView, GrupoUpdateView, GrupoDeleteView,
    SubgrupoListView, SubgrupoCreateView, SubgrupoUpdateView, SubgrupoDeleteView,
    SeccionSubgrupoListView, SeccionSubgrupoCreateView, SeccionSubgrupoUpdateView, SeccionSubgrupoDeleteView,     ConceptoDeMovimientoListView,
    ConceptoDeMovimientoCreateView, ConceptoDeMovimientoUpdateView, ConceptoDeMovimientoDeleteView,    TiposDeSolicitudListView,
    TiposDeSolicitudCreateView,
    TiposDeSolicitudUpdateView,
    TiposDeSolicitudDeleteView,
)


urlpatterns = [
    path('', views.index, name='index'),

    # URLs para Bien
    path('bienes/', views.BienListView.as_view(), name='bien_list'),
    path('bienes/nuevo/', views.BienCreateView.as_view(), name='bien_create'),
    path('bienes/<int:bien_id>/', views.bien_descripcion, name='bien_descripcion'),
    path('bienes/pdf/', views.pdf_bienes, name='pdf_bienes'),
    path('bienes/<int:pk>/delete/', BienDeleteView.as_view(), name='bien_delete'),
    path('api/notificaciones/', views.api_notificaciones, name='api_notificaciones'),
    path('bien/<int:pk>/edit/', BienUpdateView.as_view(), name='bien_edit'),


    #####################################################################
    path('usuarios/', ListaUsuariosView.as_view(), name='lista_usuarios'),
    #Solicitud
    path('crear-solicitud/', views.crear_solicitud, name='crear_solicitud'),
    path('lista-solicitudes/', views.lista_solicitudes, name='lista_solicitudes'),
    path('solicitudes/', views.lista_solicitudes, name='lista_solicitudes'),


    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    #path('registro/', views.registro, name='registro'),
    #path('acceso-denegado/', views.acceso_denegado, name='acceso_denegado'),

    
    
    
    path('solicitud/<int:solicitud_id>/', views.detalle_solicitud, name='detalle_solicitud'),

    ##########################################################################


    path('asignar-bienes/', views.asignar_bienes, name='asignar_bienes_departamento'),
    path('bienes-asignados/', views.bienes_asignados, name='bienes_asignados'),

    path('registro/', views.registro_usuario, name='registro_usuario'),

    path('admin-bienes/usuarios/', ListaUsuariosView.as_view(), name='lista_usuarios'),
    path('admin-bienes/usuario/<int:pk>/restablecer-contrasena/', RestablecerContrasenaView.as_view(), name='restablecer_contrasena'),
    path('admin-bienes/usuario/<int:pk>/asignar-rol/', AsignarRolesView.as_view(), name='asignar_roles'),

    # URL para la página principal de gestión de usuarios (donde estarán los botones)
    path('admin-bienes/gestion-usuarios/', views.gestion_usuarios, name='gestion_usuarios'),


    path('listar_departamentos/', views.listar_departamentos, name='listar_departamentos'),
    path('agregar/', views.agregar_departamento, name='agregar_departamento'),
    path('editar/<int:id_departamento>/', views.editar_departamento, name='editar_departamento'),
    path('eliminar/<int:id_departamento>/', views.eliminar_departamento, name='eliminar_departamento'),


    path('inventario-activo/', views.inventario_activo, name='inventario_activo'),

    path('bien/lista/', views.BienListView.as_view(), name='bien_list'),
    path('bien/crear/', views.BienCreateView.as_view(), name='bien_create'),
    path('bien/eliminar/<int:pk>/', views.BienDeleteView.as_view(), name='bien_delete'),
    path('stock/<int:pk>/', views.StockDetailView.as_view(), name='stock_detail'),
    path('stock/lista/', StockListView.as_view(), name='stock_list'),

    path('solicitud/crear/', views.crear_solicitud, name='crear_solicitud'),
    path('solicitudes/', views.lista_solicitudes, name='lista_solicitudes'),



    path('api/notificaciones/', views.api_notificaciones, name='api_notificaciones'),
    path('solicitud_desincorporacion', views.solicitud_desincorporacion, name='solicitud_desincorporacion'),
    path('procesar-desincorporacion/<int:solicitud_id>/', views.procesar_desincorporacion, name='procesar_desincorporacion'),
    path('bienes_usuarios/', views.bienes_usuario, name='bienes_usuarios'),
    path('bienes-admin/', views.bienes_admin, name='bienes_admin'),
    path('bienes-resguardados/', views.bienes_resguardados, name='bienes_resguardados'),
    path('solicitud/permanente/crear/', views.crear_solicitud_permanente, name='crear_solicitud_permanente'),
    path('solicitud/permanente/procesar/<int:solicitud_id>/', views.procesar_solicitud_permanente, name='procesar_solicitud_permanente'),
    path('solicitud/temporal/crear/', views.crear_solicitud_temporal, name='crear_solicitud_temporal'),
    path('api/bien/<int:bien_id>/info/', views.get_bien_info, name='get_bien_info'),
    path('mi-perfil/', views.ver_mi_perfil, name='ver_mi_perfil'),

    path('tipos-solicitudes/', TiposDeSolicitudListView.as_view(), name='tipos-de-solicitud-list'),
    path('solicitudes/eliminar/<int:pk>/', TiposDeSolicitudDeleteView.as_view(), name='tipos-de-solicitud-delete'),

    path('historial-bien/<int:bien_id>/', views.historial_bien, name='historial_bien'),
    path('finalizar-traslado-temporal/<int:asignacion_id>/', views.finalizar_traslado_temporal, name='finalizar_traslado_temporal'),
    path('solicitud/temporal/<int:solicitud_id>/procesar/', views.procesar_solicitud_temporal, name='procesar_solicitud_temporal'),
    path('bienes-en-traslado-temporal/', views.listar_bienes_en_traslado_temporal, name='listar_bienes_en_traslado_temporal'),
    path('finalizar-traslado-temporal/<int:asignacion_id>/', views.finalizar_traslado_temporal, name='finalizar_traslado_temporal'),
    path('api/cantidad_disponible/<int:bien_id>/', views.cantidad_disponible, name='cantidad_disponible'),
    path('finalizar-traslado-temporal/<int:asignacion_id>/', views.finalizar_traslado_temporal, name='finalizar_traslado_temporal'),

    path('solicitud/nuevo-bien/crear/', views.crear_solicitud_nuevo_bien, name='crear_solicitud_nuevo_bien'),
    path('solicitud/nuevo-bien/procesar/<int:solicitud_id>/',views.procesar_solicitud_nuevo_bien, name='procesar_solicitud_nuevo_bien'),
    path('tipos-bien/crear/', views.crear_tipo_bien, name='crear_tipo_bien'),
    path('tipos-bien/<int:pk>/editar/', views.editar_tipo_bien, name='editar_tipo_bien'),
    path('tipos-bien/<int:pk>/', views.detalle_tipo_bien, name='detalle_tipo_bien'),
    path('inventario-por-tipo/', views.inventario_por_tipo, name='inventario_por_tipo'),
    path('api/obtener_departamento_destino/<int:bien_id>/', views.obtener_departamento_destino, name='obtener_departamento_destino'),
    path('bienes-desincorporados/', views.bienes_desincorporados, name='bienes_desincorporados'),


    # URLs para Grupo
    path('grupos/', GrupoListView.as_view(), name='grupo-list'),
    path('grupos/create/', GrupoCreateView.as_view(), name='grupo-create'),
    path('grupos/update/<int:pk>/', GrupoUpdateView.as_view(), name='grupo-update'),
    path('grupos/delete/<int:pk>/', GrupoDeleteView.as_view(), name='grupo-delete'),

    # URLs para Subgrupo
    path('subgrupos/', SubgrupoListView.as_view(), name='subgrupo_list'),
    path('subgrupos/nuevo/', SubgrupoCreateView.as_view(), name='subgrupo_create'),
    path('subgrupos/<int:pk>/editar/', SubgrupoUpdateView.as_view(), name='subgrupo_update'),
    path('subgrupos/<int:pk>/eliminar/', SubgrupoDeleteView.as_view(), name='subgrupo_delete'),

    # URLs para SeccionSubgrupo
    path('secciones/', SeccionSubgrupoListView.as_view(), name='seccionsubgrupo_list'),
    path('secciones/nuevo/', SeccionSubgrupoCreateView.as_view(), name='seccionsubgrupo_create'),
    path('secciones/<int:pk>/editar/', SeccionSubgrupoUpdateView.as_view(), name='seccionsubgrupo_update'),
    path('secciones/<int:pk>/eliminar/', SeccionSubgrupoDeleteView.as_view(), name='seccionsubgrupo_delete'),
    path('verificar-numero-identificacion/', views.verificar_numero_identificacion, name='verificar_numero_identificacion'),
    
    path('reportes/', views.menu_reportes, name='menu_reportes'),
    path('reportes/bm1/', views.pdf_bm1, name='pdf_bm1'),
    path('reportes/bm2/', views.pdf_bm2, name='pdf_bm2'),
    path('reportes/general/', views.pdf_bienes, name='pdf_bienes'),
    

    path('solicitudes/mantenimiento/crear/', views.crear_solicitud_mantenimiento, name='crear_solicitud_mantenimiento'),
    path('solicitudes/mantenimiento/procesar/<int:solicitud_id>/', views.procesar_solicitud_mantenimiento, name='procesar_solicitud_mantenimiento'),
    path('bienes/mantenimiento/', views.bienes_en_mantenimiento, name='bienes_en_mantenimiento'),

    path('bien/<int:bien_id>/ficha-tecnica-pdf/', views.ficha_tecnica_pdf, name='ficha_tecnica_pdf'),


    path('conceptos/', ConceptoDeMovimientoListView.as_view(), name='concepto_list'),
    path('conceptos/nuevo/', ConceptoDeMovimientoCreateView.as_view(), name='concepto_create'),
    path('conceptos/<int:pk>/editar/', ConceptoDeMovimientoUpdateView.as_view(), name='concepto_update'),
    path('conceptos/<int:pk>/eliminar/', ConceptoDeMovimientoDeleteView.as_view(), name='concepto_delete'),

    path('tipos-solicitud/', TiposDeSolicitudListView.as_view(), name='tipos_solicitud_list'),
    path('tipos-solicitud/crear/', TiposDeSolicitudCreateView.as_view(), name='tipos_solicitud_create'),
    path('tipos-solicitud/editar/<int:pk>/', TiposDeSolicitudUpdateView.as_view(), name='tipos_solicitud_edit'),
    path('tipos-solicitud/eliminar/<int:pk>/', TiposDeSolicitudDeleteView.as_view(), name='tipos_solicitud_delete'),

    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-reportes/', views.admin_reportes, name='admin_reportes'),


    path('reports/department-assets/<int:department_id>/', views.pdf_assets_by_department, name='pdf_assets_by_department'),



    path('get-subgrupos/', views.get_subgrupos, name='get_subgrupos'),
    path('get-secciones/', views.get_secciones, name='get_secciones'),

    path('api/usuarios/<int:usuario_id>/bienes/', views.get_bienes_usuario, name='api_bienes_usuario'),

    path('usuarios/', views.ListaUsuariosView.as_view(), name='lista_usuarios'),
    path('usuarios/<int:pk>/cambiar-estado/', views.CambiarEstadoUsuarioView.as_view(), name='cambiar_estado_usuario'),
    path('bienes/actualizar-concepto/<int:bien_id>/', views.actualizar_concepto_movimiento, name='actualizar_concepto_movimiento'),
    path('bienes/conceptos-movimiento/', views.obtener_conceptos_movimiento, name='obtener_conceptos_movimiento'),
    path('historial/<int:historial_id>/pdf/', views.historial_bien_pdf, name='historial_bien_pdf'),
    path('historial/bien/<int:bien_id>/', views.historial_bien, name='historial_bien'),
    path('historial/pdf/<int:historial_id>/', views.historial_bien_pdf, name='historial_bien_pdf'),

    path('get-subgrupos/', views.get_subgrupos, name='get_subgrupos'),
    path('get-secciones/', views.get_secciones, name='get_secciones'),
    path('verificar-numero-identificacion/', views.verificar_numero_identificacion, name='verificar_numero_identificacion'),
    path('reports/bm1/', views.pdf_bm1, name='pdf_bm1'),
    path('api/departments/', views.get_departments, name='get_departments'),
    path('gerencias/', views.UnidadOrganizacionalListView.as_view(), name='unidad_list'),
    path('gerencias/nueva/', views.UnidadOrganizacionalCreateView.as_view(), name='unidad_create'),
    path('gerencias/<int:pk>/editar/', views.UnidadOrganizacionalUpdateView.as_view(), name='unidad_update'),
    path('gerencias/<int:pk>/eliminar/', views.UnidadOrganizacionalDeleteView.as_view(), name='unidad_delete'),
    path('get-departamentos/', views.get_departamentos_por_gerencia, name='get_departamentos_por_gerencia'),

    path('generar_pdf_historial/<int:historial_id>/formulario/', views.generar_pdf_historial, name='formulario_pdf_historial'),
    path('guardar_descripcion_pdf/<int:historial_id>/', views.guardar_descripcion_pdf, name='guardar_descripcion_pdf'),
    path('generar_pdf_historial/<int:historial_id>/formulario/', views.generar_pdf_historial, name='formulario_pdf_historial'),
    path('guardar_descripcion_pdf/<int:historial_id>/', views.guardar_descripcion_pdf, name='guardar_descripcion_pdf'),
    path('historial_bien_pdf/<int:historial_id>/',views.historial_bien_pdf,name='historial_bien_pdf'),
    path('reports/get-locations/', views.get_locations, name='get_locations'),
    path('notificaciones/estandar/', views.usuario_estandar_notificaciones, name='usuario_notificaciones'),
    path('notificaciones/administrador/', views.admin_notificaciones, name='admin_bienes_notificaciones'),
    path('notificaciones/marcar-leida/<int:notificacion_id>/', views.marcar_como_leida, name='marcar_notificacion_leida'), 
    path('notificaciones/marcar-todas-leidas/', views.marcar_todas_como_leidas, name='marcar_todas_leidas'),    
    path('notificaciones/eliminar/<int:notificacion_id>/', views.eliminar_notificacion, name='eliminar_notificacion'),
    path('api/notificaciones/no-leidas-count/', views.get_unread_notifications_count, name='notificaciones_no_leidas_count'),


]





