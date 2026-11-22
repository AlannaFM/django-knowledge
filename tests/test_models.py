from django.test import TestCase
from django.contrib.auth.models import User, AnonymousUser
from django.core import mail

from knowledge.models import Question, Response, Category


class ModelsTestCase(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'secret')
        self.joe = User.objects.create_user('joe', 'joedirt@example.com', 'secret')
        self.bob = User.objects.create_user('bob', 'bob@example.com', 'secret')
        self.anon = AnonymousUser()

        self.joe.first_name = 'Joe'
        self.joe.last_name = 'Dirt'
        self.joe.save()

        #joe pergunta
        self.question = Question.objects.create(
            user=self.joe,
            title='What time is it?',
            body='Whenever I look at my watch I see the little hand at 3 and the big hand at 7.',
        )

        # admin responde
        self.response = Response.objects.create(
            question=self.question,
            user=self.admin,
            body='The little hand at 3 means 3 pm or am, the big hand at 7 means 3:35 am or pm.',
        )

    def test_category_str(self):
        category = Category.objects.create(title='Python', slug='python')
        self.assertEqual(str(category), 'Python')

    def test_basic_question_answering(self):
        """
        dada uma pergunta feita por um usuário real, rastreie os estados de resposta e aceitação.
        """
        question = Question.objects.create(
            user=self.joe,
            title='What time is it?',
            body='Whenever I look at my watch I see the little hand at 3 and the big hand at 7.',
        )

        self.assertFalse(question.answered())
        self.assertFalse(question.accepted())

        response = Response.objects.create(
            question=question,
            user=self.admin,
            body='The little hand at 3 means 3 pm or am, the big hand at 7 means 3:35 am or pm.',
        )

        self.assertTrue(question.answered())
        self.assertFalse(question.accepted())

        # joe aceita a resposta
        question.accept(response)

        self.assertTrue(question.answered())
        self.assertTrue(question.accepted())
        self.assertIn('accept', response.states())

        # remover resposta aceita
        question.accept()

        self.assertFalse(question.accepted())

        response = Response.objects.get(id=response.id)  # recarregar
        self.assertNotIn('accept', response.states())

        # aceitar resposta
        response.accept()

        question = Question.objects.get(id=question.id)  # recarregar
        self.assertTrue(question.answered())
        self.assertTrue(question.accepted())
        self.assertIn('accept', response.states())

    def test_switching_question(self):
        question = self.question
        self.assertEqual(question.status, 'private')
        self.assertIn('private', question.states())

        question.public()
        self.assertEqual(question.status, 'public')
        self.assertIn('public', question.states())

        question.private()
        self.assertEqual(question.status, 'private')
        self.assertIn('private', question.states())

        # herdar e interno não alteram o status da pergunta
        question.inherit()
        self.assertEqual(question.status, 'private')
        self.assertIn('private', question.states())

        question.internal()
        self.assertEqual(question.status, 'private')
        self.assertIn('private', question.states())

    def test_switching_response(self):
        response = self.response
        self.assertEqual(response.status, 'inherit')
        self.assertIn('inherit', response.states())

        response.public()
        self.assertEqual(response.status, 'public')
        self.assertIn('public', response.states())

        response.internal()
        self.assertEqual(response.status, 'internal')
        self.assertIn('internal', response.states())

        response.private()
        self.assertEqual(response.status, 'private')
        self.assertIn('private', response.states())

        response.inherit()
        self.assertEqual(response.status, 'inherit')
        self.assertIn('inherit', response.states())

    def test_question_can_view_matrix(self):
        """
        teste de matriz para Question.can_view:
        status (public, private, internal) x usuário (anonymous, owner, other user, staff)
        """
        question = self.question  # dono é joe

        #  PUBLICO 
        question.public()
        self.assertTrue(question.can_view(self.anon), "Public question should be visible to anonymous")
        self.assertTrue(question.can_view(self.joe), "Public question should be visible to owner")
        self.assertTrue(question.can_view(self.bob), "Public question should be visible to other user")
        self.assertTrue(question.can_view(self.admin), "Public question should be visible to staff")

        #  PRIVADO 
        question.private()
        self.assertFalse(question.can_view(self.anon), "Private question should not be visible to anonymous")
        self.assertTrue(question.can_view(self.joe), "Private question should be visible to owner")
        self.assertFalse(question.can_view(self.bob), "Private question should not be visible to other user")
        self.assertTrue(question.can_view(self.admin), "Private question should be visible to staff")

        #  INTERNO 
        question.status = 'internal'
        question.save()
        self.assertFalse(question.can_view(self.anon), "Internal question should not be visible to anonymous")
        self.assertFalse(question.can_view(self.joe), "Internal question should not be visible to non-staff owner")
        self.assertFalse(question.can_view(self.bob), "Internal question should not be visible to other user")
        self.assertTrue(question.can_view(self.admin), "Internal question should be visible to staff")

    def test_response_can_view_matrix(self):
        """
        teste de matriz para Response.can_view:
        status (public, private, internal, inherit) x usuário (anonymous, owner, question owner, other user, staff)
        """
        question = self.question  # dono da pergunta é joe
        response = self.response  # dono da resposta é admin

        #  uma resposta criada por bob para testar dono da resposta vs dono da pergunta
        bob_response = Response.objects.create(
            question=question,
            user=self.bob,
            body='Bob response body',
            status='public',
        )

        #  PUBLICO 
        bob_response.public()
        self.assertTrue(bob_response.can_view(self.anon))
        self.assertTrue(bob_response.can_view(self.bob))    # dono da resposta
        self.assertTrue(bob_response.can_view(self.joe))    # dono da pergunta
        self.assertTrue(bob_response.can_view(self.admin))  # staff

        #  PRIVADO 
        bob_response.private()
        self.assertFalse(bob_response.can_view(self.anon), "Private response hidden from anon")
        self.assertTrue(bob_response.can_view(self.bob), "Private response visible to response owner")
        self.assertTrue(bob_response.can_view(self.joe), "Private response visible to question owner")
        self.assertTrue(bob_response.can_view(self.admin), "Private response visible to staff")

        other_user = User.objects.create_user('charlie', 'charlie@example.com', 'secret')
        self.assertFalse(bob_response.can_view(other_user), "Private response hidden from unrelated user")

        #  INTERNO 
        bob_response.internal()
        self.assertFalse(bob_response.can_view(self.anon), "Internal response hidden from anon")
        self.assertFalse(bob_response.can_view(self.bob), "Internal response hidden from response owner")
        self.assertFalse(bob_response.can_view(self.joe), "Internal response hidden from question owner")
        self.assertFalse(bob_response.can_view(other_user), "Internal response hidden from other user")
        self.assertTrue(bob_response.can_view(self.admin), "Internal response visible to staff")

      #HERDAR  
        bob_response.inherit()

        #  QUANDO A PERGUNTA É PÚBLICA
        question.public()
        self.assertTrue(bob_response.can_view(self.anon))
        self.assertTrue(bob_response.can_view(self.bob))
        self.assertTrue(bob_response.can_view(self.joe))
        self.assertTrue(bob_response.can_view(self.admin))

        #  QUANDO A PERGUNTA É PRIVADA
        question.private()
        self.assertFalse(bob_response.can_view(self.anon))
        self.assertFalse(bob_response.can_view(self.bob))  # bob não é dono da pergunta nem staff
        self.assertTrue(bob_response.can_view(self.joe))   # dono da pergunta
        self.assertTrue(bob_response.can_view(self.admin)) # staff

    def test_get_responses(self):
        """
        garante que adicionar outra resposta não se misture com outras respostas.
        """
        self.assertEqual(len(self.question.get_responses(self.anon)), 0)
        self.assertEqual(len(self.question.get_responses(self.joe)), 1)
        self.assertEqual(len(self.question.get_responses(self.admin)), 1)

        question2 = Question.objects.create(
            title='Where is my cat?',
            body='His name is whiskers.',
            user=self.joe,
        )
        Response.objects.create(
            question=question2,
            user=self.admin,
            body='I saw him in the backyard.',
        )

        self.assertEqual(len(self.question.get_responses(self.anon)), 0)
        self.assertEqual(len(self.question.get_responses(self.joe)), 1)
        self.assertEqual(len(self.question.get_responses(self.admin)), 1)

    def test_get_public_responses(self):
        """
        respostas públicas para perguntas públicas.
        """
        question = Question.objects.create(
            title='Where is my cat?',
            body='His name is whiskers.',
            user=self.joe,
            status='public',
        )
        Response.objects.create(
            question=question,
            user=self.admin,
            body='I saw him in the backyard.',
            status='inherit',
        )

        self.assertEqual(len(question.get_responses(self.anon)), 1)
        self.assertEqual(len(question.get_responses(self.joe)), 1)
        self.assertEqual(len(question.get_responses(self.admin)), 1)

    def test_locking(self):
        self.assertFalse(self.question.locked)
        self.assertNotIn('lock', self.question.states())

        self.question.lock()

        self.assertTrue(self.question.locked)
        self.assertIn('lock', self.question.states())

    def test_normal_question_get_name_and_email(self):
        self.assertEqual(self.question.get_name(), 'Joe Dirt')
        self.assertEqual(self.question.get_email(), 'joedirt@example.com')

        question = Question.objects.create(
            title='Where is my cat?',
            body='His name is whiskers.',
            user=self.bob,
        )

        self.assertEqual(question.get_name(), 'bob')  # username quando não tem o primeiro nome e sobrenome
        self.assertEqual(question.get_email(), 'bob@example.com')

    def test_anon_question_get_name_and_email(self):
        question = Question.objects.create(
            title='Where is my cat?',
            body='His name is whiskers.',
            name='Joe Dirt',
            email='joedirt@example.com',
        )

        self.assertEqual(question.get_name(), 'Joe Dirt')
        self.assertEqual(question.get_email(), 'joedirt@example.com')

    def test_response_str(self):
        self.assertEqual(str(self.response), self.response.body[0:100] + '...')
        empty_response = Response(question=self.question, body=None)
        self.assertEqual(str(empty_response), '...')
