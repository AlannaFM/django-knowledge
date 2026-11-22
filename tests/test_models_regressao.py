from knowledge.models import Question, Response


def test_get_name_sem_nome_e_sem_usuario_retorna_anonymous(db):
    """antes: AttributeError ('NoneType' has no attribute 'strip')."""
    pergunta = Question.objects.create(title="Titulo", body="Corpo")

    assert str(pergunta.get_name()) == "Anonymous"


def test_clear_accepted_funciona_com_usuario_solicitante(db, joe, bob):
    """antes: AttributeError ('list' has no attribute 'update')."""
    pergunta = Question.objects.create(user=joe, title="Duvida", body="Texto")
    resposta = Response.objects.create(
        user=bob, question=pergunta, body="Resposta", accepted=True)
    pergunta._requesting_user = joe

    pergunta.clear_accepted()

    resposta.refresh_from_db()
    assert resposta.accepted is False