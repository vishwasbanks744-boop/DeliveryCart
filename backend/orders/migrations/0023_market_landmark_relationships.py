import django.db.models.deletion
from django.db import migrations, models


def populate_location_relations(apps, schema_editor):
    Market = apps.get_model("orders", "Market")
    Landmark = apps.get_model("orders", "Landmark")
    Restaurant = apps.get_model("orders", "Restaurant")

    for restaurant in Restaurant.objects.all().iterator():
        market_name = (restaurant.legacy_market_name or "").strip()
        if not market_name:
            continue
        pincode = (restaurant.pincode or "").strip()
        if len(pincode) != 6 or not pincode.isdigit():
            pincode = ""
        market, _ = Market.objects.get_or_create(name=market_name, pincode=pincode)
        restaurant.market_id = market.pk
        restaurant.save(update_fields=["market"])
        landmark_name = (restaurant.nearby_landmark or "").strip()
        if landmark_name:
            landmark, _ = Landmark.objects.get_or_create(name=landmark_name, market=market)
            restaurant.nearby_landmarks.add(landmark)


def restore_legacy_location_text(apps, schema_editor):
    Restaurant = apps.get_model("orders", "Restaurant")
    for restaurant in Restaurant.objects.all().iterator():
        if restaurant.market_id:
            restaurant.legacy_market_name = restaurant.market.name
            restaurant.save(update_fields=["legacy_market_name"])
        landmark = restaurant.nearby_landmarks.first()
        if landmark:
            restaurant.nearby_landmark = landmark.name
            restaurant.save(update_fields=["nearby_landmark"])


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0022_decimal_product_quantities"),
    ]

    operations = [
        migrations.CreateModel(
            name="Market",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160)),
                ("pincode", models.CharField(blank=True, max_length=6)),
            ],
            options={"ordering": ["name", "pincode"]},
        ),
        migrations.AddConstraint(
            model_name="market",
            constraint=models.UniqueConstraint(fields=("name", "pincode"), name="unique_market_name_pincode"),
        ),
        migrations.CreateModel(
            name="Landmark",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160)),
                ("market", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="landmarks", to="orders.market")),
            ],
            options={"ordering": ["market__name", "name"]},
        ),
        migrations.AddConstraint(
            model_name="landmark",
            constraint=models.UniqueConstraint(fields=("name", "market"), name="unique_landmark_per_market"),
        ),
        migrations.RenameField(
            model_name="restaurant",
            old_name="market",
            new_name="legacy_market_name",
        ),
        migrations.AddField(
            model_name="restaurant",
            name="market",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="restaurants", to="orders.market"),
        ),
        migrations.AddField(
            model_name="restaurant",
            name="nearby_landmarks",
            field=models.ManyToManyField(blank=True, related_name="restaurants", to="orders.landmark"),
        ),
        migrations.AddField(
            model_name="accountprofile",
            name="landmark",
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.AddField(
            model_name="accountprofile",
            name="market",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="customers", to="orders.market"),
        ),
        migrations.AddField(
            model_name="accountprofile",
            name="pincode",
            field=models.CharField(blank=True, max_length=6),
        ),
        migrations.RunPython(populate_location_relations, restore_legacy_location_text),
    ]
