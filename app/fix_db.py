from sqlalchemy import text
from backend.app.database import engine

def add_columns():
    with engine.connect() as conn:
        print("🔧 Adding latitude and longitude columns...")
        try:
            # 1. Add latitude
            conn.execute(text("ALTER TABLE risk_records ADD COLUMN latitude FLOAT NULL;"))
            print("✅ Added 'latitude' column.")
        except Exception as e:
            print(f"⚠️ Could not add latitude (might already exist): {e}")

        try:
            # 2. Add longitude
            conn.execute(text("ALTER TABLE risk_records ADD COLUMN longitude FLOAT NULL;"))
            print("✅ Added 'longitude' column.")
        except Exception as e:
            print(f"⚠️ Could not add longitude (might already exist): {e}")
            
        conn.commit()
        print("🎉 Database schema updated successfully!")

if __name__ == "__main__":
    add_columns()