import re
from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, field_validator, ConfigDict

class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

class Login(Input):
    email: str = Field(min_length=5, max_length=120)
    password: str = Field(min_length=8, max_length=128)

    @field_validator('email')
    @classmethod
    def email_valid(cls, value):
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
            raise ValueError('Введите корректный email')
        return value.lower()

class Register(Login):
    name: str = Field(min_length=2, max_length=80)

class ListingInput(Input):
    title: str = Field(min_length=5, max_length=120)
    description: str = Field(min_length=20, max_length=3000)
    type_id: int = Field(ge=1, le=4)
    city: str = Field(min_length=2, max_length=80)
    address: str = Field(min_length=5, max_length=200)
    price: int = Field(ge=1000, le=10000000)
    rooms: int = Field(ge=0, le=20)
    area: float = Field(ge=5, le=10000, allow_inf_nan=False)
    phone: str = Field(min_length=7, max_length=30)
    status: Literal['available','rented'] = 'available'

    @field_validator('phone')
    @classmethod
    def phone_valid(cls, value):
        if not re.fullmatch(r'[+\d()\s-]+', value) or len(re.sub(r'\D','',value)) < 7:
            raise ValueError('Введите корректный телефон')
        return value

class RentalInput(Input):
    move_in: date
    message: str = Field(default='', max_length=1000)

    @field_validator('move_in')
    @classmethod
    def future_date(cls, value):
        if value < date.today():
            raise ValueError('Дата не может быть в прошлом')
        return value

class RentalStatus(Input):
    status: Literal['accepted','rejected','cancelled']

class UserStatus(Input):
    active: bool
