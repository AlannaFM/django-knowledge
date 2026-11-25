""" testes dos formulários de pergunta e de resposta
portados de legacy_tests/mock/tests/forms.py, usando a api nova
(get_question_form_class e get_response_form_class); os testes do final
garantem que as funções antigas deprecadas funcionam até o pr 4 """

import pytest
from django.contrib.auth.models import AnonymousUser

import knowledge.settings
from knowledge.forms import (
    AnonymousQuestionForm,
    AnonymousResponseForm,
    AuthenticatedQuestionForm,
    AuthenticatedResponseForm,
    QuestionForm,
    ResponseForm,
    get_question_form_class,
    get_response_form_class,
)
from knowledge.models import Question

QUESTION_POST = {  # dados de uma pergunta, como se viessem do formulário da página
    'title': 'This is a title friend!',
    'body': 'This is the body friend!',
}


@pytest.fixture
def anon():  # usuário não logado
    return AnonymousUser()


@pytest.fixture
def question(joe):  # pergunta feita pelo joe, igual ao setUp do legado
    return Question.objects.create(
        user=joe,
        title='What time is it?',
        body='Whenever I look at my watch I see the little hand at 3.',
    )

# quem recebe qual formulário

def test_question_form_display(anon, joe, admin_user):
    assert get_question_form_class(anon) is None  # padrão: KNOWLEDGE_ALLOW_ANONYMOUS = False
    assert get_question_form_class(joe) is AuthenticatedQuestionForm
    assert get_question_form_class(admin_user) is AuthenticatedQuestionForm


def test_response_form_display(anon, joe, bob, admin_user, question):
    assert get_response_form_class(anon, question) is None
    assert get_response_form_class(joe, question) is AuthenticatedResponseForm
    assert get_response_form_class(admin_user, question) is AuthenticatedResponseForm
    assert get_response_form_class(bob, question) is AuthenticatedResponseForm  # com FREE_RESPONSE quem não perguntou também responde


def test_pergunta_trancada_nao_aceita_resposta(admin_user, question):
    question.lock()
    assert get_response_form_class(admin_user, question) is None  # nem a equipe responde


def test_anonimo_permitido_recebe_formularios_anonimos(monkeypatch, anon, question):
    monkeypatch.setattr(knowledge.settings, 'ALLOW_ANONYMOUS', True)  # monkeypatch desfaz a troca no fim do teste
    assert get_question_form_class(anon) is AnonymousQuestionForm
    assert get_response_form_class(anon, question) is AnonymousResponseForm

# salvar

def test_form_saving(joe, question):
    form = AuthenticatedQuestionForm({**QUESTION_POST, 'status': 'private'}, user=joe)
    assert form.is_valid(), form.errors  # se falhar, mostra os erros do formulário

    saved = form.save()
    assert saved.status == 'private'
    assert saved.name is None
    assert saved.email is None
    assert saved.title == 'This is a title friend!'
    assert saved.body == 'This is the body friend!'
    assert saved.user == joe  # o user vem do construtor, não do formulário

    form = AuthenticatedResponseForm(
        {'body': 'This is the response body friend!'},
        user=joe, question=saved,
    )
    assert form.is_valid(), form.errors

    response = form.save()
    assert response.status == 'inherit'  # quem não é da equipe não escolhe status, fica o padrão
    assert response.name is None
    assert response.email is None
    assert response.body == 'This is the response body friend!'
    assert response.user == joe
    assert response.question == saved


def test_save_sem_commit_nao_grava(joe):
    form = AuthenticatedQuestionForm({**QUESTION_POST, 'status': 'public'}, user=joe)
    assert form.is_valid()

    unsaved = form.save(commit=False)
    assert unsaved.pk is None  # não foi para o banco
    assert unsaved.user == joe  # mas o user já foi preenchido


def test_campo_user_nao_aparece_no_formulario(joe, question):
    assert 'user' not in AuthenticatedQuestionForm(user=joe).fields  # no legado era um campo escondido
    assert 'user' not in AuthenticatedResponseForm(user=joe, question=question).fields
    assert 'question' not in AuthenticatedResponseForm(user=joe, question=question).fields

# status

def test_form_question_status(joe, admin_user):
    assert 'status' in AuthenticatedQuestionForm(user=joe).fields

    internal = {**QUESTION_POST, 'status': 'internal'}
    assert not AuthenticatedQuestionForm(internal, user=joe).is_valid()  # internal só para a equipe
    assert AuthenticatedQuestionForm(internal, user=admin_user).is_valid()

    public = {**QUESTION_POST, 'status': 'public'}
    saved = AuthenticatedQuestionForm(public, user=joe).save()
    assert saved.status == 'public'


def test_status_da_resposta_so_para_equipe(joe, admin_user, question):
    assert 'status' not in AuthenticatedResponseForm(user=joe, question=question).fields
    assert 'status' in AuthenticatedResponseForm(user=admin_user, question=question).fields

# campos obrigatórios e alertas

def test_campos_obrigatorios(joe):
    form = AuthenticatedQuestionForm({'title': 'Só o título'}, user=joe)
    assert not form.is_valid()
    assert 'body' in form.errors
    assert 'status' in form.errors


def test_campo_alert_depende_da_setting(monkeypatch, joe):
    monkeypatch.setattr(knowledge.settings, 'ALERTS', False)
    assert 'alert' not in AuthenticatedQuestionForm(user=joe).fields

    monkeypatch.setattr(knowledge.settings, 'ALERTS', True)
    form = AuthenticatedQuestionForm(user=joe)
    assert 'alert' in form.fields
    assert form.fields['alert'].required is False  # alert continua opcional

# honeypot

def test_honeypot_so_nos_formularios_anonimos(anon, joe, question):
    assert 'phone_number' in AnonymousQuestionForm(user=anon).fields
    assert 'phone_number' in AnonymousResponseForm(user=anon, question=question).fields
    assert 'phone_number' not in AuthenticatedQuestionForm(user=joe).fields
    assert 'phone_number' not in AuthenticatedResponseForm(user=joe, question=question).fields


def test_is_spam(anon, joe):
    anonymous_post = {**QUESTION_POST, 'name': 'Test Guy', 'email': 'anon@example.com'}

    assert not AnonymousQuestionForm(anonymous_post, user=anon).is_spam
    assert AnonymousQuestionForm({**anonymous_post, 'phone_number': '123'}, user=anon).is_spam  # robô preencheu o campo escondido
    assert AuthenticatedQuestionForm({**QUESTION_POST, 'phone_number': '123'}, user=joe).is_spam is False  # logado nunca é spam

# funções antigas (deprecadas)

def test_question_form_antiga_ainda_funciona(anon, joe):
    with pytest.deprecated_call():  # confere que o aviso de deprecada aparece
        assert QuestionForm(anon) is None
    with pytest.deprecated_call():
        assert isinstance(QuestionForm(joe), AuthenticatedQuestionForm)


def test_response_form_antiga_ainda_funciona(anon, joe, question):
    with pytest.deprecated_call():
        assert ResponseForm(anon, question) is None
    with pytest.deprecated_call():
        form = ResponseForm(joe, question, {'body': 'Resposta'})
    assert form.is_valid()
    assert form.save().question == question