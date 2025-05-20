from django import template
register = template.Library()

@register.filter
def replace_underscores(value):
    """Turns 'cash_in' → 'Cash In' etc."""
    return str(value).replace('_', ' ').title()
