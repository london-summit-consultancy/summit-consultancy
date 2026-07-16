import pytest
from django.urls import reverse


class TestHomeJourney:
    def test_homepage_renders(self, client, db):
        response = client.get(reverse("core:home"))
        assert response.status_code == 200

    def test_homepage_is_rebranded(self, client, db):
        html = client.get(reverse("core:home")).content.decode()
        assert "London Summit" in html
        assert "Pioneer" not in html

    def test_homepage_has_static_wireframe_hero_and_no_webgl(self, client, db):
        # 3D/WebGL removed: the opener is now a static blueprint hero.
        html = client.get(reverse("core:home")).content.decode()
        assert "experience.min.js" not in html
        assert "data-experience" not in html
        assert "data-hero-wireframe" in html
        assert "lsx-blueprint" in html

    def test_homepage_renders_chapter_narrative(self, client, db):
        html = client.get(reverse("core:home")).content.decode()
        # Chapters are server-rendered as the permanent narrative. The evergreen
        # chapters always render; data-driven ones (featured services/projects)
        # appear when content exists — see test_chapter_three_weaves_featured_services.
        assert html.count("data-chapter-node") >= 4

    def test_chapter_one_carries_hero_h1_for_fallback(self, client, db):
        html = client.get(reverse("core:home")).content.decode()
        assert "<h1" in html

    def test_chapter_three_weaves_featured_services(self, client, service):
        service.is_featured = True
        service.save()
        html = client.get(reverse("core:home")).content.decode()
        assert service.name.lower() in html.lower()


class TestSecondaryHeroes:
    @pytest.mark.parametrize(
        "url_name",
        ["core:about", "services:landing", "portfolio:list", "inquiries:contact"],
    )
    def test_page_has_static_hero_motif_and_no_webgl(self, client, db, url_name):
        # Ambient 3D removed: heroes carry a static blueprint motif instead.
        response = client.get(reverse(url_name))
        assert response.status_code == 200
        html = response.content.decode()
        assert "data-experience" not in html
        assert "experience.min.js" not in html
        assert "hero-motif" in html
