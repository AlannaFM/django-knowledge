""" testes dos templatetags (knowledge_tags) e dos templates do app
portados de legacy_tests/mock/tests/templatetags.py, mais testes novos
para o filtro markdown e para o carregamento de todos os templates """

from pathlib import Path

import pytest
from django.template import Context, Template
from django.template.loader import get_template
from django.test import RequestFactory

from knowledge.templatetags.knowledge_tags import (
    get_gravatar,
    markdown_filter,
    page_query,
)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / 'knowledge' / 'templates'
TODOS_OS_TEMPLATES = sorted(  # lista com o caminho de cada template do app
    p.relative_to(TEMPLATES_DIR).as_posix()
    for p in TEMPLATES_DIR.rglob('*')
    if p.is_file()
)

# legado

def test_gravatar():  # gera a url da foto de perfil a partir do e-mail
    assert get_gravatar('bryan@bryanhelmig.com', 60, 'g', 'retro') == (
        'https://secure.gravatar.com/avatar/'
        '883955996dbb79f38d8814dbfb336885.jpg?s=60&amp;r=g&amp;d=retro'
    )


def test_page_query_substitui_pagina_existente():
    request = RequestFactory().get('/faker/?something=extra&page=123')
    assert page_query(request, 666) == 'something=extra&amp;page=666'

def test_page_query_adiciona_pagina():  # separado em dois testes com nomes que explicam o caso, se um falhar já se sabe qual
    request = RequestFactory().get('/faker/?something=extra')
    assert page_query(request, 666) == 'something=extra&amp;page=666'

# markdown

def test_markdown_converte_negrito():
    assert markdown_filter('**oi**') == '<p><strong>oi</strong></p>'


@pytest.mark.parametrize('vazio', [None, ''])  # roda o teste uma vez com None e outra com ''
def test_markdown_aceita_vazio(vazio):  # pergunta sem corpo não pode quebrar a página
    assert markdown_filter(vazio) == ''


def test_markdown_no_template_com_striptags_remove_html():
    """ os templates usam |striptags|markdown, então o <script> não pode passar """
    template = Template('{% load knowledge_tags %}{{ texto|striptags|markdown }}')
    html = template.render(Context({'texto': '<script>alert(1)</script>**oi**'}))
    assert '<script>' not in html  # proteção contra xss
    assert '<strong>oi</strong>' in html

# templates

def test_existem_templates_para_testar():  # evita que o teste abaixo passe sem testar nada se a pasta mudar
    assert len(TODOS_OS_TEMPLATES) > 0


@pytest.mark.parametrize('nome', TODOS_OS_TEMPLATES)  # roda uma vez para cada um dos 15 templates
def test_template_carrega_sem_erro(nome):
    """ garante que nenhum template usa tags removidas do django
    ({% load url from future %}, {% load markup %}) """
    get_template(nome)