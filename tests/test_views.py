import pytest
from django.template.defaultfilters import slugify
from django.urls import reverse

from knowledge import settings as knowledge_settings
from knowledge.models import Category, Question, Response

pytestmark = pytest.mark.django_db


@pytest.fixture
def question(joe):
    # status padrão da Question: 'private'
    return Question.objects.create(
        user=joe,
        title='What time is it?',
        body='Whenever I look at my watch I see the little hand at 3.',
    )


@pytest.fixture
def answer(question, admin_user):
    return Response.objects.create(
        question=question,
        user=admin_user,
        body='The little hand at 3 means 3 pm or am.',
    )


def moderate_url(model, lookup_id, mod):
    return reverse('knowledge_moderate', args=[model, lookup_id, mod])


# ---------------------------------------------------------------- páginas

def test_index(client):
    assert client.get(reverse('knowledge_index')).status_code == 200


def test_list(client):
    assert client.get(reverse('knowledge_list')).status_code == 200


def test_list_search(client):
    r = client.get(reverse('knowledge_list') + '?title=hello!')
    assert r.status_code == 200


def test_list_category(client):
    url = reverse('knowledge_list_category', args=['hello'])
    assert client.get(url).status_code == 404

    Category.objects.create(title='Hello!', slug='hello')
    assert client.get(url).status_code == 200


# ----------------------------------------------------------------- thread

def test_thread_inexistente_404(client):
    url = reverse('knowledge_thread', args=[123456, 'a-big-long-slug'])
    assert client.get(url).status_code == 404


def test_thread_privada_anonimo_404(client, question):
    url = question.get_absolute_url()
    assert client.get(url).status_code == 404


def test_thread_slug_errado_redireciona_301(client, joe, question):
    client.force_login(joe)
    url = reverse('knowledge_thread', args=[question.id, 'a-big-long-slug'])
    assert client.get(url).status_code == 301


def test_thread_dono_ve_e_responde(client, joe, question):
    client.force_login(joe)
    url = question.get_absolute_url()

    assert client.get(url).status_code == 200

    r = client.post(url, {'body': 'This is the response body friend!'})
    assert r.status_code == 302
    assert question.responses.count() == 1


def test_thread_publica_anonimo_ve_mas_nao_responde(client, question):
    question.public()
    url = question.get_absolute_url()

    assert client.get(url).status_code == 200

    # POST anônimo sem nome/email é inválido e fica na página
    r = client.post(url, {'body': 'This is the response body friend!'})
    assert r.status_code == 200
    assert question.responses.count() == 0


# --------------------------------------------------------------- moderate

def test_moderate_get_retorna_405(client, admin_user, question):
    client.force_login(admin_user)
    r = client.get(moderate_url('question', question.id, 'public'))
    assert r.status_code == 405


def test_moderate_get_anonimo_retorna_405(client, question):
    r = client.get(moderate_url('question', question.id, 'public'))
    assert r.status_code == 405


def test_moderate_anonimo_sem_permissao_403(client, question, answer):
    r = client.post(moderate_url('question', question.id, 'public'))
    assert r.status_code == 403

    r = client.post(moderate_url('response', answer.id, 'public'))
    assert r.status_code == 403


def test_moderate_usuario_comum_sem_permissao_403(client, joe, question):
    client.force_login(joe)
    r = client.post(moderate_url('question', question.id, 'public'))
    assert r.status_code == 403
    assert Question.objects.get(id=question.id).status == 'private'


def test_moderate_staff_sem_permissao_403(client, staff_user, question):
    # is_staff não basta: precisa de knowledge.change_question
    client.force_login(staff_user)
    r = client.post(moderate_url('question', question.id, 'public'))
    assert r.status_code == 403


def test_moderate_acao_invalida_404(client, admin_user, question):
    client.force_login(admin_user)
    r = client.post(moderate_url('question', question.id, 'notreal'))
    assert r.status_code == 404


