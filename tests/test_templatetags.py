
""" testes dos templatetags (knowledge_tags) e dos templates do app
portados de legacy_tests/mock/tests/templatetags.py """

from django.test import RequestFactory

from knowledge.templatetags.knowledge_tags import (
    get_gravatar,
    page_query,
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