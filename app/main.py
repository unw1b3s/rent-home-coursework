import hmac
import os
import secrets
import sqlite3
import time
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, Depends, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from app.db import ROOT, connect, init_db
from app.schemas import Register, Login, ListingInput, RentalInput, RentalStatus, UserStatus
from app.security import hash_password, verify_password, token_hash

@asynccontextmanager
async def lifespan(app):
    init_db()
    yield

app = FastAPI(title='ДомАренда API', version='1.0.0', description='Курсовая работа Волкова Льва Геннадьевича', lifespan=lifespan)
app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')

@app.middleware('http')
async def protect(request: Request, call_next):
    if request.method in {'POST','PUT','PATCH','DELETE'}:
        origin = request.headers.get('origin')
        expected = os.getenv('APP_ORIGIN', str(request.base_url).rstrip('/'))
        if origin and origin.rstrip('/') != expected:
            return JSONResponse({'detail':'Запрос с другого сайта запрещён'}, status_code=403)
        if request.headers.get('content-type','').split(';')[0] != 'application/json':
            return JSONResponse({'detail':'Требуется application/json'}, status_code=415)
        size = request.headers.get('content-length','0')
        if not size.isdigit() or int(size) > 20000:
            return JSONResponse({'detail':'Слишком большой запрос'}, status_code=413)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'same-origin'
    if not request.url.path.startswith('/docs'):
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    if request.url.path.startswith('/api'):
        response.headers['Cache-Control'] = 'no-store'
    return response

@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    fields = ', '.join(str(e['loc'][-1]) for e in exc.errors())
    return JSONResponse({'detail':f'Проверьте поля: {fields}'}, status_code=422)


def current_user(request: Request):
    token = request.cookies.get('session','')
    with connect() as db:
        row = db.execute('''SELECT u.id,u.name,u.email,u.role,s.csrf_token FROM sessions s
            JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>? AND u.active=1''',
                         (token_hash(token),int(time.time()))).fetchone()
    if not row:
        raise HTTPException(401,'Войдите в аккаунт')
    if request.method in {'POST','PUT','PATCH','DELETE'} and not hmac.compare_digest(
            request.headers.get('x-csrf-token',''),row['csrf_token']):
        raise HTTPException(403,'Недействительный CSRF-токен. Обновите страницу')
    return dict(row)

User = Annotated[dict, Depends(current_user)]

def admin(user: User):
    if user['role'] != 'admin':
        raise HTTPException(403,'Требуются права администратора')
    return user
Admin = Annotated[dict, Depends(admin)]


def session_response(db, user, response):
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    db.execute('DELETE FROM sessions WHERE expires_at<=?', (int(time.time()),))
    db.execute('INSERT INTO sessions VALUES (?,?,?,?)',
               (token_hash(token),user['id'],csrf,int(time.time()) + 86400))
    response.set_cookie('session',token,httponly=True,samesite='lax',secure=os.getenv('COOKIE_SECURE')=='1',max_age=86400)
    return {k:user[k] for k in ('id','name','email','role')} | {'csrf_token':csrf}

@app.get('/', include_in_schema=False)
def home():
    return FileResponse(ROOT / 'static/index.html')

@app.get('/api/health', tags=['Сервис'])
def health():
    with connect() as db:
        db.execute('SELECT 1')
    return {'status':'ok'}

@app.post('/api/auth/register', status_code=201, tags=['Авторизация'])
def register(data: Register, response: Response):
    with connect() as db:
        try:
            cursor = db.execute('INSERT INTO users(name,email,password_hash) VALUES (?,?,?)',
                                (data.name,data.email,hash_password(data.password)))
        except sqlite3.IntegrityError:
            raise HTTPException(409,'Этот email уже зарегистрирован')
        user = db.execute('SELECT * FROM users WHERE id=?',(cursor.lastrowid,)).fetchone()
        return session_response(db,user,response)

