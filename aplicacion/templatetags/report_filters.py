from django import template

register = template.Library()

@register.filter
def sum_incorporaciones(movimientos):
    """Suma todas las incorporaciones"""
    total = 0
    for mov in movimientos:
        if mov.id_tipos_de_evento.nombre in ['INCORPORACION', 'ASIGNACION']:
            total += mov.bien_id.incorporacion or 0
    return total

@register.filter
def sum_desincorporaciones(movimientos):
    """Suma todas las desincorporaciones"""
    total = 0
    for mov in movimientos:
        if mov.id_tipos_de_evento.nombre == 'DESINCORPORACION':
            total += mov.bien_id.incorporacion or 0
    return total