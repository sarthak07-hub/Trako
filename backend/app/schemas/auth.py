from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=2)
    phone: Optional[str] = None
    role: str = "PASSENGER"  # PASSENGER, OPERATOR, DRIVER, CONDUCTOR
    company_name: Optional[str] = None
    operator_license: Optional[str] = None
    employee_id: Optional[str] = None
    driving_license_number: Optional[str] = None
    operator_id: Optional[int] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int
    full_name: str
    email: str

class UserProfile(BaseModel):
    id: int
    email: str
    full_name: str
    phone: Optional[str] = None
    role: str
    company_name: Optional[str] = None
    operator_license: Optional[str] = None
    employee_id: Optional[str] = None
    driving_license_number: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6)
