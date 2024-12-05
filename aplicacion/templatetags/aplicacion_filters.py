from django import template

register = template.Library()

@register.filter
def call_method(obj, method_name):
    method = getattr(obj, method_name)
    if callable(method):
        return method
    return None

@register.simple_tag
def call_method_with_arg(obj, method_name, arg):
    method = getattr(obj, method_name)
    if callable(method):
        return method(arg)
    return None

@register.filter(name='replace')
def replace(value, args):
    """
    Reemplaza una subcadena por otra en el valor proporcionado.

    Uso en la plantilla: {{ value|replace:"a|b" }}
    Esto reemplaza todas las ocurrencias de "a" por "b".
    """
    try:
        old, new = args.split('|')
        return value.replace(old, new)
    except ValueError:
        # Si los argumentos no son correctos, retornar el valor original
        return value
    

from django import template

register = template.Library()

@register.filter(name='add_class')
def add_class(value, arg):
    return value.as_widget(attrs={'class': arg})