import pytest
from pydantic import ValidationError
from datetime import date, timedelta
from app.security import hash_password, verify_password, token_hash
from app.schemas import Register, ListingInput, RentalInput


def test_password_hashing():
    first, second=hash_password('password123'),hash_password('password123')
    assert first!=second
    assert verify_password('password123',first)
    assert not verify_password('wrong',first)
    assert not verify_password('password123','broken')
    assert not verify_password('password123','other$ab$cd')
    assert 'password123' not in first
    assert token_hash('secret')!='secret'

@pytest.mark.parametrize('change',[{'email':'wrong'},{'password':'short'},{'name':'А'},{'role':'admin'}])
def test_register_validation(change):
    with pytest.raises(ValidationError):
        Register(**(dict(name='Иван',email='user@test.ru',password='password123')|change))

@pytest.mark.parametrize('change',[{'price':-1},{'area':0},{'phone':'abcdefg'},{'type_id':8},{'description':'Коротко'},{'area':float('inf')}])
def test_listing_validation(payload,change):
    with pytest.raises(ValidationError): ListingInput(**(payload|change))


def test_date_validation():
    with pytest.raises(ValidationError): RentalInput(move_in=date.today()-timedelta(days=1))
    assert RentalInput(move_in=date.today()).message==''
