from functools import wraps
from operator import methodcaller

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import NoReverseMatch, reverse
from django.views.decorators.http import require_POST

from knowledge import settings
from knowledge.forms import get_question_form_class, get_response_form_class
from knowledge.models import Category, Question, Response
from knowledge.utils import paginate


# Despacho explícito da moderação: só o que está neste dicionário pode ser
# executado. Nada vindo da URL é usado como nome de método (sem getattr).
MODERATION_ACTIONS = {
    'question': {
        'private': methodcaller('private'),
        'public': methodcaller('public'),
        'delete': methodcaller('delete'),
        'lock': methodcaller('lock'),
        'clear_accepted': methodcaller('clear_accepted'),
    },
    'response': {
        'internal': methodcaller('internal'),
        'inherit': methodcaller('inherit'),
        'private': methodcaller('private'),
        'public': methodcaller('public'),
        'delete': methodcaller('delete'),
        'accept': methodcaller('accept'),
    },
}

# Usado pelos templates (context 'allowed_mods') e como ponto de extensão.
ALLOWED_MODS = {
    model: list(actions) for model, actions in MODERATION_ACTIONS.items()
}

MODERATION_MODELS = {
    'question': (Question, 'knowledge.change_question'),
    'response': (Response, 'knowledge.change_response'),
}


def _redirect_to_login(request):
    return HttpResponseRedirect(
        settings.LOGIN_URL + "?next=%s" % request.path)


def knowledge_login_required(view):
    """
    Substitui o bloco de login repetido nas views.
    Respeita KNOWLEDGE_LOGIN_REQUIRED (settings.LOGIN_REQUIRED), lido
    na hora do uso, por isso @login_required puro não serve.
    """
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if settings.LOGIN_REQUIRED and not request.user.is_authenticated:
            return _redirect_to_login(request)
        return view(request, *args, **kwargs)
    return wrapper


def get_my_questions(request):
    if request.user.is_anonymous:
        return None
    return Question.objects.can_view(request.user)\
                           .filter(user=request.user)


def _set_requesting_user(questions, user):
    # this is for get_responses()
    for question in questions:
        question._requesting_user = user


@knowledge_login_required
def knowledge_index(request,
                    template='django_knowledge/index.html'):

    questions = Question.objects.can_view(request.user)\
                                .prefetch_related('responses__question')[0:20]
    _set_requesting_user(questions, request.user)

    return render(request, template, {
        'request': request,
        'questions': questions,
        'my_questions': get_my_questions(request),
        'categories': Category.objects.all(),
        'BASE_TEMPLATE': settings.BASE_TEMPLATE,
    })


@knowledge_login_required
def knowledge_list(request,
                   category_slug=None,
                   template='django_knowledge/list.html',
                   Form=None):

    search = request.GET.get('title', None)
    questions = Question.objects.can_view(request.user)\
                                .prefetch_related('responses__question')

    if search:
        questions = questions.filter(
            Q(title__icontains=search) | Q(body__icontains=search)
        )

    category = None
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        questions = questions.filter(categories=category)

    paginator, questions = paginate(questions,
                                    50,
                                    request.GET.get('page', '1'))
    _set_requesting_user(questions, request.user)

    form_class = Form or get_question_form_class(request.user)
    form = None
    if form_class is not None:
        form = form_class(user=request.user,
                          initial={'title': search})  # prefill title

    return render(request, template, {
        'request': request,
        'search': search,
        'questions': questions,
        'my_questions': get_my_questions(request),
        'category': category,
        'categories': Category.objects.all(),
        'form': form,
        'BASE_TEMPLATE': settings.BASE_TEMPLATE,
    })


@knowledge_login_required
def knowledge_thread(request,
                     question_id,
                     slug=None,
                     template='django_knowledge/thread.html',
                     Form=None):

    try:
        question = Question.objects.can_view(request.user)\
                                   .get(id=question_id)
    except Question.DoesNotExist:
        if Question.objects.filter(id=question_id).exists() and \
                                hasattr(settings, 'LOGIN_REDIRECT_URL'):
            return redirect(settings.LOGIN_REDIRECT_URL)
        else:
            raise Http404

    responses = question.get_responses(request.user)

    if request.path != question.get_absolute_url():
        return redirect(question.get_absolute_url(), permanent=True)

    form_class = Form or get_response_form_class(request.user)

    if request.method == 'POST':
        form = form_class(request.POST, user=request.user, question=question)
        if form.is_valid():
            if not form.is_spam:
                form.save()
            return redirect(question.get_absolute_url())
    else:
        form = form_class(user=request.user, question=question)

    return render(request, template, {
        'request': request,
        'question': question,
        'my_questions': get_my_questions(request),
        'responses': responses,
        'allowed_mods': ALLOWED_MODS,
        'form': form,
        'categories': Category.objects.all(),
        'BASE_TEMPLATE': settings.BASE_TEMPLATE,
    })


@knowledge_login_required
@require_POST
def knowledge_moderate(
        request,
        lookup_id,
        model,
        mod,
        allowed_mods=ALLOWED_MODS):

    """
    An easy to extend method to moderate questions
    and responses in a vaguely RESTful way.

    Usage:
        /knowledge/moderate/question/1/inherit/     -> 404 (mod not allowed)
        /knowledge/moderate/question/1/public/      -> 302 (redirect)

        /knowledge/moderate/response/3/notreal/     -> 404
        /knowledge/moderate/response/3/inherit/     -> 302 (redirect)

        GET on any moderate URL                     -> 405
        User without permission                     -> 403
    """

    if model not in MODERATION_MODELS:
        raise Http404
    Model, perm = MODERATION_MODELS[model]

    if not request.user.has_perm(perm):
        raise PermissionDenied

    if mod not in allowed_mods.get(model, ()):
        raise Http404
    action = MODERATION_ACTIONS[model].get(mod)
    if action is None:
        raise Http404

    instance = get_object_or_404(
        Model.objects.can_view(request.user),
        id=lookup_id)

    action(instance)

    try:
        return redirect((
            instance if instance.is_question else instance.question
        ).get_absolute_url())
    except NoReverseMatch:
        # if we delete an instance...
        return redirect(reverse('knowledge_index'))


@knowledge_login_required
def knowledge_ask(request,
                  template='django_knowledge/ask.html',
                  Form=None):

    form_class = Form or get_question_form_class(request.user)
    if form_class is None:
        # anônimos não podem perguntar (ALLOW_ANONYMOUS desligado)
        return _redirect_to_login(request)

    if request.method == 'POST':
        form = form_class(request.POST, user=request.user)
        if form.is_valid():
            if form.is_spam:
                return redirect('knowledge_index')
            question = form.save()
            return redirect(question.get_absolute_url())
    else:
        form = form_class(user=request.user)

    return render(request, template, {
        'request': request,
        'my_questions': get_my_questions(request),
        'form': form,
        'categories': Category.objects.all(),
        'BASE_TEMPLATE': settings.BASE_TEMPLATE,
    })