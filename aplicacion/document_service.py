from django.template.loader import render_to_string
from django.http import HttpResponse
from weasyprint import HTML
import base64
import os
from django.conf import settings
from django.utils import timezone
from aplicacion.models import DescripcionPDF 

class DocumentService:
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

    def _get_base_context(self, historial):
        try:
            # Obtener la descripción PDF primero
            descripcion_pdf = DescripcionPDF.objects.filter(historial=historial).first()
            
            # Determinar origen y destino
            origen_nombre = None
            if historial.departamento_origen:
                origen_nombre = historial.departamento_origen.nombre_departamento
            elif historial.UnidadOrganizacional_origen:
                origen_nombre = historial.UnidadOrganizacional_origen.nombre

            destino_nombre = None
            if historial.departamento_destino:
                destino_nombre = historial.departamento_destino.nombre_departamento
            elif historial.UnidadOrganizacional_destino:
                destino_nombre = historial.UnidadOrganizacional_destino.nombre

            return {
                'logo_esomep': self.logos_base64.get('esomep', ''),
                'logo_portuguesa': self.logos_base64.get('portuguesa', ''),
                'fecha_actual': timezone.now().strftime("%d/%m/%Y"),
                'año_actual': timezone.now().year,
                'historial': historial,
                'bien': historial.bien_id,
                'descripcion': descripcion_pdf.descripcion if descripcion_pdf else '',
                'detalles': descripcion_pdf.detalles_adicionales if descripcion_pdf else {},
                'departamento_origen': historial.departamento_origen,
                'departamento_destino': historial.departamento_destino,
                'UnidadOrganizacional_origen': historial.UnidadOrganizacional_origen,
                'UnidadOrganizacional_destino': historial.UnidadOrganizacional_destino,
                'usuario': historial.usuario_id,
                'origen_nombre': origen_nombre,
                'destino_nombre': destino_nombre,
                'cantidad_afectada': historial.cantidad_afectada
            }
        except Exception as e:
            print(f"Error obteniendo contexto base: {str(e)}")
            raise
    def _render_pdf(self, template_name, context):
        html_string = render_to_string(template_name, context)
        html = HTML(string=html_string)
        pdf = html.write_pdf()
        
        response = HttpResponse(pdf, content_type='application/pdf')
        filename = f"{context['tipo_movimiento'].lower().replace(' ', '_')}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response

    def _generar_traslado_temporal(self, historial):
        try:
            context = self._get_base_context(historial)
            context['tipo_movimiento'] = 'TRASLADO TEMPORAL'
            
            # Obtener la descripción PDF
            descripcion_pdf = DescripcionPDF.objects.filter(historial=historial).first()
            
            if descripcion_pdf:
                context.update({
                    'descripcion': descripcion_pdf.descripcion,
                    'detalles': {
                        'motivo_traslado': descripcion_pdf.detalles_adicionales.get('motivo_traslado', ''),
                        'tiempo_estimado': descripcion_pdf.detalles_adicionales.get('tiempo_estimado', '')
                    } if descripcion_pdf.detalles_adicionales else {}
                })
            
            # Manejo de origen
            if historial.departamento_origen:
                context['departamento_origen'] = historial.departamento_origen
                context['origen_nombre'] = historial.departamento_origen.nombre_departamento
            elif historial.UnidadOrganizacional_origen:
                context['UnidadOrganizacional_origen'] = historial.UnidadOrganizacional_origen
                context['origen_nombre'] = historial.UnidadOrganizacional_origen.nombre

            # Manejo de destino
            if historial.departamento_destino:
                context['departamento_destino'] = historial.departamento_destino
                context['destino_nombre'] = historial.departamento_destino.nombre_departamento
            elif historial.UnidadOrganizacional_destino:
                context['UnidadOrganizacional_destino'] = historial.UnidadOrganizacional_destino
                context['destino_nombre'] = historial.UnidadOrganizacional_destino.nombre
            
            # Agregar información adicional importante
            context.update({
                'fecha_traslado': historial.fecha_evento.strftime("%d/%m/%Y"),
                'cantidad_afectada': historial.cantidad_afectada,
                'bien': historial.bien_id,
                'motivo': descripcion_pdf.detalles_adicionales.get('motivo_traslado', '') if descripcion_pdf and descripcion_pdf.detalles_adicionales else '',
                'tiempo_estimado': descripcion_pdf.detalles_adicionales.get('tiempo_estimado', '') if descripcion_pdf and descripcion_pdf.detalles_adicionales else ''
            })
            
            return self._render_pdf('actas/traslado_temporal.html', context)
            
        except Exception as e:
            print(f"Error generando PDF de traslado temporal: {str(e)}")
            raise

    def _generar_desincorporacion(self, historial):
        try:
            context = self._get_base_context(historial)
            context['tipo_movimiento'] = 'DESINCORPORACION'
            
            # Obtener la descripción PDF
            descripcion_pdf = DescripcionPDF.objects.filter(historial=historial).first()
            
            if descripcion_pdf:
                context.update({
                    'descripcion': descripcion_pdf.descripcion,
                    'detalles': descripcion_pdf.detalles_adicionales or {}
                })
            
            # Asegurar que se incluya el departamento o unidad de origen
            if historial.departamento_origen:
                context['origen_nombre'] = historial.departamento_origen.nombre_departamento
                context['departamento_origen'] = historial.departamento_origen
            elif historial.UnidadOrganizacional_origen:
                context['origen_nombre'] = historial.UnidadOrganizacional_origen.nombre
                context['UnidadOrganizacional_origen'] = historial.UnidadOrganizacional_origen
            
            context['fecha_desincorporacion'] = historial.fecha_evento.strftime("%d/%m/%Y")
            context['cantidad_afectada'] = historial.cantidad_afectada
            
            return self._render_pdf('actas/desincorporacion.html', context)
        except Exception as e:
            print(f"Error generando PDF de desincorporación: {str(e)}")
            raise

    def _generar_mantenimiento(self, historial):
        try:
            context = self._get_base_context(historial)
            context['tipo_movimiento'] = 'MANTENIMIENTO'
            
            # Obtener la descripción PDF
            descripcion_pdf = DescripcionPDF.objects.filter(historial=historial).first()
            
            if descripcion_pdf:
                context.update({
                    'descripcion': descripcion_pdf.descripcion,
                    'detalles': {
                        'tipo_mantenimiento': descripcion_pdf.detalles_adicionales.get('tipo_mantenimiento', ''),
                        'fallas_encontradas': descripcion_pdf.detalles_adicionales.get('fallas_encontradas', ''),
                        'solucion_aplicada': descripcion_pdf.detalles_adicionales.get('solucion_aplicada', '')
                    } if descripcion_pdf.detalles_adicionales else {}
                })
            
            # Asegurarse de que se incluya el departamento o unidad de origen
            if historial.departamento_origen:
                context['origen_nombre'] = historial.departamento_origen.nombre_departamento
            elif historial.UnidadOrganizacional_origen:
                context['origen_nombre'] = historial.UnidadOrganizacional_origen.nombre
            
            context['fecha_mantenimiento'] = historial.fecha_evento.strftime("%d/%m/%Y")
            
            return self._render_pdf('actas/mantenimiento.html', context)
        except Exception as e:
            print(f"Error generando PDF de mantenimiento: {str(e)}")
            raise

    def _generar_fin_mantenimiento(self, historial):
        context = self._get_base_context(historial)
        context['tipo_movimiento'] = 'FIN DE MANTENIMIENTO'
        descripcion_pdf = DescripcionPDF.objects.filter(historial=historial).first()
        
        if descripcion_pdf and descripcion_pdf.detalles_adicionales:
            detalles = descripcion_pdf.detalles_adicionales
            context.update({
                'trabajos_realizados': detalles.get('trabajos_realizados', ''),
                'estado_final': detalles.get('estado_final', ''),
                'recomendaciones': detalles.get('recomendaciones', ''),
                'tipo_mantenimiento': detalles.get('tipo_mantenimiento', ''),
                'descripcion': descripcion_pdf.descripcion
            })
        
        # Asegurarse de que se incluya el departamento o unidad de destino
        if historial.departamento_destino:
            context['destino_nombre'] = historial.departamento_destino.nombre_departamento
        elif historial.UnidadOrganizacional_destino:
            context['destino_nombre'] = historial.UnidadOrganizacional_destino.nombre
        else:
            context['destino_nombre'] = 'No especificado'

        context['fecha_evento'] = historial.fecha_evento.strftime("%d/%m/%Y")
        return self._render_pdf('actas/fin_mantenimiento.html', context)

    def _generar_asignacion(self, historial):
        context = self._get_base_context(historial)
        context['tipo_movimiento'] = 'ASIGNACION'
        descripcion_pdf = DescripcionPDF.objects.filter(historial=historial).first()
        
        # Obtener el bien y sus especificaciones
        bien = historial.bien_id
        context.update({
            'bien': bien,
            'especificaciones': bien.especificacion_set.all() if bien else [],
            'descripciones': bien.descripcion_set.all() if bien else []
        })
        
        # Determinar destino
        if historial.departamento_destino:
            context['destino_nombre'] = historial.departamento_destino.nombre_departamento
            context['departamento_destino'] = historial.departamento_destino
        elif historial.UnidadOrganizacional_destino:
            context['destino_nombre'] = historial.UnidadOrganizacional_destino.nombre
            context['UnidadOrganizacional_destino'] = historial.UnidadOrganizacional_destino
        
        # Actualizar el contexto con la descripción y detalles
        if descripcion_pdf:
            context.update({
                'descripcion': descripcion_pdf.descripcion,
                'detalles': {
                    'motivo_asignacion': descripcion_pdf.detalles_adicionales.get('motivo_asignacion', '') if descripcion_pdf.detalles_adicionales else ''
                }
            })
        
        context['cantidad_afectada'] = historial.cantidad_afectada
        context['fecha_asignacion'] = historial.fecha_evento.strftime("%d/%m/%Y")
        
        return self._render_pdf('actas/asignacion.html', context)

    def _generar_resguardo(self, historial):
        try:
            context = self._get_base_context(historial)
            context['tipo_movimiento'] = 'RESGUARDO'

            # Obtener la descripción PDF
            descripcion_pdf = DescripcionPDF.objects.filter(historial=historial).first()
            
            if descripcion_pdf:
                context.update({
                    'descripcion': descripcion_pdf.descripcion,
                    'detalles': descripcion_pdf.detalles_adicionales or {}
                })

            # Manejo de origen (Departamento y/o Unidad Organizacional)
            context.update(self._get_origen_info(historial))

            # Información adicional del resguardo
            context.update({
                'fecha_resguardo': historial.fecha_evento.strftime("%d/%m/%Y"),
                'cantidad_afectada': historial.cantidad_afectada
            })

            return self._render_pdf('actas/resguardo.html', context)
        except Exception as e:
            print(f"Error generando PDF de resguardo: {str(e)}")
            raise

    def _get_origen_info(self, historial):
        """
        Obtiene la información de origen del historial, manejando tanto
        departamento como unidad organizacional.
        """
        origen_info = {
            'departamento_origen': None,
            'UnidadOrganizacional_origen': None,
            'origen_nombre': '',
            'origen_completo': ''
        }

        # Manejo del departamento de origen
        if historial.departamento_origen:
            origen_info['departamento_origen'] = historial.departamento_origen
            origen_info['origen_nombre'] = historial.departamento_origen.nombre_departamento
            origen_info['origen_completo'] = f"Departamento: {historial.departamento_origen.nombre_departamento}"

        # Manejo de la unidad organizacional de origen
        if historial.UnidadOrganizacional_origen:
            origen_info['UnidadOrganizacional_origen'] = historial.UnidadOrganizacional_origen
            # Si ya hay un departamento, agregamos la unidad como información adicional
            if origen_info['departamento_origen']:
                origen_info['origen_nombre'] = (
                    f"{historial.UnidadOrganizacional_origen.nombre} - "
                    f"{historial.departamento_origen.nombre_departamento}"
                )
                origen_info['origen_completo'] = (
                    f"Unidad: {historial.UnidadOrganizacional_origen.nombre}\n"
                    f"Departamento: {historial.departamento_origen.nombre_departamento}"
                )
            else:
                origen_info['origen_nombre'] = historial.UnidadOrganizacional_origen.nombre
                origen_info['origen_completo'] = f"Unidad: {historial.UnidadOrganizacional_origen.nombre}"

        return origen_info

    def _generar_traslado_permanente(self, historial):
        try:
            context = self._get_base_context(historial)
            descripcion_pdf = DescripcionPDF.objects.filter(historial=historial).first()
            
            context.update({
                'tipo_movimiento': 'TRASLADO PERMANENTE',
                'bien': historial.bien_id,
                'cantidad_afectada': historial.cantidad_afectada,
                'fecha_evento': historial.fecha_evento.strftime("%d/%m/%Y"),
                'fecha_traslado': historial.fecha_evento.strftime("%d/%m/%Y"),
                'descripcion': descripcion_pdf.descripcion if descripcion_pdf else historial.descripcion,
            })

            # Manejo de origen
            if historial.departamento_origen:
                context['origen_nombre'] = historial.departamento_origen.nombre_departamento
                context['departamento_origen'] = historial.departamento_origen
            elif historial.UnidadOrganizacional_origen:
                context['origen_nombre'] = historial.UnidadOrganizacional_origen.nombre
                context['UnidadOrganizacional_origen'] = historial.UnidadOrganizacional_origen

            # Manejo de destino
            if historial.departamento_destino:
                context['destino_nombre'] = historial.departamento_destino.nombre_departamento
                context['departamento_destino'] = historial.departamento_destino
            elif historial.UnidadOrganizacional_destino:
                context['destino_nombre'] = historial.UnidadOrganizacional_destino.nombre
                context['UnidadOrganizacional_destino'] = historial.UnidadOrganizacional_destino

            # Agregar detalles adicionales si existen
            if descripcion_pdf and descripcion_pdf.detalles_adicionales:
                detalles = descripcion_pdf.detalles_adicionales
                context.update({
                    'motivo_traslado': detalles.get('motivo_traslado', ''),
                    'observaciones': detalles.get('observaciones', ''),
                    'detalles_adicionales': detalles
                })

            return self._render_pdf('actas/traslado_permanente.html', context)
        except Exception as e:
            print(f"Error generando PDF de traslado permanente: {str(e)}")
            raise