from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.auth import UserRegister, UserLogin, Token, UserProfile, PasswordChange
from app.services.auth_service import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(user_in: UserRegister, db: Session = Depends(get_db)):
    # Check existing email
    existing_user = db.query(User).filter(User.email == user_in.email.lower().strip()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists"
        )
    
    # Valid role check
    allowed_roles = [UserRole.PASSENGER, UserRole.OPERATOR, UserRole.DRIVER, UserRole.CONDUCTOR]
    target_role = user_in.role.upper().strip()
    if target_role not in allowed_roles:
        target_role = UserRole.PASSENGER

    new_user = User(
        email=user_in.email.lower().strip(),
        hashed_password=hash_password(user_in.password),
        full_name=user_in.full_name.strip(),
        phone=user_in.phone.strip() if user_in.phone else None,
        role=target_role,
        company_name=user_in.company_name.strip() if user_in.company_name else None,
        operator_license=user_in.operator_license.strip() if user_in.operator_license else None,
        employee_id=user_in.employee_id.strip() if user_in.employee_id else None,
        driving_license_number=user_in.driving_license_number.strip() if user_in.driving_license_number else None,
        operator_id=user_in.operator_id,
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Issue JWT token
    token = create_access_token({
        "sub": str(new_user.id),
        "email": new_user.email,
        "role": new_user.role,
        "full_name": new_user.full_name
    })

    return Token(
        access_token=token,
        token_type="bearer",
        role=new_user.role,
        user_id=new_user.id,
        full_name=new_user.full_name,
        email=new_user.email
    )

@router.post("/login", response_model=Token)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == credentials.email.lower().strip()).first()
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Please contact support."
        )

    token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "full_name": user.full_name
    })

    return Token(
        access_token=token,
        token_type="bearer",
        role=user.role,
        user_id=user.id,
        full_name=user.full_name,
        email=user.email
    )

@router.get("/me", response_model=UserProfile)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    return current_user

@router.post("/change-password")
def change_password(
    pwd_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not verify_password(pwd_data.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    current_user.hashed_password = hash_password(pwd_data.new_password)
    current_user.updated_at = datetime.utcnow()
    db.commit()
    return {"message": "Password updated successfully"}

@router.get("/demo-accounts")
def get_demo_accounts():
    """
    Returns pre-configured demo account credentials for easy review and demonstration.
    """
    return [
        {
            "role": "PASSENGER",
            "name": "Aarav Sharma",
            "email": "aarav.passenger@trako.io",
            "password": "Password123!",
            "description": "Book seats, track live bus, view digital tickets"
        },
        {
            "role": "OPERATOR",
            "name": "KTC Coastal Travels",
            "email": "ops@coastallines.in",
            "password": "Password123!",
            "description": "Manage fleet, routes, trips, physical QR, live radar"
        },
        {
            "role": "DRIVER",
            "name": "Rajesh Naik (Driver)",
            "email": "rajesh.driver@trako.io",
            "password": "Password123!",
            "description": "Start trip, stream smartphone GPS coordinates"
        },
        {
            "role": "CONDUCTOR",
            "name": "Suresh Gawde (Conductor)",
            "email": "suresh.conductor@trako.io",
            "password": "Password123!",
            "description": "Scan digital ticket QR, verify passengers, no-show management"
        }
    ]
