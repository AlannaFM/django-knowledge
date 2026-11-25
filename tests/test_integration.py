import pytest
from django.urls import reverse

from knowledge import settings as knowledge_settings
from knowledge.models import Question, Response

PERGUNTA_ANONIMA = {
    'name': 'Ana',
    'email': 'ana@example.com',
    'title': 'Como funciona?',
    'body': 'Quero entender o fluxo.',
}

PERGUNTA_LOGADO = {
    'title': 'Pergunta de usuario logado',
    'body': 'Corpo da pergunta.',
    'status': 'private',
}


def test_anonimo_cria_pergunta(client, db, monkeypatch):
    monkeypatch.setattr(knowledge_settings, 'ALLOW_ANONYMOUS', True)

    resp = client.post(reverse('knowledge_ask'), PERGUNTA_ANONIMA)

    assert resp.status_code == 302
    pergunta = Question.objects.get()
    assert pergunta.user is None
    assert pergunta.name == 'Ana'


def test_logado_cria_pergunta_ligada_ao_usuario(client, db, joe):
    client.force_login(joe)

    resp = client.post(reverse('knowledge_ask'), PERGUNTA_LOGADO)

    assert resp.status_code == 302
    pergunta = Question.objects.get()
    assert pergunta.user == joe


def test_honeypot_descarta_pergunta_de_robo(client, db, monkeypatch):
    monkeypatch.setattr(knowledge_settings, 'ALLOW_ANONYMOUS', True)
    dados = dict(PERGUNTA_ANONIMA, phone_number='11999999999')

    resp = client.post(reverse('knowledge_ask'), dados)

    assert resp.status_code == 302
    assert Question.objects.count() == 0


def test_anonimo_nao_pergunta_com_allow_anonymous_desligado(client, db, monkeypatch):
    monkeypatch.setattr(knowledge_settings, 'ALLOW_ANONYMOUS', False)

    resp = client.post(reverse('knowledge_ask'), PERGUNTA_ANONIMA)

    assert resp.status_code == 200
    assert Question.objects.count() == 0


def test_dono_responde_a_propria_pergunta(client, db, joe):
    client.force_login(joe)
    client.post(reverse('knowledge_ask'), PERGUNTA_LOGADO)
    pergunta = Question.objects.get()

    resp = client.post(pergunta.get_absolute_url(), {'body': 'Minha resposta.'})

    assert resp.status_code == 302
    resposta = Response.objects.get()
    assert resposta.user == joe
    assert resposta.question == pergunta


def test_fluxo_privado_moderado_publico(client, db, joe, admin_user):
    # 1. logado pergunta (fica privada)
    client.force_login(joe)
    client.post(reverse('knowledge_ask'), PERGUNTA_LOGADO)
    pergunta = Question.objects.get()
    url = pergunta.get_absolute_url()
    client.logout()

    # 2. anonimo nao ve
    assert client.get(url).status_code == 404

    # 3. admin modera para publica
    client.force_login(admin_user)
    moderar = reverse('knowledge_moderate', args=['question', pergunta.id, 'public'])
    assert client.post(moderar).status_code == 302
    client.logout()

    # 4. anonimo agora ve
    assert client.get(url).status_code == 200