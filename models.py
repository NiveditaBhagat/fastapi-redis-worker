from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from database import Base



class Orders(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    product: Mapped[str] = mapped_column(String(100), index=True)
    amount: Mapped[int]
    status: Mapped[str] = mapped_column(String(50))