@app.post('/api/auth/login', tags=['Авторизация'])
def login(data: Login, response: Response, request: Request):
    # Лимит попыток на IP в одном процессе; для нескольких процессов нужен общий limiter.
    ip = request.client.host if request.client else 'unknown'
    now = time.monotonic()
    attempts = getattr(app.state,'attempts',{})
    attempts = {key:[t for t in times if now-t<300] for key,times in attempts.items() if times and now-times[-1]<300}
    recent = attempts.get(ip,[])
    app.state.attempts = attempts
    if len(recent) >= 10:
        raise HTTPException(429,'Слишком много попыток. Повторите через 5 минут')
    with connect() as db:
        user = db.execute('SELECT * FROM users WHERE email=?',(data.email,)).fetchone()
        valid = verify_password(data.password, user['password_hash'] if user else hash_password('dummy-password'))
        if not user or not valid or not user['active']:
            attempts[ip] = recent + [now]
            raise HTTPException(401,'Неверный email или пароль')
        attempts.pop(ip,None)
        return session_response(db,user,response)

@app.get('/api/auth/me', tags=['Авторизация'])
def me(user: User):
    return user

@app.post('/api/auth/logout', status_code=204, tags=['Авторизация'])
def logout(request: Request, user: User):
    with connect() as db:
        db.execute('DELETE FROM sessions WHERE token_hash=?',(token_hash(request.cookies['session']),))
    response = Response(status_code=204)
    response.delete_cookie('session')
    return response

@app.get('/api/types', tags=['Каталог'])
def types():
    with connect() as db:
        return [dict(r) for r in db.execute('SELECT * FROM property_types')]

SELECT_LISTING = '''SELECT l.*,p.name AS type_name,u.name AS owner_name
 FROM listings l JOIN property_types p ON p.id=l.type_id JOIN users u ON u.id=l.owner_id'''

def listing_by_id(db, listing_id):
    row = db.execute(SELECT_LISTING + ' WHERE l.id=?',(listing_id,)).fetchone()
    if not row:
        raise HTTPException(404,'Объявление не найдено')
    return dict(row)

def check_owner(row, user):
    if row['owner_id'] != user['id'] and user['role'] != 'admin':
        raise HTTPException(403,'Нельзя изменять чужое объявление')

@app.get('/api/listings', tags=['Каталог'])
def listings(q: str = Query('',max_length=120), city: str = Query('',max_length=80),
             type_id: int | None = Query(None,ge=1,le=4), max_price: int | None = Query(None,ge=1000),
             page: int = Query(1,ge=1), page_size: int = Query(6,ge=1,le=50),
             sort: str = Query('newest',pattern='^(newest|price_asc|price_desc)$')):
    conditions, args = ["l.status='available'",'u.active=1'], []
    if q:
        conditions.append('(l.title LIKE ? OR l.description LIKE ?)')
        args.extend([f'%{q}%',f'%{q}%'])
    if city:
        conditions.append('l.city = ? COLLATE NOCASE'); args.append(city)
    if type_id:
        conditions.append('l.type_id=?'); args.append(type_id)
    if max_price is not None:
        conditions.append('l.price<=?'); args.append(max_price)
    where = ' WHERE ' + ' AND '.join(conditions)
    order = {'newest':'l.id DESC','price_asc':'l.price ASC,l.id DESC','price_desc':'l.price DESC,l.id DESC'}[sort]
    with connect() as db:
        total = db.execute('SELECT COUNT(*) FROM listings l JOIN users u ON u.id=l.owner_id'+where,args).fetchone()[0]
        rows = db.execute(SELECT_LISTING+where+' ORDER BY '+order+' LIMIT ? OFFSET ?', args+[page_size,(page-1)*page_size])
        items = [dict(row) for row in rows]
    for item in items:
        item.pop('phone')
    return {'items':items,'total':total,'page':page,'page_size':page_size}

@app.get('/api/listings/{listing_id}', tags=['Каталог'])
def listing(listing_id: int, request: Request):
    try:
        viewer = current_user(request)
    except HTTPException:
        viewer = None
    with connect() as db:
        row = listing_by_id(db,listing_id)
        owner = db.execute('SELECT active FROM users WHERE id=?',(row['owner_id'],)).fetchone()
        if not owner['active'] and not (viewer and viewer['role'] == 'admin'):
            raise HTTPException(404,'Объявление не найдено')
    if not viewer:
        row.pop('phone')
    return row

