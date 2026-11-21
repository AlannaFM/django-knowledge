def test_settings_do_django_carregam(settings):
    assert settings.ROOT_URLCONF == "core.urls"
