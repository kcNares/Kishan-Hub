# kishan/tests/test_recommender.py
from django.test import TestCase
from django.contrib.auth.models import User
from accounts.models import Profile
from kishan.models import Tool, Rental
from kishan.recommender import build_item_similarity_matrix, recommend_tools_for_farmer
from datetime import timedelta
from django.utils import timezone


class RecommenderTestCase(TestCase):
    def setUp(self):
        # create farmer users and profiles
        u1 = User.objects.create_user(username="farmer1", password="pass")
        u2 = User.objects.create_user(username="farmer2", password="pass")
        p1 = Profile.objects.create(user=u1, is_farmer=True)
        p2 = Profile.objects.create(user=u2, is_farmer=True)

        # create sample tools
        t1 = Tool.objects.create(
            name="Tractor A",
            description="Tractor",
            image="test.jpg",
            daily_rent_price=1000,
            delivery_charge=0,
            category_id=1,
            owner_id=1,
        )
        t2 = Tool.objects.create(
            name="Harrow B",
            description="Harrow",
            image="test.jpg",
            daily_rent_price=500,
            delivery_charge=0,
            category_id=1,
            owner_id=1,
        )
        t3 = Tool.objects.create(
            name="Rotavator C",
            description="Rotavator",
            image="test.jpg",
            daily_rent_price=700,
            delivery_charge=0,
            category_id=1,
            owner_id=1,
        )
        t4 = Tool.objects.create(
            name="Water Pump D",
            description="Pump",
            image="test.jpg",
            daily_rent_price=300,
            delivery_charge=0,
            category_id=1,
            owner_id=1,
        )

        now = timezone.now()
        # create rentals: farmer1 rented t1 and t2; farmer2 rented t1 and t3
        Rental.objects.create(
            tool=t1,
            farmer=p1,
            start_date=now - timedelta(days=10),
            end_date=now - timedelta(days=9),
            total_price=1000,
            status="paid",
            is_active=False,
        )
        Rental.objects.create(
            tool=t2,
            farmer=p1,
            start_date=now - timedelta(days=8),
            end_date=now - timedelta(days=7),
            total_price=500,
            status="paid",
            is_active=False,
        )
        Rental.objects.create(
            tool=t1,
            farmer=p2,
            start_date=now - timedelta(days=6),
            end_date=now - timedelta(days=5),
            total_price=1000,
            status="paid",
            is_active=False,
        )
        Rental.objects.create(
            tool=t3,
            farmer=p2,
            start_date=now - timedelta(days=4),
            end_date=now - timedelta(days=3),
            total_price=700,
            status="paid",
            is_active=False,
        )

    def test_build_similarity(self):
        sim, id_map, idx_map = build_item_similarity_matrix(force_rebuild=True)
        # ensure we have some tools
        self.assertTrue(sim.size > 0)
        self.assertTrue(len(id_map) >= 3)

    def test_recommend_for_farmer(self):
        p = Profile.objects.get(user__username="farmer1")
        qs = recommend_tools_for_farmer(p, top_n=3)
        # Should recommend t3 (Rotavator) since farmer2 who rented t1 also rented t3
        names = [t.name for t in qs]
        self.assertIn("Rotavator C", names)