@app.post('/api/listings', status_code=201, tags=['Объявления'])
def create_listing(data: ListingInput, user: User):
    values = data.model_dump()
    with connect() as db:
        cursor = db.execute('INSERT INTO listings(owner_id,'+','.join(values)+') VALUES ('+','.join('?' for _ in range(len(values)+1))+')',
                            [user['id']]+list(values.values()))
        return listing_by_id(db,cursor.lastrowid)

@app.put('/api/listings/{listing_id}', tags=['Объявления'])
def update_listing(listing_id: int, data: ListingInput, user: User):
    values = data.model_dump()
    with connect() as db:
        check_owner(listing_by_id(db,listing_id),user)
        db.execute('UPDATE listings SET '+','.join(k+'=?' for k in values)+' WHERE id=?',list(values.values())+[listing_id])
        if data.status == 'rented':
            db.execute("UPDATE rental_requests SET status='rejected' WHERE listing_id=? AND status='pending'",(listing_id,))
        else:
            # Повторная сдача завершает прежнюю принятую заявку в рамках учебной модели.
            db.execute("UPDATE rental_requests SET status='cancelled' WHERE listing_id=? AND status='accepted'",(listing_id,))
        return listing_by_id(db,listing_id)

@app.delete('/api/listings/{listing_id}', status_code=204, tags=['Объявления'])
def delete_listing(listing_id: int, user: User):
    with connect() as db:
        check_owner(listing_by_id(db,listing_id),user)
        db.execute('DELETE FROM listings WHERE id=?',(listing_id,))
    return Response(status_code=204)

@app.get('/api/my/listings', tags=['Личный кабинет'])
def my_listings(user: User):
    with connect() as db:
        return [dict(r) for r in db.execute(SELECT_LISTING+' WHERE l.owner_id=? ORDER BY l.id DESC',(user['id'],))]

@app.post('/api/listings/{listing_id}/requests', status_code=201, tags=['Заявки'])
def send_request(listing_id: int, data: RentalInput, user: User):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = listing_by_id(db,listing_id)
        owner = db.execute('SELECT active FROM users WHERE id=?',(row['owner_id'],)).fetchone()
        if row['owner_id'] == user['id']:
            raise HTTPException(400,'Нельзя отправить заявку на своё объявление')
        if row['status'] != 'available' or not owner['active']:
            raise HTTPException(409,'Объект недоступен для аренды')
        try:
            cursor = db.execute('INSERT INTO rental_requests(listing_id,tenant_id,move_in,message) VALUES (?,?,?,?)',
                                (listing_id,user['id'],str(data.move_in),data.message))
        except sqlite3.IntegrityError:
            raise HTTPException(409,'У вас уже есть активная заявка на этот объект')
        return dict(db.execute('SELECT * FROM rental_requests WHERE id=?',(cursor.lastrowid,)).fetchone())

@app.get('/api/my/requests', tags=['Заявки'])
def my_requests(user: User):
    with connect() as db:
        return [dict(r) for r in db.execute('''SELECT r.*,l.title,l.owner_id,u.name AS tenant_name
          FROM rental_requests r JOIN listings l ON l.id=r.listing_id JOIN users u ON u.id=r.tenant_id
          WHERE r.tenant_id=? OR l.owner_id=? ORDER BY r.id DESC''',(user['id'],user['id']))]

