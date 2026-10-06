from decimal import Decimal
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User
from catalog.models import Product, Variant, ShippingRate
from catalog.services import hq_bulk_update
from orders.models import Order
from orders.services import place_order, mark_paid, ship_order


class Command(BaseCommand):
    help = "Seed initial Elrah Exclusive demo users, apparel collections, variants, shipping rates and sample orders."

    def handle(self, *args, **options):
        self.stdout.write("Starting Elrah Exclusive data seed...")

        # 1. Regional Shipping Rates (Per Order)
        for region, fee in ShippingRate.DEFAULTS.items():
            rate, created = ShippingRate.objects.get_or_create(region=region, defaults={"fee": fee})
            if created:
                self.stdout.write(f"Created ShippingRate: {rate}")

        # 2. Key User Accounts
        admin_user, _ = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@elrahexclusive.my",
                "first_name": "Elrah",
                "last_name": "Executive Admin",
                "role": User.Role.ADMIN,
                "status": User.Status.APPROVED,
                "is_staff": True,
                "is_superuser": True,
                "phone": "0120000001",
                "shop_name": "Elrah Exclusive Headquarters",
            },
        )
        admin_user.set_password("password123")
        admin_user.save()

        hq_user, _ = User.objects.get_or_create(
            username="hq",
            defaults={
                "email": "hq@elrahexclusive.my",
                "first_name": "Elrah HQ",
                "last_name": "Warehouse",
                "role": User.Role.HQ,
                "status": User.Status.APPROVED,
                "phone": "0120000002",
                "shop_name": "Elrah Central Fulfillment Hub",
            },
        )
        hq_user.set_password("password123")
        hq_user.save()

        ds1, _ = User.objects.get_or_create(
            username="dropship1",
            defaults={
                "email": "dropship1@elrahexclusive.my",
                "first_name": "Ali",
                "last_name": "Eksklusif Boutique",
                "role": User.Role.DROPSHIPPER,
                "status": User.Status.APPROVED,
                "phone": "0191234567",
                "shop_name": "Ali Elrah Boutique",
                "bank_name": "Maybank",
                "bank_account_number": "164012345678",
                "bank_account_holder": "Ali bin Abu",
                "bank_id_number": "950101-14-1234",
            },
        )
        ds1.bank_name = "Maybank"
        ds1.bank_account_number = "164012345678"
        ds1.bank_account_holder = "Ali bin Abu"
        ds1.bank_id_number = "950101-14-1234"
        ds1.set_password("password123")
        ds1.save()

        pending_user, _ = User.objects.get_or_create(
            username="pending1",
            defaults={
                "email": "pending1@elrahexclusive.my",
                "first_name": "Siti",
                "last_name": "Apparel",
                "role": User.Role.DROPSHIPPER,
                "status": User.Status.PENDING,
                "phone": "0187654321",
                "shop_name": "Siti Muslimah & Menswear",
            },
        )
        pending_user.set_password("password123")
        pending_user.save()

        self.stdout.write("Created users: admin, hq, dropship1 (approved affiliate), pending1 (pending applicant)")

        # 3. Official Elrah Exclusive Product Collections
        products_data = [
            {
                "name": "Baju Melayu Daytona (2026)",
                "prefix": "BM-DAYTONA",
                "dropship": Decimal("110.00"),
                "srp": Decimal("199.00"),
                "desc": "Koleksi Baju Melayu Flagship 2026 berpotongan Slim Fit moden. Fabrik Crepe Silk Premium berkualiti tinggi yang sejuk, beralun dan 'stretchable'. Didatangkan khas dengan FREE Set Butang Baju Melayu Eksklusif & Pin Rantai Kristal Elrah.",
                "variants": [
                    ("Emerald Green", "S", 25), ("Emerald Green", "M", 40), ("Emerald Green", "L", 35), ("Emerald Green", "XL", 20), ("Emerald Green", "XXL", 10),
                    ("Royal Blue", "S", 20), ("Royal Blue", "M", 30), ("Royal Blue", "L", 30), ("Royal Blue", "XL", 15),
                    ("Maroon", "S", 30), ("Maroon", "M", 45), ("Maroon", "L", 40), ("Maroon", "XL", 25), ("Maroon", "XXL", 12),
                    ("Jet Black", "S", 35), ("Jet Black", "M", 50), ("Jet Black", "L", 45), ("Jet Black", "XL", 30), ("Jet Black", "XXL", 15),
                    ("Champagne Gold", "S", 15), ("Champagne Gold", "M", 25), ("Champagne Gold", "L", 20), ("Champagne Gold", "XL", 10),
                    ("Navy Blue", "S", 25), ("Navy Blue", "M", 35), ("Navy Blue", "L", 30), ("Navy Blue", "XL", 20),
                    ("Dusty Rose", "S", 15), ("Dusty Rose", "M", 20), ("Dusty Rose", "L", 18), ("Dusty Rose", "XL", 8),
                    ("Off White", "S", 20), ("Off White", "M", 30), ("Off White", "L", 25), ("Off White", "XL", 15),
                ]
            },
            {
                "name": "Baju Melayu Modern Fit (2026)",
                "prefix": "BM-MODERN",
                "dropship": Decimal("100.00"),
                "srp": Decimal("189.00"),
                "desc": "Baju Melayu Modern Fit 2026 dengan fabrik High-End Italian Dobby bertekstur mewah. Kain sejuk, tidak mudah berkedut, dan memberikan potongan tampan terletak di badan.",
                "variants": [
                    ("Midnight Blue", "S", 20), ("Midnight Blue", "M", 30), ("Midnight Blue", "L", 25), ("Midnight Blue", "XL", 15),
                    ("Olive Green", "S", 18), ("Olive Green", "M", 25), ("Olive Green", "L", 22), ("Olive Green", "XL", 12),
                    ("Dusty Mint", "S", 15), ("Dusty Mint", "M", 20), ("Dusty Mint", "L", 18), ("Dusty Mint", "XL", 10),
                    ("Pure White", "S", 25), ("Pure White", "M", 35), ("Pure White", "L", 30), ("Pure White", "XL", 20), ("Pure White", "XXL", 10),
                    ("Charcoal Grey", "S", 15), ("Charcoal Grey", "M", 22), ("Charcoal Grey", "L", 20), ("Charcoal Grey", "XL", 10),
                ]
            },
            {
                "name": "Baju Melayu Teluk Belanga Classic Pesak (2026)",
                "prefix": "BM-TELUK",
                "dropship": Decimal("95.00"),
                "srp": Decimal("179.00"),
                "desc": "Sentuhan tradisi Melayu Johor dengan leher Teluk Belanga dan potongan pesak klasik yang selesa. Menggunakan Japanese Cotton Silk lembut dan bernafas.",
                "variants": [
                    ("Baby Blue", "S", 18), ("Baby Blue", "M", 24), ("Baby Blue", "L", 20), ("Baby Blue", "XL", 12),
                    ("Dusty Green", "S", 15), ("Dusty Green", "M", 22), ("Dusty Green", "L", 18), ("Dusty Green", "XL", 10),
                    ("Sage", "S", 12), ("Sage", "M", 18), ("Sage", "L", 15), ("Sage", "XL", 8),
                    ("Soft Peach", "S", 12), ("Soft Peach", "M", 16), ("Soft Peach", "L", 14), ("Soft Peach", "XL", 6),
                    ("Pure White", "S", 20), ("Pure White", "M", 30), ("Pure White", "L", 25), ("Pure White", "XL", 15),
                ]
            },
            {
                "name": "Kurta Hakeem (2025)",
                "prefix": "KRT-HAKEEM",
                "dropship": Decimal("50.00"),
                "srp": Decimal("99.00"),
                "desc": "Kurta moden berkoler Mandarin dengan kancing butang berukir logo Elrah Exclusive. Rekaan kemas dan minimalis untuk digayakan ke pejabat, solat Jumaat, atau majlis kenduri.",
                "variants": [
                    ("Ash Grey", "S", 20), ("Ash Grey", "M", 30), ("Ash Grey", "L", 25), ("Ash Grey", "XL", 15), ("Ash Grey", "XXL", 8),
                    ("Dark Mustard", "S", 15), ("Dark Mustard", "M", 22), ("Dark Mustard", "L", 18), ("Dark Mustard", "XL", 10),
                    ("Maroon", "S", 25), ("Maroon", "M", 35), ("Maroon", "L", 30), ("Maroon", "XL", 20), ("Maroon", "XXL", 10),
                    ("Sage Green", "S", 18), ("Sage Green", "M", 28), ("Sage Green", "L", 24), ("Sage Green", "XL", 12),
                    ("Jet Black", "S", 30), ("Jet Black", "M", 40), ("Jet Black", "L", 35), ("Jet Black", "XL", 25), ("Jet Black", "XXL", 12),
                ]
            },
            {
                "name": "Kurta Rushdy (2025)",
                "prefix": "KRT-RUSHDY",
                "dropship": Decimal("45.00"),
                "srp": Decimal("89.00"),
                "desc": "Kurta potongan santai leher Cekak Musang berserta poket sorok di dada dan sisi. Fabrik Cotton Poly lembut dan anti-panas.",
                "variants": [
                    ("Navy Blue", "S", 20), ("Navy Blue", "M", 28), ("Navy Blue", "L", 25), ("Navy Blue", "XL", 15),
                    ("Terra Cotta", "S", 14), ("Terra Cotta", "M", 20), ("Terra Cotta", "L", 16), ("Terra Cotta", "XL", 8),
                    ("Khaki Brown", "S", 18), ("Khaki Brown", "M", 25), ("Khaki Brown", "L", 20), ("Khaki Brown", "XL", 12),
                    ("Pure White", "S", 22), ("Pure White", "M", 30), ("Pure White", "L", 28), ("Pure White", "XL", 18),
                ]
            },
            {
                "name": "Sampin Songket Tenun Eksklusif",
                "prefix": "SMP-TENUN",
                "dropship": Decimal("65.00"),
                "srp": Decimal("129.00"),
                "desc": "Sampin songket tenun tangan motif bunga penuh warisan Melayu (Ukuran 2.25 meter siap jahit). Kilauan benang emas/perak menaikkan seri busana Melayu anda.",
                "variants": [
                    ("Hitam Emas", "Free Size", 25),
                    ("Hitam Perak", "Free Size", 20),
                    ("Navy Emas", "Free Size", 18),
                    ("Maroon Emas", "Free Size", 15),
                ]
            },
            {
                "name": "Set Butang Baju Melayu & Pin Rantai Signature",
                "prefix": "ACC-SET",
                "dropship": Decimal("20.00"),
                "srp": Decimal("39.00"),
                "desc": "Aksesori lengkap Baju Melayu: 5 butang kristal tahan karat berserta rantai pin kerongsang dada berlogo rasmi Elrah Exclusive.",
                "variants": [
                    ("Gold Swarovski", "Free Size", 40),
                    ("Silver Swarovski", "Free Size", 35),
                    ("Gunmetal Black", "Free Size", 25),
                ]
            }
        ]

        now = timezone.now()
        for pdata in products_data:
            prod, _ = Product.objects.update_or_create(
                sku_prefix=pdata["prefix"],
                defaults={
                    "name": pdata["name"],
                    "dropship_price": pdata["dropship"],
                    "suggested_retail_price": pdata["srp"],
                    "description": pdata["desc"],
                    "is_active": True,
                }
            )
            for colour, size, initial_qty in pdata["variants"]:
                clean_colour = "".join(c for c in colour.upper() if c.isalnum())
                clean_size = "".join(c for c in size.upper() if c.isalnum())
                sku = f"{pdata['prefix']}-{clean_colour}-{clean_size}"
                Variant.objects.update_or_create(
                    product=prod,
                    size=size,
                    colour=colour,
                    defaults={
                        "sku": sku,
                        "stock": initial_qty,
                        "stock_updated_at": now - timedelta(hours=1),  # Verified within 24h
                    }
                )

        self.stdout.write("Created Elrah Exclusive products, collections, and variants.")

        # 4. Sample Customer Orders for dropship1
        v1 = Variant.objects.filter(product__sku_prefix="BM-DAYTONA", colour="Emerald Green", size="L").first()
        v2 = Variant.objects.filter(product__sku_prefix="SMP-TENUN", colour="Hitam Emas").first()
        v3 = Variant.objects.filter(product__sku_prefix="KRT-HAKEEM", colour="Maroon", size="M").first()

        # Order 1: Shipped (Daytona + Sampin)
        if not Order.objects.filter(customer_name="Khairul Azhar").exists() and v1 and v2:
            o1 = place_order(
                dropshipper=ds1,
                customer={
                    "customer_name": "Khairul Azhar",
                    "customer_phone": "0123344556",
                    "address": "No. 88, Jalan Wangsa Melawati 4",
                    "postcode": "53300",
                    "city": "Kuala Lumpur",
                    "state": "W.P. Kuala Lumpur",
                    "notes": "Hantar sebelum Hari Raya",
                },
                items=[
                    {"variant_id": v1.id, "qty": 1, "sell_price": Decimal("199.00")},
                    {"variant_id": v2.id, "qty": 1, "sell_price": Decimal("129.00")},
                ]
            )
            mark_paid(o1, o1.total_cents)
            ship_order(o1, hq_user, "J&T Express", "JNT608821992MY")
            o1.paid_at = now - timedelta(days=2)
            o1.shipped_at = now - timedelta(days=1)
            o1.save()

        # Order 2: Paid (Awaiting HQ shipment: Kurta Hakeem)
        if not Order.objects.filter(customer_name="Amirul Hakim").exists() and v3:
            o2 = place_order(
                dropshipper=ds1,
                customer={
                    "customer_name": "Amirul Hakim",
                    "customer_phone": "0178899112",
                    "address": "Lot 44, Lorong Bayu Indah",
                    "postcode": "88400",
                    "city": "Kota Kinabalu",
                    "state": "Sabah",
                    "notes": "Pakej hadiah",
                },
                items=[
                    {"variant_id": v3.id, "qty": 1, "sell_price": Decimal("99.00")},
                ]
            )
            mark_paid(o2, o2.total_cents)
            o2.paid_at = now - timedelta(hours=3)
            o2.save()

        # Additional competing dropshippers for the sales leaderboard
        ds_megat, _ = User.objects.get_or_create(
            username="megat_elrah",
            defaults={
                "email": "megat@test.com",
                "first_name": "Megat",
                "last_name": "Iskandar",
                "role": User.Role.DROPSHIPPER,
                "status": User.Status.APPROVED,
                "phone": "0123344111",
                "shop_name": "Megat Menswear Melaka",
                "bank_name": "CIMB",
                "bank_account_number": "7012345678",
                "bank_account_holder": "Megat Iskandar",
                "bank_id_number": "920101-04-1234",
            },
        )
        ds_megat.set_password("password123")
        ds_megat.save()

        ds_hafiz, _ = User.objects.get_or_create(
            username="hafiz_bangi",
            defaults={
                "email": "hafiz@test.com",
                "first_name": "Hafiz",
                "last_name": "Rahman",
                "role": User.Role.DROPSHIPPER,
                "status": User.Status.APPROVED,
                "phone": "0134455222",
                "shop_name": "Hafiz Exclusive Bangi",
                "bank_name": "Maybank",
                "bank_account_number": "114012349988",
                "bank_account_holder": "Hafiz bin Rahman",
                "bank_id_number": "940202-10-5678",
            },
        )
        ds_hafiz.set_password("password123")
        ds_hafiz.save()

        ds_zul, _ = User.objects.get_or_create(
            username="zul_busana",
            defaults={
                "email": "zul@test.com",
                "first_name": "Zulkifli",
                "last_name": "Hassan",
                "role": User.Role.DROPSHIPPER,
                "status": User.Status.APPROVED,
                "phone": "0178877665",
                "shop_name": "Zul Busana Shah Alam",
                "bank_name": "Bank Islam",
                "bank_account_number": "120123456789",
                "bank_account_holder": "Zulkifli bin Hassan",
                "bank_id_number": "910303-10-1122",
            },
        )
        ds_zul.set_password("password123")
        ds_zul.save()

        # Orders for Megat (Top #1: 2x Daytona + 2x Modern Fit = RM 776.00)
        v_daytona_black = Variant.objects.filter(product__sku_prefix="BM-DAYTONA", colour="Jet Black", size="M").first()
        v_modern_white = Variant.objects.filter(product__sku_prefix="BM-MODERN", colour="Pure White", size="L").first()
        if not Order.objects.filter(customer_name="Dato' Seri Zulkifli").exists() and v_daytona_black and v_modern_white:
            om1 = place_order(
                dropshipper=ds_megat,
                customer={
                    "customer_name": "Dato' Seri Zulkifli",
                    "customer_phone": "0199998888",
                    "address": "No. 1, Jalan Bukit Tunku",
                    "postcode": "50480",
                    "city": "Kuala Lumpur",
                    "state": "W.P. Kuala Lumpur",
                    "notes": "VIP Customer",
                },
                items=[
                    {"variant_id": v_daytona_black.id, "qty": 2, "sell_price": Decimal("199.00")},
                    {"variant_id": v_modern_white.id, "qty": 2, "sell_price": Decimal("189.00")},
                ]
            )
            mark_paid(om1, om1.total_cents)
            om1.paid_at = now - timedelta(days=1)
            om1.save()

        # Orders for Hafiz (#2: 2x Daytona + 1x Kurta Hakeem = RM 497.00)
        v_daytona_navy = Variant.objects.filter(product__sku_prefix="BM-DAYTONA", colour="Navy Blue", size="L").first()
        v_kurta_black = Variant.objects.filter(product__sku_prefix="KRT-HAKEEM", colour="Jet Black", size="L").first()
        if not Order.objects.filter(customer_name="Ustaz Syamsul").exists() and v_daytona_navy and v_kurta_black:
            oh1 = place_order(
                dropshipper=ds_hafiz,
                customer={
                    "customer_name": "Ustaz Syamsul",
                    "customer_phone": "0133334444",
                    "address": "Surau Al-Falah, Seksyen 3",
                    "postcode": "43650",
                    "city": "Bangi",
                    "state": "Selangor",
                },
                items=[
                    {"variant_id": v_daytona_navy.id, "qty": 2, "sell_price": Decimal("199.00")},
                    {"variant_id": v_kurta_black.id, "qty": 1, "sell_price": Decimal("99.00")},
                ]
            )
            mark_paid(oh1, oh1.total_cents)
            oh1.paid_at = now - timedelta(hours=12)
            oh1.save()

        # Orders for Zul Busana (#4: 1x Teluk Belanga + 1x Kurta Rushdy = RM 268.00)
        v_teluk_blue = Variant.objects.filter(product__sku_prefix="BM-TELUK", colour="Baby Blue", size="M").first()
        v_rushdy_white = Variant.objects.filter(product__sku_prefix="KRT-RUSHDY", colour="Pure White", size="M").first()
        if not Order.objects.filter(customer_name="Tuan Razak").exists() and v_teluk_blue and v_rushdy_white:
            oz1 = place_order(
                dropshipper=ds_zul,
                customer={
                    "customer_name": "Tuan Razak",
                    "customer_phone": "0188887777",
                    "address": "No 25 Jalan Platinum 7/42",
                    "postcode": "40000",
                    "city": "Shah Alam",
                    "state": "Selangor",
                },
                items=[
                    {"variant_id": v_teluk_blue.id, "qty": 1, "sell_price": Decimal("179.00")},
                    {"variant_id": v_rushdy_white.id, "qty": 1, "sell_price": Decimal("89.00")},
                ]
            )
            mark_paid(oz1, oz1.total_cents)
            oz1.paid_at = now - timedelta(hours=8)
            oz1.save()

        self.stdout.write(self.style.SUCCESS("Elrah Exclusive demo data seed completed successfully!"))
