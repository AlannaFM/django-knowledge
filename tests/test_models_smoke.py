import pytest
from knowledge.models import Question


@pytest.mark.django_db
def test_cria_question_minima():
    """verifica que uma pergunta pode ser criada apenas com o título"""

    q = Question.objects.create(
        title="Como instalar o django-knowledge?",
        status="public",
    )
    assert q.pk is not None
    assert q.title == "Como instalar o django-knowledge?"
    assert str(q) == q.title


@pytest.mark.django_db
def test_question_status_padrao():
    """o status padrão de uma pergunta deve ser private"""

    q = Question.objects.create(title="Pergunta de teste")
    assert q.status == "private"
