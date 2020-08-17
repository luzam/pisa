#! /usr/bin/python
# -*- encoding: utf-8 -*-

from __future__ import absolute_import
from django.template.loader import get_template
from django.template import Context
from django.http import HttpResponse
import six
from sx.pisa3 import pisaDocument
import cgi

def render_to_pdf(template_src, context_dict):
    '''
    Renderiza el template con el contexto.
    Envía al cliente la Respuesta HTTP del contenido PDF para
    el template renderizado.
    '''
    template = get_template(template_src)
    context = Context(context_dict)
    html  = template.render(context)
    result = six.moves.StringIO()
    pdf = pisaDocument(six.moves.StringIO(html.encode("ISO-8859-1")), result)
    if not pdf.err:
        return HttpResponse(result.getvalue(), mimetype='application/pdf')
    return HttpResponse('We had some errors<pre>%s</pre>' % cgi.escape(html))
