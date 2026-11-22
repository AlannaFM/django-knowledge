from unittest.mock import patch

from django.test import TestCase
from django.contrib.auth.models import User, AnonymousUser
from django.contrib.sites.models import Site
from django.conf import settings as django_settings
from django.core import mail

from knowledge.models import Question, Response
from knowledge import settings


class SignalsTestCase(TestCase):
    def setUp(self):
        # Patch django.template.loader.render_to_string para evitar chamar get_absolute_url  e tags de marcação ausentes
        self.render_patcher = patch(
            'django.template.loader.render_to_string',
            return_value='Notification content',
        )
        self.mock_render = self.render_patcher.start()

        # Garante que o site existe para Site.objects.get_current()
        Site.objects.get_or_create(
            id=django_settings.SITE_ID,
            defaults={'domain': 'example.com', 'name': 'example.com'}
        )

        self.initial_alerts = settings.ALERTS
        settings.ALERTS = True

        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'secret')
        self.joe = User.objects.create_user('joe', 'joedirt@example.com', 'secret')
        self.bob = User.objects.create_user('bob', 'bob@example.com', 'secret')
        self.anon = AnonymousUser()

        self.joe.first_name = 'Joe'
        self.joe.last_name = 'Dirt'
        self.joe.save()

        # joe faz uma pergunta com alert=True
        self.question = Question.objects.create(
            user=self.joe,
            title='What time is it?',
            body='Whenever I look at my watch I see the little hand at 3 and the big hand at 7.',
            alert=True,
        )

        # admin responde com alert=True
        self.response = Response.objects.create(
            question=self.question,
            user=self.admin,
            body='The little hand at 3 means 3 pm or am, the big hand at 7 means 3:35 am or pm.',
            alert=True,
        )

        mail.outbox = []  # zera a caixa de correio após setUp

    def tearDown(self):
        self.render_patcher.stop()
        mail.outbox = []
        settings.ALERTS = self.initial_alerts
        super().tearDown()

    def test_sending_alerts_normal(self):
        """
        Uma pergunta por joe, uma resposta por admin: bob responde via ORM.
        Os alertas devem ir para joe (dono da pergunta) e admin (respondedor anterior)
        """
        mail.outbox = []

        response = Response.objects.create(
            question=self.question,
            user=self.bob,
            body='This is the response body from bob!',
            alert=True,
        )

        self.assertTrue(response.alert)
        self.assertEqual(len(mail.outbox), 2)  # um para joe, um para admin
        recipients = [m.to[0] for m in mail.outbox]
        self.assertIn(self.joe.email, recipients)
        self.assertIn(self.admin.email, recipients)

    def test_sending_alerts_dedupe(self):
        """
        Uma pergunta de joe, duas respostas do admin: bob responde
        Admin deve receber apenas um email, não duplicado.
        """
        # Admin adiciona outra resposta
        Response.objects.create(
            question=self.question,
            user=self.admin,
            body='Another response from admin!',
            status='inherit',
            alert=True,
        )

        mail.outbox = []  # reset

        # Bob responde
        response = Response.objects.create(
            question=self.question,
            user=self.bob,
            body='Response from bob!',
            alert=True,
        )

        self.assertTrue(response.alert)
        self.assertEqual(len(mail.outbox), 2)  # um para joe, um para admin (deduped)

    def test_sending_alerts_remove_self(self):
        """
        uma pergunta de joe, uma resposta do admin: joe responde.
        joe é o criador desta resposta, então ele não deve receber um email.
        só admin deve receber um alerta
        """
        mail.outbox = []

        response = Response.objects.create(
            question=self.question,
            user=self.joe,
            body='Response by joe himself!',
            alert=True,
        )

        self.assertTrue(response.alert)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.admin.email])

    def test_sending_staffers_on_new_question(self):
        """
        quando um usuário não-staff cria uma nova pergunta, os staffers com knowledge.change_question
        recebem um alerta.
        """
        mail.outbox = []

        Question.objects.create(
            user=self.joe,
            title='New question by joe',
            body='Question body content',
            status='private',
            alert=True,
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.admin.email])

    def test_sending_staffers_remove_self(self):
        """
        quando um usuário staff cria uma nova pergunta, ele é excluído dos destinatários.
        """
        mail.outbox = []

        Question.objects.create(
            user=self.admin,
            title='New question by admin',
            body='Question body content',
            status='private',
            alert=True,
        )

        self.assertEqual(len(mail.outbox), 0)

    def test_no_alerts_when_settings_disabled(self):
        """
        quando settings.ALERTS é falso, nenhum alerta é enviado.
        """
        settings.ALERTS = False
        mail.outbox = []

        Response.objects.create(
            question=self.question,
            user=self.bob,
            body='Response without alerts enabled',
            alert=True,
        )

        self.assertEqual(len(mail.outbox), 0)
