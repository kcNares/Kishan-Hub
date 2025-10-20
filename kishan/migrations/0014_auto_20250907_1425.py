from django.db import migrations
import uuid
from django.db.models import Q


def generate_order_ids(apps, schema_editor):
    Rental = apps.get_model("kishan", "Rental")
    # Select rows where order_id is NULL or empty string
    # qs = Rental.objects.filter(Q(order_id__isnull=True) | Q(order_id__exact=""))
    # for rental in qs:
    #     rental.order_id = f"RNT-{uuid.uuid4().hex[:12].upper()}"
    #     rental.save(update_fields=["order_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("kishan", "0013_alter_rental_status"),
    ]

    operations = [
        migrations.RunPython(
            generate_order_ids, reverse_code=migrations.RunPython.noop
        ),
    ]
