import pytest


@pytest.fixture
def joe(db, django_user_model):
    return django_user_model.objects.create_user("joe", "joe@example.com", "senha123")


@pytest.fixture
def bob(db, django_user_model):
    return django_user_model.objects.create_user("bob", "bob@example.com", "senha123")


@pytest.fixture
def staff_user(db, django_user_model):
    return django_user_model.objects.create_user(
        "staff", "staff@example.com", "senha123", is_staff=True
    )
