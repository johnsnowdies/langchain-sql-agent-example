import random
import os
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from datetime import date, timedelta
from app.models import User, Product, Order
from sqlalchemy.exc import IntegrityError

# Database configuration
db_url = f'postgresql://{os.getenv("DB_USER")}:{os.getenv("DB_PASS")}@{os.getenv("DB_HOST")}/{os.getenv("DB_NAME")}'
engine = create_engine(db_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def generate_random_date(start_date, end_date):
    time_between_dates = end_date - start_date
    days_between_dates = time_between_dates.days
    random_number_of_days = random.randrange(days_between_dates)
    return start_date + timedelta(days=random_number_of_days)


def get_db():
    db = SessionLocal()
    try:
        return db
    finally:
        db.close()


def load_fixtures():
    db = get_db()
    try:
        # Check if data already exists
        result = db.execute(select(User).limit(1))
        if result.scalar_one_or_none() is not None:
            print("Fixtures already loaded. Skipping...")
            return

        # Add users
        users = [
            User(email=f'user{i}@example.com', full_name=f'User {i}')
            for i in range(1, 10001)
        ]
        db.add_all(users)
        db.commit()
        print("10,000 users added successfully.")

        # Add products
        products = [
            Product(name=f'Product {i}')
            for i in range(1, 1001)
        ]
        db.add_all(products)
        db.commit()
        print("1,000 products added successfully.")

        # Add orders
        start_date = date(2023, 1, 1)
        end_date = date(2023, 12, 31)

        batch_size = 1000
        total_orders = 100000

        for i in range(0, total_orders, batch_size):
            orders = [
                Order(
                    date=generate_random_date(start_date, end_date),
                    product_id=random.randint(1, 1000),
                    quantity=random.randint(1, 10),
                    amount=round(random.uniform(10.00, 1000.00), 2),
                    user_id=random.randint(1, 10000)
                )
                for _ in range(batch_size)
            ]
            db.add_all(orders)
            try:
                db.commit()
                print(f"Added orders {i+1} to {i+batch_size}")
            except IntegrityError:
                db.rollback()
                print(f"Error adding orders {i+1} to {i+batch_size}, skipping batch")

        print("100,000 orders added successfully.")
        print("All fixtures loaded successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error loading fixtures: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    load_fixtures()