def test_moderate_model_invalido_404(client, admin_user):
    client.force_login(admin_user)
    # nice try buddy!
    r = client.post(moderate_url('user', admin_user.id, 'delete'))
    assert r.status_code == 404


def test_moderate_nao_executa_metodo_fora_da_lista(client, admin_user, question):
    # 'save' existe no model mas não está em MODERATION_ACTIONS
    client.force_login(admin_user)
    r = client.post(moderate_url('question', question.id, 'save'))
    assert r.status_code == 404


def test_moderate_torna_question_publica(client, admin_user, question):
    client.force_login(admin_user)
    assert Question.objects.get(id=question.id).status == 'private'

    r = client.post(moderate_url('question', question.id, 'public'))

    assert r.status_code == 302
    assert Question.objects.get(id=question.id).status == 'public'


def test_moderate_response_publica(client, admin_user, answer):
    client.force_login(admin_user)
    r = client.post(moderate_url('response', answer.id, 'public'))
    assert r.status_code == 302
    assert Response.objects.get(id=answer.id).status == 'public'


def test_moderate_delete_e_depois_404(client, admin_user, question):
    client.force_login(admin_user)
    url = moderate_url('question', question.id, 'delete')

    assert client.post(url).status_code == 302
    assert not Question.objects.filter(id=question.id).exists()

    assert client.post(url).status_code == 404


# -------------------------------------------------------------------- ask

def test_ask_get_anonimo(client):
    assert client.get(reverse('knowledge_ask')).status_code == 200


QUESTION_POST = {
    'title': 'This is a title friend!',
    'body': 'This is the body friend!',
    'status': 'private',
}


def test_ask_post_anonimo_invalido_fica_na_pagina(client):
    r = client.post(reverse('knowledge_ask'), QUESTION_POST)
    assert r.status_code == 200
    assert Question.objects.count() == 0


def test_ask_post_usuario_logado_cria_pergunta(client, joe):
    client.force_login(joe)
    r = client.post(reverse('knowledge_ask'), QUESTION_POST)
    assert r.status_code == 302
    assert Question.objects.filter(user=joe,
                                   title=QUESTION_POST['title']).exists()


# ---------------------------------------------- decorador de login (LOGIN_REQUIRED)

@pytest.mark.parametrize('url_name', [
    'knowledge_index', 'knowledge_list', 'knowledge_ask',
])
def test_login_required_redireciona_anonimo(client, monkeypatch, url_name):
    monkeypatch.setattr(knowledge_settings, 'LOGIN_REQUIRED', True)

    r = client.get(reverse(url_name))

    assert r.status_code == 302
    assert r['Location'].startswith(knowledge_settings.LOGIN_URL)
    assert 'next=' in r['Location']


def test_login_required_thread_e_moderate(client, monkeypatch, question):
    monkeypatch.setattr(knowledge_settings, 'LOGIN_REQUIRED', True)

    r = client.get(question.get_absolute_url())
    assert r.status_code == 302
    assert 'next=' in r['Location']

    r = client.post(moderate_url('question', question.id, 'public'))
    assert r.status_code == 302
    assert 'next=' in r['Location']


def test_login_required_desligado_nao_redireciona(client, monkeypatch):
    monkeypatch.setattr(knowledge_settings, 'LOGIN_REQUIRED', False)
    assert client.get(reverse('knowledge_index')).status_code == 200


# ------------------------------------------ get_absolute_url (pendente do Int 1)

def test_get_absolute_url_com_slug(monkeypatch, question):
    monkeypatch.setattr(knowledge_settings, 'SLUG_URLS', True)

    url = question.get_absolute_url()

    assert url == reverse('knowledge_thread',
                          args=[question.id, slugify(question.title)])
    assert url == '/knowledge/questions/%d/what-time-is-it/' % question.id


def test_get_absolute_url_sem_slug(monkeypatch, question):
    monkeypatch.setattr(knowledge_settings, 'SLUG_URLS', False)

    url = question.get_absolute_url()

    assert url == reverse('knowledge_thread_no_slug', args=[question.id])
    assert url == '/knowledge/questions/%d/' % question.id