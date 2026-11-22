import sys
import os
import uvicorn

# Ensure backend directory is in sys.path
backend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.database import Base, engine
import app.models
from seed_data import seed_database
from app.config import settings

def main():
    print("=" * 65)
    print("  TRAKO — Smarter Journeys. Better Connections.")
    print("  Smart Bus Transportation and Management Platform")
    print("=" * 65)

    print("\n[*] Initializing Database schema...")
    Base.metadata.create_all(bind=engine)

    print("[*] Checking / Seeding Demo Data...")
    try:
        seed_database()
    except Exception as e:
        print(f"[!] Seed check: {e}")

    print("\n[+] Database ready!")
    print(f"[+] Starting Uvicorn Server at http://{settings.HOST}:{settings.PORT}")
    print(f"[+] Landing Page: http://localhost:{settings.PORT}/pages/index.html")
    print(f"[+] Swagger Docs: http://localhost:{settings.PORT}/docs")
    print("=" * 65 + "\n")

    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=False)

if __name__ == "__main__":
    main()
