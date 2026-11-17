from app.db.database import Base, engine
import app.models  # Ensures all models are registered in Base.metadata


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    create_tables()
    print("Database tables created/verified successfully!")