@app.patch('/api/requests/{request_id}', tags=['Заявки'])
def change_request(request_id: int, data: RentalStatus, user: User):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('''SELECT r.*,l.owner_id,l.status AS listing_status FROM rental_requests r
            JOIN listings l ON l.id=r.listing_id WHERE r.id=?''',(request_id,)).fetchone()
        if not row:
            raise HTTPException(404,'Заявка не найдена')
        permitted = row['tenant_id']==user['id'] if data.status=='cancelled' else row['owner_id']==user['id']
        if not permitted:
            raise HTTPException(403,'Нет прав на это действие')
        if row['status'] != 'pending':
            raise HTTPException(409,'Можно изменить только ожидающую заявку')
        if data.status == 'accepted':
            if row['listing_status'] != 'available':
                raise HTTPException(409,'Объект уже сдан')
            db.execute("UPDATE listings SET status='rented' WHERE id=?",(row['listing_id'],))
            db.execute("UPDATE rental_requests SET status='rejected' WHERE listing_id=? AND status='pending' AND id<>?",(row['listing_id'],request_id))
        db.execute('UPDATE rental_requests SET status=? WHERE id=?',(data.status,request_id))
    return {'id':request_id,'status':data.status}

@app.get('/api/admin/summary', tags=['Администрирование'])
def summary(user: Admin):
    with connect() as db:
        return {table:db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in ('users','listings','rental_requests')}

@app.get('/api/admin/users', tags=['Администрирование'])
def users(user: Admin, page: int = Query(1,ge=1), page_size: int = Query(20,ge=1,le=100)):
    with connect() as db:
        return {'items':[dict(r) for r in db.execute('SELECT id,name,email,role,active FROM users ORDER BY id LIMIT ? OFFSET ?',
                    (page_size,(page-1)*page_size))], 'total':db.execute('SELECT COUNT(*) FROM users').fetchone()[0]}

@app.patch('/api/admin/users/{user_id}', tags=['Администрирование'])
def block_user(user_id: int, data: UserStatus, user: Admin):
    with connect() as db:
        row = db.execute('SELECT role FROM users WHERE id=?',(user_id,)).fetchone()
        if not row:
            raise HTTPException(404,'Пользователь не найден')
        if row['role']=='admin':
            raise HTTPException(400,'Нельзя блокировать администратора')
        db.execute('UPDATE users SET active=? WHERE id=?',(int(data.active),user_id))
        if not data.active:
            db.execute('DELETE FROM sessions WHERE user_id=?',(user_id,))
    return {'id':user_id,'active':data.active}

@app.get('/api/admin/listings', tags=['Администрирование'])
def all_listings(user: Admin, page: int = Query(1,ge=1), page_size: int = Query(20,ge=1,le=100)):
    with connect() as db:
        return {'items':[dict(r) for r in db.execute(SELECT_LISTING+' ORDER BY l.id DESC LIMIT ? OFFSET ?',
                (page_size,(page-1)*page_size))], 'total':db.execute('SELECT COUNT(*) FROM listings').fetchone()[0]}


def documented_openapi():
    """Добавить описание cookie-сессии и CSRF в стандартную схему FastAPI."""
    from fastapi.openapi.utils import get_openapi
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=app.title,version=app.version,routes=app.routes,
                        description='JSON API. После входа браузер получает HttpOnly cookie session. '
                        'Для изменения данных передавайте X-CSRF-Token из ответа входа или GET /api/auth/me.')
    schema['components']['securitySchemes'] = {
        'SessionCookie':{'type':'apiKey','in':'cookie','name':'session'},
        'CSRFToken':{'type':'apiKey','in':'header','name':'X-CSRF-Token'}}
    public = {'/api/health','/api/types','/api/auth/register','/api/auth/login','/api/listings'}
    for path,methods in schema['paths'].items():
        for method,operation in methods.items():
            if not isinstance(operation,dict) or method not in {'get','post','put','patch','delete'}:
                continue
            needs_auth = path not in public and not (path=='/api/listings/{listing_id}' and method=='get')
            needs_auth = needs_auth or (path=='/api/listings' and method=='post')
            if needs_auth:
                operation['security'] = [{'SessionCookie':[], **({'CSRFToken':[]} if method!='get' else {})}]
                operation['responses']['401'] = {'description':'Сессия отсутствует или истекла'}
                operation['responses']['403'] = {'description':'Нет прав или неверный CSRF-токен'}
    app.openapi_schema = schema
    return schema

app.openapi = documented_openapi
