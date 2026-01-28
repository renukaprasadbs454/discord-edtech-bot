"""
CSV Import Script for Discord Mind Matrix Bot
Run this script to import your student data from CSV file

Usage:
    python import_csv.py

Make sure your CSV file (students.csv) is in the 'data' folder with columns:
    name, email, university, course, batch

Example:
    Name,Email id,University,Course,Batch name
    Joshya,joshya@clinf.com,VTU,Android App Development,Nomads
    Pragati,pragati@clinf.com,GTU,Data Analytics,Pioneers
"""

import sqlite3
import csv
import os

# Database and CSV paths
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.path.join(DATA_DIR, "student_data.db")
CSV_PATH = os.path.join(DATA_DIR, "students.csv")


def setup_database():
    """Create the database and tables if they don't exist"""
    # Ensure data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create students table with UNIQUE constraints to prevent duplicates
    cursor.execute("""
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
        cursor.execute("ALTER TABLE students ADD COLUMN batch TEXT")
        print("✅ Added 'batch' column to existing database")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Add university column if it doesn't exist (for existing databases)
    try:
        cursor.execute("ALTER TABLE students ADD COLUMN university TEXT")
        print("✅ Added 'university' column to existing database")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Create OTP codes table
    cursor.execute("""
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
    
    # Create verification logs table
    cursor.execute("""
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
    
    conn.commit()
    print(f"✅ Database initialized at: {DB_PATH}")
    return conn


def import_csv_data(conn):
    """Import student data from CSV file"""
    cursor = conn.cursor()
    
    if not os.path.exists(CSV_PATH):
        print(f"\n❌ Error: CSV file not found at: {CSV_PATH}")
        print(f"\nPlease create a file named 'students.csv' in the 'data' folder with this format:")
        print("-" * 70)
        print("Name,Email id,University,Course,Batch name")
        print("Joshya,joshya@clinf.com,VTU,Android App Development,Nomads")
        print("Pragati,pragati@clinf.com,GTU,Data Analytics,Pioneers")
        print("-" * 70)
        
        # Create sample CSV
        create_sample = input("\nWould you like to create a sample CSV file? (y/n): ")
        if create_sample.lower() == 'y':
            create_sample_csv()
            print(f"\n✅ Sample CSV created at: {CSV_PATH}")
            print("Edit this file with your actual student data, then run this script again.")
        return
    
    print(f"\n📂 Reading CSV file: {CSV_PATH}")
    
    success_count = 0
    duplicate_count = 0
    error_count = 0
    
    try:
        with open(CSV_PATH, 'r', encoding='utf-8') as f:
            # Try to detect the CSV format
            sample = f.read(1024)
            f.seek(0)
            
            # Check if it has a header
            sniffer = csv.Sniffer()
            has_header = sniffer.has_header(sample)
            
            reader = csv.reader(f)
            
            # Skip header if present
            if has_header:
                header = next(reader)
                print(f"📋 CSV Header detected: {header}")
            
            for row_num, row in enumerate(reader, start=2 if has_header else 1):
                # Clean up row - remove empty trailing columns
                row = [col.strip() for col in row if col.strip()]
                
                if len(row) < 4:
                    print(f"⚠️ Row {row_num}: Skipping (insufficient columns - need at least name, email, university, course)")
                    error_count += 1
                    continue
                
                # Expected: name, email, university, course, batch (batch is optional)
                name = row[0].strip()
                email = row[1].strip().lower()
                university = row[2].strip().upper() if len(row) > 2 else ""
                course = row[3].strip() if len(row) > 3 else ""
                batch = row[4].strip() if len(row) > 4 else None
                
                if not email or not course:
                    print(f"⚠️ Row {row_num}: Skipping (missing email or course)")
                    error_count += 1
                    continue
                
                try:
                    cursor.execute("""
                        INSERT INTO students (name, email, university, course, batch)
                        VALUES (?, ?, ?, ?, ?)
                    """, (name, email, university, course, batch))
                    success_count += 1
                except sqlite3.IntegrityError:
                    print(f"⏭️ Duplicate: {email}")
                    duplicate_count += 1
        
        conn.commit()
        
        print("\n" + "=" * 50)
        print("📊 Import Summary")
        print("=" * 50)
        print(f"✅ Successfully added: {success_count} students")
        print(f"⏭️ Duplicates skipped: {duplicate_count} students")
        print(f"⚠️ Errors/skipped:    {error_count} rows")
        print("=" * 50)
        
        # Show total count
        cursor.execute("SELECT COUNT(*) FROM students")
        total = cursor.fetchone()[0]
        print(f"\n📈 Total students in database: {total}")
        
    except Exception as e:
        print(f"\n❌ Error reading CSV: {e}")


def create_sample_csv():
    """Create a sample CSV file for reference"""
    os.makedirs(DATA_DIR, exist_ok=True)
    
    sample_data = [
        ["Name", "Email id", "University", "Course", "Batch name"],
        ["Joshya", "joshya@example.com", "VTU", "Android App Development", "Nomads"],
        ["Pragati", "pragati@example.com", "GTU", "Data Analytics", "Pioneers"],
        ["Sujit Kumar", "sujit@example.com", "VTU", "Android App Development", "Navigants"],
        ["Tirumal", "tirumal@example.com", "GTU", "Data Analytics", "Pioneers"],
    ]
    
    with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(sample_data)


def view_students(conn, limit=10):
    """View students in the database"""
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM students")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM students WHERE is_verified = 1")
    verified = cursor.fetchone()[0]
    
    print(f"\n📊 Database Statistics:")
    print(f"   Total students: {total}")
    print(f"   Verified: {verified}")
    print(f"   Unverified: {total - verified}")
    
    if total > 0:
        print(f"\n📋 Sample students (first {limit}):")
        print("-" * 110)
        print(f"   {'Status':<6} | {'Name':<16} | {'Email':<24} | {'Univ':<5} | {'Course':<20} | {'Batch'}")
        print("-" * 110)
        cursor.execute(f"SELECT name, email, university, course, batch, is_verified FROM students LIMIT {limit}")
        for row in cursor.fetchall():
            status = "✅" if row[5] else "⏳"
            univ = row[2] or "N/A"
            batch = row[4] or "N/A"
            print(f"   {status:<6} | {row[0]:<16} | {row[1]:<24} | {univ:<5} | {row[3]:<20} | {batch}")
        print("-" * 110)


def main():
    """Main function"""
    print("=" * 60)
    print("🎓 Mind Matrix Bot - Student Data Import Tool")
    print("=" * 60)
    
    conn = setup_database()
    
    while True:
        print("\n📌 Options:")
        print("   1. Import students from CSV")
        print("   2. View current students")
        print("   3. Clear all students (reset)")
        print("   4. Exit")
        
        choice = input("\nEnter choice (1-4): ").strip()
        
        if choice == "1":
            import_csv_data(conn)
        elif choice == "2":
            view_students(conn)
        elif choice == "3":
            confirm = input("⚠️ This will delete ALL student data. Type 'YES' to confirm: ")
            if confirm == "YES":
                cursor = conn.cursor()
                cursor.execute("DELETE FROM students")
                cursor.execute("DELETE FROM otp_codes")
                cursor.execute("DELETE FROM verification_logs")
                conn.commit()
                print("✅ All data cleared!")
            else:
                print("Cancelled.")
        elif choice == "4":
            break
        else:
            print("Invalid choice. Please enter 1-4.")
    
    conn.close()
    print("\n👋 Goodbye!")


if __name__ == "__main__":
    main()
