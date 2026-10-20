from datetime import date, timedelta
from app.db import connect


def login(client,email):
    response=client.post('/api/auth/login',json={'email':email,'password':'password123'})
    assert response.status_code==200
    return {'X-CSRF-Token':response.json()['csrf_token']}


def test_auth_lifecycle(client,account):
    assert client.get('/api/auth/me').status_code==401
    user, headers=account()
    assert user['role']=='user'
    assert client.get('/api/auth/me').json()['email']=='owner@test.ru'
    with connect() as db:
        stored=db.execute('SELECT * FROM sessions').fetchone()
        assert stored['token_hash']!=client.cookies.get('session')
    assert client.post('/api/auth/logout',json={},headers=headers).status_code==204
    assert client.get('/api/auth/me').status_code==401
    response=client.post('/api/auth/login',json={'email':'OWNER@test.ru','password':'password123'})
    assert response.status_code==200
    assert 'HttpOnly' in response.headers['set-cookie']
    assert 'SameSite=lax' in response.headers['set-cookie']
    assert client.post('/api/auth/register',json={'email':'owner@test.ru','name':'Другой','password':'password123'}).status_code==409


def test_login_rate_limit(client,account):
    account()
    for _ in range(10):
        assert client.post('/api/auth/login',json={'email':'owner@test.ru','password':'wrong12345'}).status_code==401
    assert client.post('/api/auth/login',json={'email':'owner@test.ru','password':'password123'}).status_code==429


def test_csrf_and_origin(client,account,payload):
    _, headers=account()
    assert client.post('/api/listings',json=payload).status_code==403
    assert client.post('/api/listings',json=payload,headers=headers|{'Origin':'https://evil.example'}).status_code==403
    assert client.post('/api/listings',content='x',headers={'Content-Type':'text/plain'}).status_code==415
    assert client.post('/api/listings',json=payload,headers=headers|{'Content-Length':'30000'}).status_code==413
    assert client.post('/api/listings',json=payload,headers=headers|{'Origin':'http://testserver'}).status_code==201


def test_catalog_crud_and_permissions(client,listing,account,payload):
    item,owner,headers=listing; identifier=item['id']
    changed=payload|{'title':'Изменённая квартира'}
    assert client.put(f'/api/listings/{identifier}',json=changed,headers=headers).status_code==200
    assert client.get('/api/my/listings').json()[0]['title']==changed['title']
    _, other=account('other@test.ru','Другой')
    assert client.put(f'/api/listings/{identifier}',json=payload,headers=other).status_code==403
    assert client.request('DELETE',f'/api/listings/{identifier}',json={},headers=other).status_code==403
    assert client.get('/api/admin/users').status_code==403
    headers=login(client,owner['email'])
    assert client.request('DELETE',f'/api/listings/{identifier}',json={},headers=headers).status_code==204
    assert client.get(f'/api/listings/{identifier}').status_code==404


def test_search_sort_pagination_and_contacts(client,account,payload):
    _,h=account()
    for i in range(8):
        assert client.post('/api/listings',json=payload|{'price':10000+i*1000,'city':'Казань' if i<4 else 'Москва'},headers=h).status_code==201
    assert client.get('/api/listings').json()['total']==8
    assert len(client.get('/api/listings?page=2').json()['items'])==2
    data=client.get('/api/listings?city=Казань&max_price=12000&sort=price_desc&type_id=1&q=мебелью').json()
    assert data['total']==3 and data['items'][0]['price']==12000
    assert client.get('/api/listings?q=%27%20OR%201=1--').json()['total']==0
    assert client.get('/api/listings?sort=price_asc').json()['items'][0]['price']==10000
    assert client.get('/api/listings?page=0').status_code==422
    assert 'phone' not in client.get('/api/listings').json()['items'][0]
    assert 'phone' in client.get('/api/listings/1').json()
    client.post('/api/auth/logout',json={},headers=h)
    assert 'phone' not in client.get('/api/listings/1').json()


