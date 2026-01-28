"""
Database Module for Discord Mind Matrix Bot
Uses SQLite for local storage - no external database needed!
"""

import os
import logging
import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("database")

# Database file stored in project folder
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "student_data.db")


class Database:
    """SQLite Database handler for local storage"""
    
    def __init__(self):
        self.db_path = DB_PATH
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
    
    async def connect(self):
        """Initialize the database and create tables"""
        try:
            await self._create_tables()
            logger.info(f"SQLite database initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    async def close(self):
        """Placeholder for compatibility - SQLite doesn't need connection pool closing"""
        logger.info("Database closed")
    
    async def _get_connection(self):
        """Get a database connection"""
        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row
        return conn
    
    async def _create_tables(self):
        """Create required tables if they don't exist"""
        async with aiosqlite.connect(self.db_path) as conn:
            # Students table - Your main student registry
            # email is UNIQUE - prevents duplicate students
            # discord_id is UNIQUE - prevents one student verifying multiple accounts
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS students (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    name TEXT,
                    university TEXT,
                    course TEXT NOT NULL,
                    batch TEXT,
                    discord_id INTEGER UNIQUE,
                    is_verified INTEGER DEFAULT 0,
                    verified_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Add batch column if it doesn't exist (for existing databases)
            try:
                await conn.execute("ALTER TABLE students ADD COLUMN batch TEXT")
                logger.info("Added 'batch' column to existing database")
            except Exception:
                pass  # Column already exists
            
            # Add university column if it doesn't exist (for existing databases)
            try:
                await conn.execute("ALTER TABLE students ADD COLUMN university TEXT")
                logger.info("Added 'university' column to existing database")
            except Exception:
                pass  # Column already exists
            
            # OTP storage table - Temporary OTP codes
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS otp_codes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL,
                    code TEXT NOT NULL,
                    discord_id INTEGER NOT NULL,
                    attempts INTEGER DEFAULT 0,
                    expires_at TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Verification logs - For audit trail
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS verification_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT,
                    discord_id INTEGER,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    details TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await conn.commit()
            logger.info("Database tables verified/created")
    
    # ============================================
    # STUDENT OPERATIONS
    # ============================================
    async def get_student_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get student record by email address"""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM students WHERE LOWER(email) = LOWER(?)",
                (email,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def get_student_by_discord_id(self, discord_id: int) -> Optional[Dict[str, Any]]:
        """Get student record by Discord ID"""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM students WHERE discord_id = ?",
                (discord_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def is_email_already_verified(self, email: str) -> bool:
        """Check if email is already linked to a Discord account"""
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                """
                SELECT discord_id FROM students 
                WHERE LOWER(email) = LOWER(?) AND discord_id IS NOT NULL
                """,
                (email,)
            )
            result = await cursor.fetchone()
            return result is not None
    
    async def is_discord_id_used(self, discord_id: int) -> bool:
        """Check if this Discord ID is already linked to any email"""
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT id FROM students WHERE discord_id = ?",
                (discord_id,)
            )
            result = await cursor.fetchone()
            return result is not None
    
    async def verify_student(self, email: str, discord_id: int) -> bool:
        """Mark a student as verified and link their Discord ID"""
        async with aiosqlite.connect(self.db_path) as conn:
            try:
                # First check if discord_id is already used
                cursor = await conn.execute(
                    "SELECT id FROM students WHERE discord_id = ?",
                    (discord_id,)
                )
                if await cursor.fetchone():
                    logger.warning(f"Discord ID {discord_id} already linked to another account")
                    return False
                
                await conn.execute(
                    """
                    UPDATE students 
                    SET discord_id = ?, is_verified = 1, verified_at = ?
                    WHERE LOWER(email) = LOWER(?)
                    """,
                    (discord_id, datetime.utcnow().isoformat(), email)
                )
                await conn.commit()
                logger.info(f"Student verified: {email} -> Discord ID {discord_id}")
                return True
            except Exception as e:
                logger.warning(f"Verification failed for {email}: {e}")
                return False
    
    async def unverify_student(self, discord_id: int) -> bool:
        """Remove verification from a student by Discord ID"""
        async with aiosqlite.connect(self.db_path) as conn:
            try:
                await conn.execute(
                    "UPDATE students SET discord_id = NULL, is_verified = 0, verified_at = NULL WHERE discord_id = ?",
                    (discord_id,)
                )
                await conn.commit()
                logger.info(f"Student unverified: Discord ID {discord_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to unverify Discord ID {discord_id}: {e}")
                return False
    
    async def get_student_course(self, email: str) -> Optional[str]:
        """Get the course name for a student"""
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT course FROM students WHERE LOWER(email) = LOWER(?)",
                (email,)
            )
            row = await cursor.fetchone()
            return row[0] if row else None
    
    async def get_student_batch(self, email: str) -> Optional[str]:
        """Get the batch name for a student"""
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT batch FROM students WHERE LOWER(email) = LOWER(?)",
                (email,)
            )
            row = await cursor.fetchone()
            return row[0] if row else None
    
    async def get_student_course_and_batch(self, email: str) -> tuple[Optional[str], Optional[str]]:
        """Get both course and batch for a student"""
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT course, batch FROM students WHERE LOWER(email) = LOWER(?)",
                (email,)
            )
            row = await cursor.fetchone()
            if row:
                return (row[0], row[1])
            return (None, None)
    
    async def get_student_university_course_batch(self, email: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """Get university, course and batch for a student"""
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT university, course, batch FROM students WHERE LOWER(email) = LOWER(?)",
                (email,)
            )
            row = await cursor.fetchone()
            if row:
                return (row[0], row[1], row[2])
            return (None, None, None)
    
    # ============================================
    # OTP OPERATIONS
    # ============================================
    async def store_otp(self, email: str, code: str, discord_id: int, expiry_minutes: int = 5):
        """Store a new OTP code"""
        expires_at = (datetime.utcnow() + timedelta(minutes=expiry_minutes)).isoformat()
        async with aiosqlite.connect(self.db_path) as conn:
            # Delete any existing OTP for this email/discord_id
            await conn.execute(
                "DELETE FROM otp_codes WHERE LOWER(email) = LOWER(?) OR discord_id = ?",
                (email, discord_id)
            )
            # Insert new OTP
            await conn.execute(
                """
                INSERT INTO otp_codes (email, code, discord_id, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (email, code, discord_id, expires_at)
            )
            await conn.commit()
            logger.info(f"OTP stored for {email}, expires at {expires_at}")
    
    async def verify_otp(self, discord_id: int, code: str) -> Dict[str, Any]:
        """
        Verify an OTP code
        Returns: {"valid": bool, "email": str or None, "error": str or None}
        """
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT email, code, attempts, expires_at 
                FROM otp_codes WHERE discord_id = ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (discord_id,)
            )
            row = await cursor.fetchone()
            
            if not row:
                return {"valid": False, "email": None, "error": "No OTP found. Please request a new one."}
            
            email = row["email"]
            stored_code = row["code"]
            attempts = row["attempts"]
            expires_at = datetime.fromisoformat(row["expires_at"])
            
            # Check expiration
            if datetime.utcnow() > expires_at:
                await conn.execute("DELETE FROM otp_codes WHERE discord_id = ?", (discord_id,))
                await conn.commit()
                return {"valid": False, "email": email, "error": "OTP expired. Please request a new one."}
            
            # Check attempts
            if attempts >= 3:
                await conn.execute("DELETE FROM otp_codes WHERE discord_id = ?", (discord_id,))
                await conn.commit()
                return {"valid": False, "email": email, "error": "Too many failed attempts. Please request a new OTP."}
            
            # Verify code
            if code != stored_code:
                await conn.execute(
                    "UPDATE otp_codes SET attempts = attempts + 1 WHERE discord_id = ?",
                    (discord_id,)
                )
                await conn.commit()
                remaining = 2 - attempts
                return {"valid": False, "email": email, "error": f"Invalid OTP. {remaining} attempts remaining."}
            
            # OTP is valid - delete it
            await conn.execute("DELETE FROM otp_codes WHERE discord_id = ?", (discord_id,))
            await conn.commit()
            return {"valid": True, "email": email, "error": None}
    
    async def get_pending_otp(self, discord_id: int) -> Optional[Dict[str, Any]]:
        """Check if user has a pending OTP request"""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT email, expires_at, created_at 
                FROM otp_codes WHERE discord_id = ?
                """,
                (discord_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    # ============================================
    # LOGGING OPERATIONS
    # ============================================
    async def log_verification_action(
        self, 
        email: Optional[str], 
        discord_id: int, 
        action: str, 
        status: str, 
        details: str = None
    ):
        """Log a verification action for audit purposes"""
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                INSERT INTO verification_logs (email, discord_id, action, status, details)
                VALUES (?, ?, ?, ?, ?)
                """,
                (email, discord_id, action, status, details)
            )
            await conn.commit()
    
    # ============================================
    # ADMIN OPERATIONS
    # ============================================
    async def get_verification_stats(self) -> Dict[str, int]:
        """Get verification statistics"""
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute("SELECT COUNT(*) FROM students")
            total = (await cursor.fetchone())[0]
            
            cursor = await conn.execute("SELECT COUNT(*) FROM students WHERE is_verified = 1")
            verified = (await cursor.fetchone())[0]
            
            cursor = await conn.execute("SELECT COUNT(*) FROM otp_codes")
            pending = (await cursor.fetchone())[0]
            
            return {
                "total_students": total or 0,
                "verified": verified or 0,
                "unverified": (total or 0) - (verified or 0),
                "pending_otps": pending or 0
            }
    
    async def add_student(self, email: str, name: str, course: str, batch: str = "", university: str = "") -> bool:
        """Add a new student to the database (supports 5-column CSV format with university)"""
        async with aiosqlite.connect(self.db_path) as conn:
            try:
                await conn.execute(
                    """
                    INSERT INTO students (email, name, university, course, batch)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (email, name, university, course, batch)
                )
                await conn.commit()
                return True
            except Exception as e:
                logger.warning(f"Student already exists or error: {email} - {e}")
                return False
    
    async def bulk_add_students(self, students: list) -> Dict[str, int]:
        """
        Bulk add students from a list
        students: list of tuples (email, name, course)
        """
        added = 0
        skipped = 0
        
        async with aiosqlite.connect(self.db_path) as conn:
            for email, name, course in students:
                try:
                    await conn.execute(
                        """
                        INSERT OR IGNORE INTO students (email, name, course)
                        VALUES (?, ?, ?)
                        """,
                        (email, name, course)
                    )
                    if conn.total_changes > 0:
                        added += 1
                    else:
                        skipped += 1
                except Exception:
                    skipped += 1
            await conn.commit()
        
        return {"added": added, "skipped": skipped}
    
    # ============================================
    # ADDITIONAL ADMIN OPERATIONS
    # ============================================
    async def get_all_students(self, limit: int = 100) -> list:
        """Get all students (for admin view)"""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM students ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def get_verified_students(self) -> list:
        """Get all verified students"""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM students WHERE is_verified = 1 ORDER BY verified_at DESC"
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


# Global database instance
db = Database()


async def init_database():
    """Initialize the database connection"""
    await db.connect()


async def close_database():
    """Close the database connection"""
    await db.close()
