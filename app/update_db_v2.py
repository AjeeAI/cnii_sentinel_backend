from sqlalchemy import text
from app.database import engine

def update_schema_v2():
    with engine.connect() as conn:
        print("🔧 Initializing Sentinel Database Upgrade (v2)...")
        
        # 1. Add source_title column
        try:
            conn.execute(text("ALTER TABLE risk_records ADD COLUMN source_title VARCHAR(255) NULL;"))
            print("✅ Added 'source_title' column.")
        except Exception as e:
            print(f"⚠️ Skipping 'source_title' (might already exist): {e}")

        # 2. Add published_date column
        try:
            conn.execute(text("ALTER TABLE risk_records ADD COLUMN published_date VARCHAR(50) NULL;"))
            print("✅ Added 'published_date' column.")
        except Exception as e:
            print(f"⚠️ Skipping 'published_date' (might already exist): {e}")
            
        conn.commit()
        print("🎉 Database schema is now synchronized with the new architecture!")

if __name__ == "__main__":
    update_schema_v2()