def test_requests_business_flow(client,listing,account):
    item,owner,h=listing; identifier=item['id']; data={'move_in':str(date.today()+timedelta(days=1)),'message':'Хочу снять'}
    assert client.post(f'/api/listings/{identifier}/requests',json=data,headers=h).status_code==400
    tenant,t=account('tenant@test.ru','Арендатор')
    result=client.post(f'/api/listings/{identifier}/requests',json=data,headers=t)
    assert result.status_code==201; request_id=result.json()['id']
    assert client.post(f'/api/listings/{identifier}/requests',json=data,headers=t).status_code==409
    assert client.patch(f'/api/requests/{request_id}',json={'status':'accepted'},headers=t).status_code==403
    assert len(client.get('/api/my/requests').json())==1
    _,second=account('second@test.ru','Второй')
    r2=client.post(f'/api/listings/{identifier}/requests',json=data,headers=second).json()['id']
    h=login(client,owner['email'])
    assert len(client.get('/api/my/requests').json())==2
    assert client.patch(f'/api/requests/{request_id}',json={'status':'accepted'},headers=h).status_code==200
    assert client.get(f'/api/listings/{identifier}').json()['status']=='rented'
    assert client.get('/api/listings').json()['total']==0
    assert client.patch(f'/api/requests/{r2}',json={'status':'accepted'},headers=h).status_code==409
    t=login(client,tenant['email'])
    assert client.patch(f'/api/requests/{request_id}',json={'status':'cancelled'},headers=t).status_code==409
    assert client.post(f'/api/listings/{identifier}/requests',json=data,headers=t).status_code==409


def test_cancel_reject_and_cascade(client,listing,account):
    item,owner,h=listing; data={'move_in':str(date.today())}
    tenant,t=account('tenant@test.ru','Арендатор')
    req=client.post(f"/api/listings/{item['id']}/requests",json=data,headers=t).json()['id']
    assert client.patch('/api/requests/999',json={'status':'cancelled'},headers=t).status_code==404
    assert client.patch(f'/api/requests/{req}',json={'status':'cancelled'},headers=t).status_code==200
    req=client.post(f"/api/listings/{item['id']}/requests",json=data,headers=t).json()['id']
    h=login(client,owner['email'])
    assert client.patch(f'/api/requests/{req}',json={'status':'rejected'},headers=h).status_code==200
    assert client.request('DELETE',f"/api/listings/{item['id']}",json={},headers=h).status_code==204
    assert client.get('/api/my/requests').json()==[]


def test_admin_and_blocking(client,listing,account,make_admin):
    item,owner,h=listing
    administrator,a=account('admin@test.ru','Администратор'); make_admin(administrator['id'])
    assert client.get('/api/admin/summary').json()['listings']==1
    assert client.get('/api/admin/listings').json()['total']==1
    assert client.get('/api/admin/users').json()['total']==2
    assert client.patch(f"/api/admin/users/{administrator['id']}",json={'active':False},headers=a).status_code==400
    assert client.patch('/api/admin/users/999',json={'active':False},headers=a).status_code==404
    assert client.patch(f"/api/admin/users/{owner['id']}",json={'active':False},headers=a).status_code==200
    assert client.get('/api/listings').json()['total']==0
    assert client.get(f"/api/listings/{item['id']}").status_code==404
    assert client.post('/api/auth/login',json={'email':owner['email'],'password':'password123'}).status_code==401
    assert client.patch(f"/api/admin/users/{owner['id']}",json={'active':True},headers=a).status_code==200
    assert client.request('DELETE',f"/api/listings/{item['id']}",json={},headers=a).status_code==204


def test_routes_and_openapi(client):
    assert client.get('/').status_code==200
    assert client.get('/static/app.js').status_code==200
    assert client.get('/api/health').json()=={'status':'ok'}
    assert len(client.get('/api/types').json())==4
    assert '/api/listings' in client.get('/openapi.json').json()['paths']
    assert client.get('/docs').status_code==200


def test_mark_rented_and_reopen(client,listing,account,payload):
    item,owner,h=listing
    _,t=account('tenant@test.ru','Арендатор')
    client.post(f"/api/listings/{item['id']}/requests",json={'move_in':str(date.today())},headers=t)
    h=login(client,owner['email'])
    assert client.put(f"/api/listings/{item['id']}",json=payload|{'status':'rented'},headers=h).status_code==200
    assert client.get('/api/my/requests').json()[0]['status']=='rejected'
    assert client.put(f"/api/listings/{item['id']}",json=payload,headers=h).status_code==200
    assert client.get('/api/listings').json()['total']==1
