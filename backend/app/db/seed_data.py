from decimal import Decimal
from sqlalchemy import select
from app.core.security import hash_password
from app.db.database import SessionLocal
from app.models.category import Category
from app.models.product import Product
from app.models.user import User


def seed_database(force: bool = False):
    from app.core.config import settings
    if settings.is_production and not force:
        print("Notice: Demo account seeding is disabled in production environments.")
        return

    db = SessionLocal()
    try:
        # Seed Default Admin & Customer if not present
        admin_user = db.scalar(select(User).where(User.email == "admin@ecommerce.com"))
        if not admin_user:
            admin_user = User(
                name="Admin User",
                email="admin@ecommerce.com",
                password_hash=hash_password("admin123"),
                role="admin",
                phone="+85512345678",
                is_active=True,
            )
            db.add(admin_user)
            db.commit()
            print("Seeded default admin user: admin@ecommerce.com / admin123")

        customer_user = db.scalar(select(User).where(User.email == "customer@ecommerce.com"))
        if not customer_user:
            customer_user = User(
                name="Customer Demo",
                email="customer@ecommerce.com",
                password_hash=hash_password("password123"),
                role="customer",
                phone="+85598765432",
                is_active=True,
            )
            db.add(customer_user)
            db.commit()
            print("Seeded default customer user: customer@ecommerce.com / password123")

        # Seed Seller 1: Alex Rivera (TechGadgets Official Store)
        seller_user_1 = db.scalar(select(User).where(User.email == "seller@ecommerce.com"))
        if not seller_user_1:
            seller_user_1 = User(
                name="Alex Rivera",
                email="seller@ecommerce.com",
                password_hash=hash_password("seller123"),
                role="seller",
                phone="+85512999001",
                is_active=True,
            )
            db.add(seller_user_1)
            db.commit()
            print("Seeded default seller 1: seller@ecommerce.com / seller123")

        # Seed Seller 2: Sarah Chen (Urban Chic Boutique)
        seller_user_2 = db.scalar(select(User).where(User.email == "seller2@ecommerce.com"))
        if not seller_user_2:
            seller_user_2 = User(
                name="Sarah Chen",
                email="seller2@ecommerce.com",
                password_hash=hash_password("seller123"),
                role="seller",
                phone="+85512999002",
                is_active=True,
            )
            db.add(seller_user_2)
            db.commit()
            print("Seeded default seller 2: seller2@ecommerce.com / seller123")

        # Ensure Seller table records exist
        from app.models.seller import Seller
        seller_record_1 = db.scalar(select(Seller).where(Seller.email == "seller@ecommerce.com"))
        if not seller_record_1:
            seller_record_1 = Seller(
                user_id=seller_user_1.id,
                name="TechGadgets Official Store",
                owner_name="Alex Rivera",
                email="seller@ecommerce.com",
                phone="+85512999001",
                address="Building 4, Monivong Blvd, Phnom Penh",
                description="Authorized retailer for premier tech accessories and smart electronics.",
                status="Active",
                rating=Decimal("4.90"),
                products_count=5,
            )
            db.add(seller_record_1)
            db.commit()
            print("Seeded Seller record: TechGadgets Official Store")

        seller_record_2 = db.scalar(select(Seller).where(Seller.email == "seller2@ecommerce.com"))
        if not seller_record_2:
            seller_record_2 = Seller(
                user_id=seller_user_2.id,
                name="Urban Chic Boutique",
                owner_name="Sarah Chen",
                email="seller2@ecommerce.com",
                phone="+85512999002",
                address="Norodom Blvd, BKK1, Phnom Penh",
                description="Modern street fashion, casual apparel, and luxury lifestyle accessories.",
                status="Active",
                rating=Decimal("4.80"),
                products_count=4,
            )
            db.add(seller_record_2)
            db.commit()
            print("Seeded Seller record: Urban Chic Boutique")

        # Check if categories already seeded
        existing_categories = db.scalars(select(Category)).all()
        if existing_categories:
            print("Database already contains categories/products. Skipping product seed.")
            return

        print("Seeding categories and products...")

        # 1. Create Categories
        categories_data = [
            {
                "name": "Shoes",
                "description": "Running sneakers, casual trainers, and luxury footwear.",
                "image": "assets/images/products/shoe.png",
            },
            {
                "name": "Electronics",
                "description": "Smart gadgets, headphones, wearables, and audio gear.",
                "image": "assets/images/products/headphone.png",
            },
            {
                "name": "Fashion",
                "description": "Trendy apparel, streetwear, jackets, and everyday wear.",
                "image": "assets/images/products/hoodie.png",
            },
            {
                "name": "Accessories",
                "description": "Bags, wallets, watches, and smart accessories.",
                "image": "assets/images/products/watch.png",
            },
            {
                "name": "Beauty",
                "description": "Skincare, perfumes, organic oils, and cosmetics.",
                "image": "assets/images/products/skincare.png",
            },
        ]

        category_map = {}
        for cat_data in categories_data:
            cat = Category(
                name=cat_data["name"],
                description=cat_data["description"],
                image=cat_data["image"],
                is_active=True,
            )
            db.add(cat)
            db.flush()
            category_map[cat.name] = cat.id

        # 2. Create Products
        products_data = [
            {
                "category": "Shoes",
                "name": "Nike Air Max 270",
                "description": "The Nike Air Max 270 delivers unmatched all-day comfort with a large Air unit in the heel and a sleek, running-inspired design.",
                "price": Decimal("159.99"),
                "discount_price": Decimal("139.99"),
                "stock": 25,
                "rating": Decimal("4.80"),
                "image_url": "assets/images/products/nike_airmax.png",
            },
            {
                "category": "Shoes",
                "name": "Adidas Ultraboost Light",
                "description": "Experience epic energy return with our lightest Ultraboost ever made, engineered with lightweight BOOST material.",
                "price": Decimal("189.99"),
                "discount_price": Decimal("169.99"),
                "stock": 18,
                "rating": Decimal("4.70"),
                "image_url": "assets/images/products/adidas_ultraboost.png",
            },
            {
                "category": "Shoes",
                "name": "Puma RS-X Efekt",
                "description": "Progressive aesthetic meets chunky comfort with premium suede overlays and bold color blocking.",
                "price": Decimal("119.99"),
                "discount_price": None,
                "stock": 30,
                "rating": Decimal("4.50"),
                "image_url": "assets/images/products/puma_rsx.png",
            },
            {
                "category": "Shoes",
                "name": "New Balance 574 Legacy",
                "description": "The most iconic New Balance silhouette crafted with ENCAP midsole cushioning for durable comfort.",
                "price": Decimal("99.99"),
                "discount_price": Decimal("84.99"),
                "stock": 40,
                "rating": Decimal("4.60"),
                "image_url": "assets/images/products/new_balance.png",
            },
            {
                "category": "Electronics",
                "name": "Sony WH-1000XM5 Wireless Headphones",
                "description": "Industry-leading noise cancellation with two processors, 8 microphones, and ultra-comfortable lightweight design.",
                "price": Decimal("399.99"),
                "discount_price": Decimal("349.99"),
                "stock": 15,
                "rating": Decimal("4.90"),
                "image_url": "assets/images/products/sony_headphones.png",
            },
            {
                "category": "Electronics",
                "name": "Apple Watch Series 9 GPS",
                "description": "Powerful sensors for health, safety and fitness insights with the brilliant Always-On Retina display.",
                "price": Decimal("399.00"),
                "discount_price": None,
                "stock": 12,
                "rating": Decimal("4.85"),
                "image_url": "assets/images/products/apple_watch.png",
            },
            {
                "category": "Electronics",
                "name": "Samsung Galaxy Buds2 Pro",
                "description": "24-bit Hi-Fi sound quality with intelligent Active Noise Cancellation and studio-grade voice clarity.",
                "price": Decimal("229.99"),
                "discount_price": Decimal("179.99"),
                "stock": 20,
                "rating": Decimal("4.65"),
                "image_url": "assets/images/products/galaxy_buds.png",
            },
            {
                "category": "Fashion",
                "name": "Classic Vintage Denim Jacket",
                "description": "Timeless relaxed-fit trucker denim jacket crafted from 100% durable heavyweight washed cotton.",
                "price": Decimal("79.99"),
                "discount_price": Decimal("59.99"),
                "stock": 35,
                "rating": Decimal("4.55"),
                "image_url": "assets/images/products/denim_jacket.png",
            },
            {
                "category": "Fashion",
                "name": "Heavyweight Fleece Hoodie",
                "description": "Ultra-soft brushed fleece interior with a double-layered hood and front kangaroo pocket.",
                "price": Decimal("54.99"),
                "discount_price": None,
                "stock": 50,
                "rating": Decimal("4.75"),
                "image_url": "assets/images/products/fleece_hoodie.png",
            },
            {
                "category": "Fashion",
                "name": "Modern Slim-Fit Chinos",
                "description": "Comfort stretch chino trousers featuring a clean tapered silhouette for everyday office and casual wear.",
                "price": Decimal("49.99"),
                "discount_price": Decimal("39.99"),
                "stock": 28,
                "rating": Decimal("4.40"),
                "image_url": "assets/images/products/chinos.png",
            },
            {
                "category": "Accessories",
                "name": "Minimalist Full-Grain Leather Wallet",
                "description": "Slim bifold wallet with RFID blocking technology, 8 card slots, and genuine top-grain leather finish.",
                "price": Decimal("45.00"),
                "discount_price": Decimal("35.00"),
                "stock": 60,
                "rating": Decimal("4.80"),
                "image_url": "assets/images/products/leather_wallet.png",
            },
            {
                "category": "Beauty",
                "name": "Organic Botanical Face Oil",
                "description": "Cold-pressed nourishing facial oil infused with rosehip, jojoba, and vitamin E for glowing hydration.",
                "price": Decimal("38.00"),
                "discount_price": None,
                "stock": 45,
                "rating": Decimal("4.90"),
                "image_url": "assets/images/products/face_oil.png",
            },
        ]

        for p_data in products_data:
            cat_id = category_map[p_data["category"]]
            prod = Product(
                category_id=cat_id,
                name=p_data["name"],
                description=p_data["description"],
                price=p_data["price"],
                discount_price=p_data["discount_price"],
                stock=p_data["stock"],
                rating=p_data["rating"],
                image_url=p_data["image_url"],
                is_active=True,
            )
            db.add(prod)

        db.commit()
        print("Successfully seeded 5 categories and 12 products into database!")

        # Explicitly seed default promotional coupons if needed
        from app.services.coupon_service import CouponService
        seeded_coupons = CouponService.seed_default_coupons(db)
        if seeded_coupons:
            print(f"Successfully seeded {seeded_coupons} promotional coupons into database!")
    except Exception as e:
        db.rollback()
        print(f"Error during seeding: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()

