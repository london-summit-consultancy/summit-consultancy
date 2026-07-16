import pytest

from apps.services.models import BuyerType, Service, ServiceCategory


@pytest.fixture
def category(db):
    return ServiceCategory.objects.create(
        buyer_type=BuyerType.CLIENT,
        headline="Services for Clients",
        description="Test category",
        display_order=1,
    )


@pytest.fixture
def service(db, category):
    return Service.objects.create(
        category=category,
        name="Contract Management",
        slug="contract-management",
        short_desc="Expert contract administration.",
        body="Full body text.",
        display_order=1,
    )
