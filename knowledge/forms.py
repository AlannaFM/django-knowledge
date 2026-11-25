""" formulários de pergunta e de resposta do django-knowledge
...
get_response_form_class """

import warnings  # usado para avisar que as funções antigas estão deprecadas

from typing import Any, Optional

from django import forms
...

from typing import Any, Optional  

from django import forms
from django.utils.translation import gettext_lazy as _  # era ugettext_lazy removido no django 4 (o u vinha do unicode do python 2)

from knowledge import settings
from knowledge.models import Question, Response

OPTIONAL_FIELDS = ('alert', 'phone_number') 


# base comum

class _KnowledgeModelForm(forms.ModelForm):
    """ comportamento comum aos formulários de pergunta e de resposta """

    def __init__(self, *args: Any, user: Any, **kwargs: Any) -> None: 
        self.user = user  # no legado o user era um campo escondido no formulário agora vem pelo construtor
        super().__init__(*args, **kwargs) 

        if not settings.ALERTS:
            self.fields.pop('alert', None) 

        for name, field in self.fields.items():
            if name not in OPTIONAL_FIELDS:
                field.required = True

    @property  # permite usar form.is_spam sem parênteses
    def is_spam(self) -> bool:
        """ só os formulários anônimos têm honeypot, os outros nunca são spam """
        return False

    def fill_instance(self, instance: Any) -> None:
        """ preenche campos que não vêm do formulário """
        if self.user.is_authenticated:
            instance.user = self.user  

    def save(self, commit: bool = True) -> Any:
        instance = super().save(commit=False) 
        self.fill_instance(instance)  
        if commit:
            instance.save()  
            self.save_m2m()  
        return instance


class _HoneypotMixin(forms.Form):
    """ campo armadilha para robôs de spam, o css do app esconde o campo
    (.field-phone_number), então uma pessoa nunca preenche """
    phone_number = forms.CharField(required=False)

    @property
    def is_spam(self) -> bool:
        return bool(self.data.get('phone_number'))  # se veio preenchido foi um robô

# perguntas

class BaseQuestionForm(_KnowledgeModelForm):
    class Meta:  # o meta diz ao django qual model e quais campos o formulário usa
        model = Question
        fields = ['title', 'body', 'alert']


class AuthenticatedQuestionForm(BaseQuestionForm):
    class Meta(BaseQuestionForm.Meta):  # herda o meta da base e so troca a lista de campos
        fields = ['title', 'body', 'status', 'alert']  # no legado era selected_fields montado com if

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        status = self.fields.get('status')
        if status is not None and not self.user.is_staff:  # só a equipe pode marcar uma pergunta como interna
            status.choices = [  
                choice for choice in status.choices if choice[0] != 'internal'  
            ]


class AnonymousQuestionForm(_HoneypotMixin, BaseQuestionForm):  
    class Meta(BaseQuestionForm.Meta):
        fields = ['name', 'email', 'title', 'body', 'alert']  


def get_question_form_class(user: Any) -> Optional[type]:
    """ devolve a classe de formulário de pergunta para este usuário,
    ou None se ele não pode perguntar """
    if user.is_anonymous:
        return AnonymousQuestionForm if settings.ALLOW_ANONYMOUS else None 
    return AuthenticatedQuestionForm  


# respostas

class BaseResponseForm(_KnowledgeModelForm):
    class Meta:
        model = Response
        fields = ['body', 'alert']

    def __init__(self, *args: Any, question: Question, **kwargs: Any) -> None:  # além do user resposta precisa saber de qual pergunta é
        self.question = question
        super().__init__(*args, **kwargs)  # o user é tratado na classe base

    def fill_instance(self, instance: Any) -> None:
        super().fill_instance(instance)  
        instance.question = self.question  # substitui o clean_question do legado


class AuthenticatedResponseForm(BaseResponseForm):
    class Meta(BaseResponseForm.Meta):
        fields = ['body', 'status', 'alert']

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        if not self.user.is_staff:  # so a equipe escolhe o status de uma resposta
            self.fields.pop('status', None)  # para os outros, o campo some e a resposta fica com o padrão 'inherit'


class AnonymousResponseForm(_HoneypotMixin, BaseResponseForm):
    class Meta(BaseResponseForm.Meta):
        fields = ['name', 'email', 'body', 'alert']


def get_response_form_class(user: Any, question: Question) -> Optional[type]:
    """ devolve a classe de formulário de resposta para este usuário e esta
    pergunta, ou None se ele não pode responder """
    if question.locked:  # pergunta trancada não aceita resposta, nem da equipe
        return None

    if not settings.FREE_RESPONSE and not \
            (user.is_staff or question.user == user):  # sem free_response so a equipe e o dono da pergunta respondem
        return None

    if user.is_anonymous:
        return AnonymousResponseForm if settings.ALLOW_ANONYMOUS else None
    return AuthenticatedResponseForm

# deprecadas

def QuestionForm(user: Any, *args: Any, **kwargs: Any) -> Optional[forms.ModelForm]:
    """ deprecada: use get_question_form_class(user), sai no pr 4 """
    warnings.warn(  # mostra um aviso para quem ainda usa a função antiga
        'QuestionForm() está deprecada; use get_question_form_class(user).',
        DeprecationWarning, stacklevel=2,  # stacklevel=2 faz o aviso apontar para quem chamou, não para esta linha
    )
    form_class = get_question_form_class(user)  # a lógica agora fica só nas classes novas
    if form_class is None:
        return None
    return form_class(*args, user=user, **kwargs)  # mesma assinatura de antes, então as views antigas continuam funcionando


def ResponseForm(user: Any, question: Question,
                 *args: Any, **kwargs: Any) -> Optional[forms.ModelForm]:
    """ deprecada: use get_response_form_class(user, question), sai no pr 4 """
    warnings.warn(
        'ResponseForm() está deprecada; use get_response_form_class(user, question).',
        DeprecationWarning, stacklevel=2,
    )
    form_class = get_response_form_class(user, question)
    if form_class is None:
        return None
    return form_class(*args, user=user, question=question, **kwargs)