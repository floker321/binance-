import os
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv('DATABASE_URL')

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class AlertHistory(Base):
    __tablename__ = 'alert_history'
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.now, index=True)
    ticker = Column(String, index=True)
    timeframe = Column(String)
    alert_type = Column(String)
    zone_type = Column(String)
    zone_price = Column(Float)
    current_price = Column(Float)
    zone_touches = Column(Integer)
    
class Watchlist(Base):
    __tablename__ = 'watchlist'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, default='default_user', index=True)
    ticker = Column(String, index=True)
    added_at = Column(DateTime, default=datetime.now)
    active = Column(Boolean, default=True)

class UserPreferences(Base):
    __tablename__ = 'user_preferences'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, default='default_user', unique=True, index=True)
    webhook_url = Column(String, nullable=True)
    custom_zones = Column(JSON, default={})
    settings = Column(JSON, default={})
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created successfully")
    except Exception as e:
        logger.error(f"❌ Error creating database tables: {e}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def add_alert_to_db(alert_data):
    db = SessionLocal()
    try:
        alert = AlertHistory(**alert_data)
        db.add(alert)
        db.commit()
        logger.info(f"✅ Alert saved to database: {alert_data['ticker']} {alert_data['alert_type']}")
    except Exception as e:
        logger.error(f"❌ Error saving alert: {e}")
        db.rollback()
    finally:
        db.close()

def get_alert_history(ticker=None, limit=50):
    db = SessionLocal()
    try:
        query = db.query(AlertHistory).order_by(AlertHistory.timestamp.desc())
        if ticker:
            query = query.filter(AlertHistory.ticker == ticker)
        alerts = query.limit(limit).all()
        return alerts
    except Exception as e:
        logger.error(f"❌ Error fetching alerts: {e}")
        return []
    finally:
        db.close()

def add_ticker_to_watchlist(ticker, user_id='default_user'):
    db = SessionLocal()
    try:
        existing = db.query(Watchlist).filter(
            Watchlist.ticker == ticker,
            Watchlist.user_id == user_id,
            Watchlist.active == True
        ).first()
        
        if not existing:
            watchlist_item = Watchlist(ticker=ticker, user_id=user_id)
            db.add(watchlist_item)
            db.commit()
            logger.info(f"✅ Added {ticker} to watchlist")
            return True
        return False
    except Exception as e:
        logger.error(f"❌ Error adding to watchlist: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def remove_ticker_from_watchlist(ticker, user_id='default_user'):
    db = SessionLocal()
    try:
        db.query(Watchlist).filter(
            Watchlist.ticker == ticker,
            Watchlist.user_id == user_id
        ).update({Watchlist.active: False})
        db.commit()
        logger.info(f"✅ Removed {ticker} from watchlist")
        return True
    except Exception as e:
        logger.error(f"❌ Error removing from watchlist: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def get_watchlist(user_id='default_user'):
    db = SessionLocal()
    try:
        items = db.query(Watchlist).filter(
            Watchlist.user_id == user_id,
            Watchlist.active == True
        ).order_by(Watchlist.added_at).all()
        return [item.ticker for item in items]
    except Exception as e:
        logger.error(f"❌ Error fetching watchlist: {e}")
        return []
    finally:
        db.close()

def get_or_create_preferences(user_id='default_user'):
    db = SessionLocal()
    try:
        prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
        if not prefs:
            prefs = UserPreferences(user_id=user_id)
            db.add(prefs)
            db.commit()
            db.refresh(prefs)
        return prefs
    except Exception as e:
        logger.error(f"❌ Error getting preferences: {e}")
        return None
    finally:
        db.close()

def update_preferences(user_id, webhook_url=None, custom_zones=None, settings=None):
    db = SessionLocal()
    try:
        prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
        if not prefs:
            prefs = UserPreferences(user_id=user_id)
            db.add(prefs)
        
        if webhook_url is not None:
            prefs.webhook_url = webhook_url
        if custom_zones is not None:
            prefs.custom_zones = custom_zones
        if settings is not None:
            prefs.settings = settings
        
        db.commit()
        logger.info(f"✅ Updated preferences for {user_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Error updating preferences: {e}")
        db.rollback()
        return False
    finally:
        db.close()
