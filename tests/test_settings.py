""" testes de como as settings KNOWLEDGE_* mudam os formulários
portados de legacy_tests/mock/tests/settings.py; no legado cada teste
trocava a setting com atribuição direta e desfazia no fim, aqui usamos
monkeypatch, que desfaz sozinho mesmo se o teste falhar no meio
o test_SLUG_URLS do legado testa views, por isso fica em tests/test_views.py """

import pytest
from django.contrib.auth.models import AnonymousUser

import knowledge.settings
from knowledge.forms import get_question_form_class, get_response_form_class
from knowledge.models import Question

QUESTION_POST = {
    'title': 'This is a title friend!',
    'body': 'This is the body friend!',
}


@pytest.fixture
def anon():  # usuário não logado
    return AnonymousUser()


@pytest.fixture
def question(joe):  
    return Question.objects.create(
        user=joe,
        title='What time is it?',
        body='Whenever I look at my watch I see the little hand at 3.',
    )


def test_ALLOW_ANONYMOUS_desligado_por_padrao(anon, question):
    assert knowledge.settings.ALLOW_ANONYMOUS is False
    assert get_question_form_class(anon) is None
    assert get_response_form_class(anon, question) is None


def test_ALLOW_ANONYMOUS_ligado(monkeypatch, anon, question):
    monkeypatch.setattr(knowledge.settings, 'ALLOW_ANONYMOUS', True)  # no legado era settings.ALLOW_ANONYMOUS = not settings.ALLOW_ANONYMOUS

    assert get_response_form_class(anon, question) is not None

    form_class = get_question_form_class(anon)
    assert form_class is not None
    assert 'status' not in form_class(user=anon).fields  # anônimo não escolhe status

    assert not form_class(QUESTION_POST, user=anon).is_valid()  # sem nome e e-mail é inválido

    form = form_class(
        {**QUESTION_POST, 'name': 'Test Guy', 'email': 'anonymous@example.com'},
        user=anon,
    )
    assert form.is_valid(), form.errors

    saved = form.save()
    assert not saved.user  # pergunta anônima não tem usuário
    assert saved.name == 'Test Guy'
    assert saved.email == 'anonymous@example.com'
    assert saved.status == 'public'  # e é pública por padrão


def test_AUTO_PUBLICIZE(monkeypatch, joe):
    assert knowledge.settings.AUTO_PUBLICIZE is False

    post = {**QUESTION_POST, 'status': 'private'}
    form_class = get_question_form_class(joe)

    assert form_class(post, user=joe).save().status == 'private'

    monkeypatch.setattr(knowledge.settings, 'AUTO_PUBLICIZE', True)
    assert form_class(post, user=joe).save().status == 'public'  # com AUTO_PUBLICIZE toda pergunta nova vira pública


def test_FREE_RESPONSE(monkeypatch, anon, joe, bob, admin_user, question):
    assert knowledge.settings.FREE_RESPONSE is True

    assert get_response_form_class(anon, question) is None  
    assert get_response_form_class(bob, question) is not None
    assert get_response_form_class(joe, question) is not None
    assert get_response_form_class(admin_user, question) is not None

    monkeypatch.setattr(knowledge.settings, 'FREE_RESPONSE', False)

    assert get_response_form_class(anon, question) is None
    assert get_response_form_class(bob, question) is None  # agora o bob não pode mais responder
    assert get_response_form_class(joe, question) is not None  # o dono continua podendo
    assert get_response_form_class(admin_user, question) is not None  # e a equipe também