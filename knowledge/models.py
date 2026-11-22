from __future__ import annotations

from typing import Any, Optional

from knowledge import settings

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings as django_settings
from django.urls import reverse

from knowledge.managers import QuestionManager, ResponseManager
from knowledge.signals import knowledge_post_save

STATUSES = (
    ('public', _('Public')),
    ('private', _('Private')),
    ('internal', _('Internal')),
)


STATUSES_EXTENDED = STATUSES + (
    ('inherit', _('Inherit')),
)


class Category(models.Model):
    added = models.DateTimeField(auto_now_add=True)
    lastchanged = models.DateTimeField(auto_now=True)

    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)

    def __str__(self) -> str:
        return self.title

    class Meta:
        ordering = ['title']
        verbose_name = _('Category')
        verbose_name_plural = _('Categories')


class KnowledgeBase(models.Model):
    """
    The base class for Knowledge models.
    """
    is_question: bool = False
    is_response: bool = False

    added = models.DateTimeField(auto_now_add=True)
    lastchanged = models.DateTimeField(auto_now=True)

    user = models.ForeignKey(django_settings.AUTH_USER_MODEL, blank=True,
                             null=True, db_index=True,
                             on_delete=models.SET_NULL)
    alert = models.BooleanField(default=settings.ALERTS,
        verbose_name=_('Alert'),
        help_text=_('Check this if you want to be alerted when a new'
                        ' response is added.'))

    # for anonymous posting, if permitted
    name = models.CharField(max_length=64, blank=True, null=True,
        verbose_name=_('Name'),
        help_text=_('Enter your first and last name.'))
    email = models.EmailField(blank=True, null=True,
        verbose_name=_('Email'),
        help_text=_('Enter a valid email address.'))

    class Meta:
        abstract = True

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.user and self.name and self.email \
                and not self.id:
            # first time because no id
            self.public(save=False)

        if settings.AUTO_PUBLICIZE and not self.id:
            self.public(save=False)

        super().save(*args, **kwargs)

    #########################
    #### GENERIC GETTERS ####
    #########################

    def get_name(self) -> str:
        """
        Get local name, then self.user's first/last, and finally
        their username if all else fails.
        """
        name = (self.name or (self.user and (
            '{0} {1}'.format(self.user.first_name, self.user.last_name).strip()
            or self.user.username
        )) or '')
        return name.strip() or _("Anonymous")

    def get_email(self) -> Optional[str]:
        """retornar a instancia email ou email do usuário"""
        return self.email or (self.user and self.user.email)

    def get_pair(self) -> tuple[str, Optional[str]]:
        """retornar tupla(name, email) """
        return (self.get_name(), self.get_email())

    def get_user_or_pair(self) -> Any:
        """retornar a instancia do usuário ou um par (name, email)"""
        return self.user or self.get_pair()

    ########################
    #### STATUS METHODS ####
    ########################

    def can_view(self, user: Any) -> bool:
        """
        Returns a boolean dictating if a User like instance can
        view the current Model instance.
        """

        if self.status == 'inherit' and self.is_response:
            return self.question.can_view(user)

        if self.status == 'internal' and user.is_staff:
            return True

        if self.status == 'private':
            if self.user == user or user.is_staff:
                return True
            if self.is_response and self.question.user == user:
                return True

        if self.status == 'public':
            return True

        return False

    def switch(self, status: str, save: bool = True) -> None:
        self.status = status
        if save:
            self.save()
    switch.alters_data = True

    def public(self, save: bool = True) -> None:
        self.switch('public', save)
    public.alters_data = True

    def private(self, save: bool = True) -> None:
        self.switch('private', save)
    private.alters_data = True

    def inherit(self, save: bool = True) -> None:
        self.switch('inherit', save)
    inherit.alters_data = True

    def internal(self, save: bool = True) -> None:
        self.switch('internal', save)
    internal.alters_data = True


class Question(KnowledgeBase):
    is_question: bool = True
    _requesting_user: Any = None

    title = models.CharField(max_length=255,
        verbose_name=_('Question'),
        help_text=_('Enter your question or suggestion.'))
    body = models.TextField(blank=True, null=True,
        verbose_name=_('Description'),
        help_text=_('Please offer details. Markdown enabled.'))

    status = models.CharField(
        verbose_name=_('Status'),
        max_length=32, choices=STATUSES,
        default='private', db_index=True)

    locked = models.BooleanField(default=False)

    categories = models.ManyToManyField('knowledge.Category', blank=True)

    objects = QuestionManager()

    class Meta:
        ordering = ['-added']
        verbose_name = _('Question')
        verbose_name_plural = _('Questions')

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        from django.template.defaultfilters import slugify

        if settings.SLUG_URLS:
            return reverse('knowledge_thread', args=[self.id, slugify(self.title)])
        else:
            return reverse('knowledge_thread_no_slug', args=[self.id])

    def inherit(self) -> None:
        pass

    def internal(self) -> None:
        pass

    def lock(self, save: bool = True) -> None:
        self.locked = not self.locked
        if save:
            self.save()
    lock.alters_data = True

    ###################
    #### RESPONSES ####
    ###################

    def get_responses(self, user: Any = None) -> list | models.QuerySet:
        user = user or self._requesting_user
        if user:
            return [r for r in self.responses.all().select_related('user') if r.can_view(user)]
        else:
            return self.responses.all().select_related('user')

    def answered(self) -> bool:
        """
        Returns a boolean indictating whether there any questions.
        """
        return bool(self.get_responses())

    def accepted(self) -> bool:
        """
        Returns a boolean indictating whether there is a accepted answer
        or not.
        """
        return any([r.accepted for r in self.get_responses()])

    def clear_accepted(self) -> None:
        self.responses.all().update(accepted=False)
    clear_accepted.alters_data = True

    def accept(self, response: Any = None) -> bool:
        """
        Given a response, make that the one and only accepted answer.
        Similar to StackOverflow.
        """
        self.clear_accepted()

        if response and response.question == self:
            response.accepted = True
            response.save()
            return True
        else:
            return False
    accept.alters_data = True

    def states(self) -> list[str | None]:
        """
        Handy for checking for mod bar button state.
        """
        return [self.status, 'lock' if self.locked else None]

    @property
    def url(self) -> str:
        return self.get_absolute_url()


class Response(KnowledgeBase):
    is_response: bool = True

    question = models.ForeignKey('knowledge.Question',
        related_name='responses',
        on_delete=models.CASCADE)

    body = models.TextField(blank=True, null=True,
        verbose_name=_('Response'),
        help_text=_('Please enter your response. Markdown enabled.'))
    status = models.CharField(
        verbose_name=_('Status'),
        max_length=32, choices=STATUSES_EXTENDED,
        default='inherit', db_index=True)
    accepted = models.BooleanField(default=False)

    objects = ResponseManager()

    class Meta:
        ordering = ['added']
        verbose_name = _('Response')
        verbose_name_plural = _('Responses')

    def __str__(self) -> str:
        return (self.body or '')[0:100] + '...'

    def states(self) -> list[str | None]:
        """
        Handy for checking for mod bar button state.
        """
        return [self.status, 'accept' if self.accepted else None]

    def accept(self) -> None:
        self.question.accept(self)
    accept.alters_data = True


# cannot attach on abstract = True... derp
models.signals.post_save.connect(knowledge_post_save, sender=Question)
models.signals.post_save.connect(knowledge_post_save, sender=Response)
