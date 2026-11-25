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


__todo__ = """
This is serious badness. Really? Functions masquerading as
clases? Lame. This should be fixed. Sorry.
                                                    ~bryan
"""


def QuestionForm(user, *args, **kwargs):
    """
    Build and return the appropriate form depending
    on the status of the passed in user.
    """

    if user.is_anonymous:  # era is_anonymous() virou propriedade no django atual e se usa sem parênteses
        if not settings.ALLOW_ANONYMOUS:
            return None
        else:
            selected_fields = ['name', 'email', 'title', 'body']
    else:
        selected_fields = ['user', 'title', 'body', 'status']

    if settings.ALERTS:
        selected_fields += ['alert']

    class _QuestionForm(forms.ModelForm):
        def __init__(self, *args, **kwargs):
            super(_QuestionForm, self).__init__(*args, **kwargs)

            for key in self.fields:
                if not key in OPTIONAL_FIELDS:
                    self.fields[key].required = True

            # hide the internal status for non-staff
            qf = self.fields.get('status', None)
            if qf and not user.is_staff:
                choices = list(qf.choices)
                choices.remove(('internal', _('Internal')))
                qf.choices = choices

            # a bit of a hack...
            # hide a field, and use clean to force
            # a specific value of ours
            for key in ['user']:
                qf = self.fields.get(key, None)
                if qf:
                    qf.widget = qf.hidden_widget()
                    qf.required = False

        # honey pot!
        phone_number = forms.CharField(required=False)

        def clean_user(self):
            return user

        class Meta:
            model = Question
            fields = selected_fields

    return _QuestionForm(*args, **kwargs)


def ResponseForm(user, question, *args, **kwargs):
    """
    Build and return the appropriate form depending
    on the status of the passed in user and question.
    """

    if question.locked:
        return None

    if not settings.FREE_RESPONSE and not \
            (user.is_staff or question.user == user):
        return None

    if user.is_anonymous:  # era is_anonymous() com parênteses da typerror : 'bool' object is not callable
        if not settings.ALLOW_ANONYMOUS:
            return None
        else:
            selected_fields = ['name', 'email']
    else:
        selected_fields = ['user']

    selected_fields += ['body', 'question']

    if user.is_staff:
        selected_fields += ['status']

    if settings.ALERTS:
        selected_fields += ['alert']

    class _ResponseForm(forms.ModelForm):
        def __init__(self, *args, **kwargs):
            super(_ResponseForm, self).__init__(*args, **kwargs)

            for key in self.fields:
                if not key in OPTIONAL_FIELDS:
                    self.fields[key].required = True

            # a bit of a hack...
            for key in ['user', 'question']:
                qf = self.fields.get(key, None)
                if qf:
                    qf.widget = qf.hidden_widget()
                    qf.required = False

        # honey pot!
        phone_number = forms.CharField(required=False)

        def clean_user(self):
            return user

        def clean_question(self):
            return question

        class Meta:
            model = Response
            fields = selected_fields

    return _ResponseForm(*args, **kwargs)