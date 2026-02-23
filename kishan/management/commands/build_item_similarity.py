# kishan/management/commands/build_item_similarity.py
from django.core.management.base import BaseCommand
from kishan.recommender import build_item_similarity_matrix


class Command(BaseCommand):
    help = "Build and cache item-item similarity matrix for kishan recommender"

    def handle(self, *args, **options):
        self.stdout.write("Building item-item similarity matrix...")
        sim, id_to_index, index_to_id = build_item_similarity_matrix(force_rebuild=True)
        if sim.size == 0 or not id_to_index:
            self.stdout.write(
                self.style.WARNING("No rental interactions found; matrix is empty.")
            )
            return
        self.stdout.write(
            self.style.SUCCESS(f"Built similarity matrix shape: {sim.shape}")
        )
        self.stdout.write(f"Cached {len(id_to_index)} tools.")
