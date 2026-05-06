import pytest

pytest_plugins = "playwright.pytest_plugin"


def pytest_configure(config):
    config.option.browser = ["chromium", "firefox", "webkit"]