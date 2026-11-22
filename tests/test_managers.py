from django.test import TestCase
from django.contrib.auth.models import User, AnonymousUser

from knowledge.models import Question, Response


class ManagersTestCase(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'secret')
        self.joe = User.objects.create_user('joe', 'joedirt@example.com', 'secret')
        self.bob = User.objects.create_user('bob', 'bob@example.com', 'secret')
        self.anon = AnonymousUser()

        self.joe.first_name = 'Joe'
        self.joe.last_name = 'Dirt'
        self.joe.save()

        # joe asks a question (private by default)
        self.question = Question.objects.create(
            user=self.joe,
            title='What time is it?',
            body='Whenever I look at my watch I see the little hand at 3 and the big hand at 7.',
        )

        # admin responds (inherit by default)
        self.response = Response.objects.create(
            question=self.question,
            user=self.admin,
            body='The little hand at 3 means 3 pm or am, the big hand at 7 means 3:35 am or pm.',
        )

    def test_question_can_view_queryset(self):
        Q = Question.objects

        # default: pergunta é privada
        self.assertEqual(Q.can_view(self.anon).count(), 0)
        self.assertEqual(Q.can_view(self.bob).count(), 0)
        self.assertEqual(Q.can_view(self.joe).count(), 1)
        self.assertEqual(Q.can_view(self.admin).count(), 1)

        # tranformar pergunta em pública
        self.question.public()
        self.assertEqual(Q.can_view(self.anon).count(), 1)
        self.assertEqual(Q.can_view(self.bob).count(), 1)
        self.assertEqual(Q.can_view(self.joe).count(), 1)
        self.assertEqual(Q.can_view(self.admin).count(), 1)

        # tornar pergunta privada novamente
        self.question.private()
        self.assertEqual(Q.can_view(self.anon).count(), 0)
        self.assertEqual(Q.can_view(self.bob).count(), 0)
        self.assertEqual(Q.can_view(self.joe).count(), 1)
        self.assertEqual(Q.can_view(self.admin).count(), 1)

    def test_question_can_view_internal_queryset(self):
        Q = Question.objects
        self.question.status = 'internal'
        self.question.save()

        # pergunta interna: apenas staff/superuser podem ver
        self.assertEqual(Q.can_view(self.anon).count(), 0)
        self.assertEqual(Q.can_view(self.bob).count(), 0)
        self.assertEqual(Q.can_view(self.joe).count(), 0)
        self.assertEqual(Q.can_view(self.admin).count(), 1)

    def test_response_can_view_queryset(self):
        R = Response.objects

        # default: resposta é herdeira, pergunta é privada -> apenas joe (dono da pergunta) e admin (staff)
        self.assertEqual(R.can_view(self.anon).count(), 0)
        self.assertEqual(R.can_view(self.bob).count(), 0)
        self.assertEqual(R.can_view(self.joe).count(), 1)
        self.assertEqual(R.can_view(self.admin).count(), 1)

        # tranformar resposta em pública
        self.response.public()
        self.assertEqual(R.can_view(self.anon).count(), 1)
        self.assertEqual(R.can_view(self.bob).count(), 1)
        self.assertEqual(R.can_view(self.joe).count(), 1)
        self.assertEqual(R.can_view(self.admin).count(), 1)

        # tornar resposta interna
        self.response.internal()
        self.assertEqual(R.can_view(self.anon).count(), 0)
        self.assertEqual(R.can_view(self.bob).count(), 0)
        self.assertEqual(R.can_view(self.joe).count(), 0)
        self.assertEqual(R.can_view(self.admin).count(), 1)

        # tornar resposta privada (resposta de admin, pergunta de joe)
        self.response.private()
        self.assertEqual(R.can_view(self.anon).count(), 0)
        self.assertEqual(R.can_view(self.bob).count(), 0)
        self.assertEqual(R.can_view(self.joe).count(), 1)   # dono da pergunta
        self.assertEqual(R.can_view(self.admin).count(), 1) # dono da resposta e staff

    def test_staff_nao_superuser_ve_conteudo_interno(self):
        staff = User.objects.create_user(
            'staff', 'staff@example.com', 'secret', is_staff=True)

        self.question.status = 'internal'
        self.question.save()
        self.response.status = 'internal'
        self.response.save()

        self.assertEqual(Question.objects.can_view(staff).count(), 1)
        self.assertEqual(Response.objects.can_view(staff).count(), 1)
        self.assertTrue(self.question.can_view(staff))
        self.assertTrue(self.response.can_view(staff))