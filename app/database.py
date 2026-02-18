from sqlalchemy import Float, create_engine, Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# Format: mysql+pymysql://user:password@host:port/db_name
# Ensure you have created the database 'sentinel_db' in MySQL first
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:password@localhost:3306/sentinel_db")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. Build the full path to the certificate
ssl_cert_path = os.path.join(BASE_DIR, "isrgrootx1.pem")


engine = create_engine(
    DATABASE_URL,
    connect_args={
        "ssl": {
            "ca": ssl_cert_path
        }
    },
    
    pool_pre_ping=True, # <--- Add this line
    pool_recycle=3600
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class PatrolReport(Base):
    __tablename__ = "patrol_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    summary = Column(Text)
    
    # Relationship to individual risks
    risks = relationship("RiskRecord", back_populates="report")

# database.py
class RiskRecord(Base):
    __tablename__ = "risk_records"
    
    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("patrol_reports.id"))
    risk_level = Column(String(50))
    risk_score = Column(Integer)
    location = Column(String(255))
    
    # --- NEW COLUMNS ---
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    threat_type = Column(String(255))
    recommended_action = Column(Text)
    summary = Column(Text)
    report = relationship("PatrolReport", back_populates="risks")

# Create tables
def init_db():
    Base.metadata.create_all(bind=engine)