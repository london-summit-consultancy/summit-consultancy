import factory
from django.contrib.auth import get_user_model

from apps.portfolio.models import Sector
from apps.tenders.models import DocumentProcessingStatus, Tender, TenderDocument

User = get_user_model()


class StaffUserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"staff{n}@londonsummit.test")
    full_name = factory.Sequence(lambda n: f"Staff Member {n}")
    is_staff = True
    is_active = True

    @factory.post_generation
    def password(self, create: bool, extracted: str | None, **kwargs) -> None:
        # Hash + persist the password ourselves so the stored hash matches the
        # instance force_login() uses (otherwise the session auth-hash mismatches
        # and every authenticated request reads as anonymous).
        self.set_password(extracted or "pw-test-12345")
        if create:
            self.save()


class TenderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Tender

    title = factory.Sequence(lambda n: f"Tender Opportunity {n}")
    client_name = factory.Sequence(lambda n: f"Client {n} Ltd")
    sector = Sector.INFRASTRUCTURE
    description = "Scope of works for the opportunity."
    created_by = factory.SubFactory(StaffUserFactory)


class TenderDocumentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TenderDocument

    tender = factory.SubFactory(TenderFactory)
    title = factory.Sequence(lambda n: f"Document {n}")
    revision = "Rev A"
    processing_status = DocumentProcessingStatus.READY
    uploaded_by = factory.SubFactory(StaffUserFactory)
