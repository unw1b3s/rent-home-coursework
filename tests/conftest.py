import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import connect

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'test.db'))
    app.state.attempts={}
    with TestClient(app) as client:
        yield client

@pytest.fixture
def account(client):
    def create(email='owner@test.ru', name='Владелец'):
        response=client.post('/api/auth/register',json={'email':email,'name':name,'password':'password123'})
        assert response.status_code==201
        return response.json(), {'X-CSRF-Token':response.json()['csrf_token']}
    return create

@pytest.fixture
def payload():
    return dict(title='Квартира для теста',description='Квартира с мебелью для длительной аренды.',
                type_id=1,city='Москва',address='ул. Тестовая, д. 1',price=30000,rooms=1,area=35,phone='+7 000 000 00 01',status='available')

@pytest.fixture
def listing(client,account,payload):
    user, headers=account()
    response=client.post('/api/listings',json=payload,headers=headers)
    assert response.status_code==201
    return response.json(),user,headers

@pytest.fixture
def make_admin():
    def promote(user_id):
        with connect() as db: db.execute("UPDATE users SET role='admin' WHERE id=?",(user_id,))
    return promote
