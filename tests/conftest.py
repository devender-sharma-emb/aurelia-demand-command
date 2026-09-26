import pytest

from aurelia.generate import generate
from aurelia.world import RetailWorld


@pytest.fixture(scope="session")
def tables():
    return generate(seed=42)


@pytest.fixture(scope="session")
def world(tables):
    return RetailWorld(**tables)
