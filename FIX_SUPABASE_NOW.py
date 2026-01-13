"""
FIX SUPABASE DATABASE - WORKING VERSION
Removes placeholder values from Supabase
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

def fix_supabase_now():
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("❌ ERROR: DATABASE_URL not found in .env!")
        return
    
    print("\n" + "="*70)
    print("🚨 FIXING SUPABASE DATABASE")
    print("="*70)
    
    engine = create_engine(database_url)
    
    with engine.connect() as conn:
        # Show current values
        print("\n📋 Current values:")
        result = conn.execute(text("SELECT key, value FROM settings WHERE key IN ('bot_channel_link', 'bot_owner_username')"))
        rows = result.fetchall()
        
        for row in rows:
            print(f"  {row[0]}: {row[1]}")
        
        # DELETE placeholders
        print("\n🗑️ Removing placeholders...")
        
        result = conn.execute(text("""
            DELETE FROM settings 
            WHERE key = 'bot_channel_link' 
            AND (value LIKE '%yourchannel%' OR value LIKE '%akhilportal%')
        """))
        print(f"  Channel links deleted: {result.rowcount}")
        
        result = conn.execute(text("""
            DELETE FROM settings 
            WHERE key = 'bot_owner_username' 
            AND (value LIKE '%yourchannel%' OR value LIKE '%akhilportal%')
        """))
        print(f"  Owner usernames deleted: {result.rowcount}")
        
        conn.commit()
    
    print("\n✅ DONE! Supabase cleaned!")
    print("="*70)

if __name__ == "__main__":
    fix_supabase_now()
