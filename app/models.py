from sqlalchemy import Column, Date, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    full_name = Column(String)

    orders = relationship("Order", back_populates="user")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)

    orders = relationship("Order", back_populates="product")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date)
    quantity = Column(Integer)
    amount = Column(Numeric(10, 2))

    product_id = Column(Integer, ForeignKey("products.id"))
    user_id = Column(Integer, ForeignKey("users.id"))

    product = relationship("Product", back_populates="orders")
    user = relationship("User", back_populates="orders")

    # Add indexes for foreign keys
    __table_args__ = (
        Index('ix_orders_product_id', product_id),
        Index('ix_orders_user_id', user_id),
    )
