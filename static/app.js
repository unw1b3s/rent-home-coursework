'use strict';
const app = document.querySelector('#app');
let user = null, types = [], routeVersion = 0;
const labels = {pending:'Ожидает ответа',accepted:'Принята',rejected:'Отклонена',cancelled:'Отменена',available:'Доступно',rented:'Сдано'};
const money = n => new Intl.NumberFormat('ru-RU').format(n);
const esc = value => String(value ?? '').replace(/[&<>"']/g, x => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));
const date = value => new Date(value + 'T00:00:00').toLocaleDateString('ru-RU');
function notify(message) { const el = document.querySelector('#notice'); el.textContent = message; el.style.display = 'block'; clearTimeout(notify.timer); notify.timer = setTimeout(()=>el.style.display='none',4500); }
async function api(path, options = {}) {
  const headers = {'Content-Type':'application/json', ...(user ? {'X-CSRF-Token':user.csrf_token} : {})};
  const response = await fetch('/api' + path, {...options, headers, credentials:'same-origin'});
  if (response.status === 204) return null;
  const data = await response.json();
  if (!response.ok) {
    if (response.status === 401 && user) { user = null; renderNav(); }
    throw new Error(typeof data.detail === 'string' ? data.detail : 'Проверьте введённые данные');
  }
  return data;
}
function renderNav() {
  document.querySelector('#nav').innerHTML = `<a href="#/">Каталог</a>${user ? `<a href="#/my">Мои объявления</a><a href="#/requests">Заявки</a>${user.role==='admin'?'<a href="#/admin">Админка</a>':''}<button class="secondary" id="logout">Выйти</button>` : '<a href="#/login">Войти</a><a class="button secondary" href="#/register">Регистрация</a>'}`;
  document.querySelector('#logout')?.addEventListener('click',async()=> { try { await api('/auth/logout',{method:'POST',body:'{}'}); user=null; renderNav(); location.hash='/'; await route(); notify('Вы вышли из аккаунта'); } catch(e) { notify(e.message); } });
}
function cover(type) { return `<div class="cover ${['','flat','studio','house','room'][type]||''}" aria-hidden="true"><div class="building">${'<i></i>'.repeat(9)}</div></div>`; }
function card(item, controls=false) {
  return `<article class="card">${cover(item.type_id)}<div class="card-body"><span class="tag ${item.status==='rented'?'rented':''}">${esc(controls?labels[item.status]:item.type_name)}</span><h3><a href="#/listing/${item.id}">${esc(item.title)}</a></h3><p class="muted">${esc(item.city)} · ${item.area} м² · ${item.rooms===0?'студия':item.rooms+' комн.'}</p><p class="price">${money(item.price)} ₽ <small>/ месяц</small></p>${controls?`<div class="actions"><a href="#/edit/${item.id}">Изменить</a><button class="secondary delete-listing" data-id="${item.id}">Удалить</button></div>`:`<a href="#/listing/${item.id}">Подробнее →</a>`}</div></article>`;
}
function pager(page,total,size,id='page') { return `<div class="pagination"><button class="secondary" data-${id}="${page-1}" ${page<=1?'disabled':''}>← Назад</button><span>${page} / ${Math.max(1,Math.ceil(total/size))}</span><button class="secondary" data-${id}="${page+1}" ${page*size>=total?'disabled':''}>Далее →</button></div>`; }
function guard() { if (!user) { location.hash='/login'; return false; } return true; }
function bindForm(id, action) {
  document.querySelector(id).addEventListener('submit', async event => {
    event.preventDefault(); const form=event.currentTarget, error=form.querySelector('.error'), button=form.querySelector('[type="submit"]');
    error.textContent=''; button.disabled=true;
    try { await action(Object.fromEntries(new FormData(form)),form); } catch(e) { error.textContent=e.message; } finally { button.disabled=false; }
  });
}
async function catalog(params, version) {
  const result = await api('/listings?' + params);
  if (version !== routeVersion) return;
  app.innerHTML = `<div class="intro"><p class="eyebrow">Аренда на длительный срок</p><h1>Найдите жильё для себя</h1><p class="muted">Квартиры, студии, дома и комнаты. Выберите подходящий вариант и отправьте заявку владельцу.</p></div>
  <form class="filters panel" id="filters"><label>Поиск<input name="q" placeholder="Например, рядом с парком" maxlength="120" value="${esc(params.get('q')||'')}"></label><label>Город<input name="city" placeholder="Любой город" maxlength="80" value="${esc(params.get('city')||'')}"></label><label>Тип жилья<select name="type_id"><option value="">Любой</option>${types.map(t=>`<option value="${t.id}" ${params.get('type_id')===String(t.id)?'selected':''}>${esc(t.name)}</option>`).join('')}</select></label><label>Цена до, ₽<input type="number" min="1000" name="max_price" placeholder="Без ограничений" value="${esc(params.get('max_price')||'')}"></label><button type="submit">Найти</button></form>
  <div class="catalog-head"><h2>Объявления <span class="muted">· ${result.total}</span></h2><select id="sort" aria-label="Сортировка"><option value="newest">Сначала новые</option><option value="price_asc">Сначала дешевле</option><option value="price_desc">Сначала дороже</option></select></div>
  <div class="grid">${result.items.length?result.items.map(x=>card(x)).join(''):'<div class="empty"><h3>Ничего не найдено</h3><p class="muted">Попробуйте изменить фильтры.</p><a href="#/">Сбросить фильтры</a></div>'}</div>${result.total>6?pager(result.page,result.total,6):''}<p class="hint auth-note">Учебный сервис. Демонстрационные объявления не являются реальными предложениями аренды.</p>`;
  document.querySelector('#sort').value=params.get('sort')||'newest';
  const navigate = p => { location.hash='/?'+p.toString(); };
  document.querySelector('#filters').addEventListener('submit',event=> { event.preventDefault(); const p=new URLSearchParams(new FormData(event.target)); [...p].forEach(([k,v])=>{if(!v)p.delete(k)}); p.set('sort',document.querySelector('#sort').value); navigate(p); });
  document.querySelector('#sort').addEventListener('change',event=> {params.set('sort',event.target.value);params.delete('page');navigate(params)});
  document.querySelectorAll('[data-page]').forEach(b=>b.onclick=()=>{params.set('page',b.dataset.page);navigate(params)});
}
function auth(register=false) {
  app.innerHTML=`<section class="panel auth"><h1>${register?'Регистрация':'Вход в аккаунт'}</h1><p class="muted">${register?'Создайте аккаунт, чтобы размещать объявления и отправлять заявки.':'Войдите, чтобы управлять объявлениями и заявками.'}</p><form id="auth">${register?'<label>Имя<input name="name" autocomplete="name" minlength="2" maxlength="80" required></label>':''}<label>Email<input name="email" type="email" autocomplete="username" maxlength="120" required></label><label>Пароль<input name="password" type="password" autocomplete="${register?'new-password':'current-password'}" minlength="8" maxlength="128" required></label>${register?'<p class="hint">Не менее 8 символов.</p>':''}<p class="error" role="alert"></p><button type="submit">${register?'Зарегистрироваться':'Войти'}</button></form><p class="hint auth-note">${register?'Уже есть аккаунт? <a href="#/login">Войти</a>':'Нет аккаунта? <a href="#/register">Зарегистрироваться</a>'}</p></section>`;
  bindForm('#auth',async data=>{ user=await api('/auth/'+(register?'register':'login'),{method:'POST',body:JSON.stringify(data)});renderNav();location.hash='/my';notify(register?'Аккаунт создан':'Вы вошли в аккаунт'); });
}
async function detail(id,version) {
  const item=await api('/listings/'+id); if(version!==routeVersion)return;
  const own=user && (user.id===item.owner_id || user.role==='admin');
  app.innerHTML=`<a class="back" href="#/">← В каталог</a><div class="detail-layout"><article class="detail"><h1>${esc(item.title)}</h1><p class="muted">${esc(item.city)}, ${esc(item.address)}</p>${cover(item.type_id)}<span class="tag ${item.status==='rented'?'rented':''}">${labels[item.status]}</span><div class="facts"><span>${esc(item.type_name)}</span><span>${item.area} м²</span><span>${item.rooms===0?'Студия':item.rooms+' комн.'}</span></div><h2>Описание</h2><p class="description">${esc(item.description)}</p></article><aside class="panel sticky"><p class="price">${money(item.price)} ₽ <small>/ месяц</small></p><p>Владелец: ${esc(item.owner_name)}</p>${user?`<p>Телефон: ${esc(item.phone)}</p>`:'<p class="hint">Контактный телефон доступен после входа.</p>'}${own?`<a class="button" href="#/edit/${item.id}">Изменить объявление</a>`:item.status==='rented'?'<p>Объект уже сдан.</p>':!user?'<a class="button" href="#/login">Войти и отправить заявку</a>':`<h2>Заявка на аренду</h2><form id="request"><label>Дата заселения<input name="move_in" type="date" min="${new Date().toLocaleDateString('en-CA')}" required></label><label>Сообщение владельцу<textarea name="message" maxlength="1000" placeholder="Расскажите, кто будет проживать"></textarea></label><p class="error" role="alert"></p><button type="submit">Отправить заявку</button></form>`}<p class="hint auth-note">Заявка помогает связаться с владельцем. Договор и оплата оформляются отдельно.</p></aside></div>`;
  if(document.querySelector('#request'))bindForm('#request',async data=>{await api(`/listings/${id}/requests`,{method:'POST',body:JSON.stringify(data)});location.hash='/requests';notify('Заявка отправлена владельцу');});
}
async function editor(id,version) {
  if(!guard())return;
  const item=id?await api('/listings/'+id):{};if(version!==routeVersion)return;
  if(id && user.id!==item.owner_id && user.role!=='admin')throw new Error('Нельзя изменять чужое объявление');
  app.innerHTML=`<div class="edit"><a class="back" href="#/my">← Мои объявления</a><section class="panel"><h1>${id?'Редактирование':'Новое объявление'}</h1><p class="muted">Укажите основные сведения о жилье и условия аренды.</p><form id="editor"><div class="form-grid"><label class="full">Заголовок<input name="title" minlength="5" maxlength="120" required value="${esc(item.title||'')}"></label><label>Тип жилья<select name="type_id">${types.map(t=>`<option value="${t.id}" ${item.type_id===t.id?'selected':''}>${esc(t.name)}</option>`).join('')}</select></label><label>Город<input name="city" minlength="2" maxlength="80" required value="${esc(item.city||'')}"></label><label class="full">Адрес<input name="address" minlength="5" maxlength="200" required value="${esc(item.address||'')}"></label><label>Аренда в месяц, ₽<input name="price" type="number" min="1000" max="10000000" required value="${item.price||''}"></label><label>Площадь, м²<input name="area" type="number" min="5" max="10000" step="0.1" required value="${item.area||''}"></label><label>Количество комнат<input name="rooms" type="number" min="0" max="20" required value="${item.rooms??1}"><span class="hint">Для студии укажите 0.</span></label><label>Контактный телефон<input name="phone" minlength="7" maxlength="30" required value="${esc(item.phone||'')}"></label><label class="full">Описание<textarea name="description" minlength="20" maxlength="3000" required>${esc(item.description||'')}</textarea></label><label>Статус<select name="status"><option value="available">Доступно</option><option value="rented" ${item.status==='rented'?'selected':''}>Сдано</option></select></label></div><p class="error" role="alert"></p><div class="actions"><button type="submit">Сохранить объявление</button><a href="#/my">Отмена</a></div></form></section></div>`;
  bindForm('#editor',async data=>{['price','rooms','area','type_id'].forEach(k=>data[k]=Number(data[k]));await api('/listings'+(id?'/'+id:''),{method:id?'PUT':'POST',body:JSON.stringify(data)});location.hash='/my';notify('Объявление сохранено');});
}
async function confirmDelete(id,refresh) {
  const dialog=document.querySelector('#confirm'); dialog.returnValue='';dialog.showModal();
  dialog.onclose=async()=>{if(dialog.returnValue==='delete'){try{await api('/listings/'+id,{method:'DELETE',body:'{}'});notify('Объявление удалено');await refresh();}catch(e){notify(e.message)}}};
}
async function my(version) {
  if(!guard())return;
  const items=await api('/my/listings');if(version!==routeVersion)return;
  app.innerHTML=`<div class="section-head"><div><h1>Мои объявления</h1><p class="muted">${esc(user.name)} · ${esc(user.email)}</p></div><a class="button" href="#/new">+ Разместить объявление</a></div><div class="grid">${items.length?items.map(x=>card(x,true)).join(''):'<div class="empty"><h2>У вас пока нет объявлений</h2><p class="muted">Добавьте жильё, которое хотите сдать в аренду.</p><a class="button" href="#/new">Разместить объявление</a></div>'}</div>`;
  document.querySelectorAll('.delete-listing').forEach(b=>b.onclick=()=>confirmDelete(b.dataset.id,route));
}
async function requests(version) {
  if(!guard())return;
  const items=await api('/my/requests');if(version!==routeVersion)return;
  function rows(incoming) {
    const subset=items.filter(x=>incoming?x.owner_id===user.id:x.tenant_id===user.id);
    return subset.length?subset.map(x=>`<div class="list-row"><div class="row-top"><h3><a href="#/listing/${x.listing_id}">${esc(x.title)}</a></h3><span class="tag">${labels[x.status]}</span></div><p class="muted">${incoming?esc(x.tenant_name)+' · ':''}Заселение ${date(x.move_in)}</p><p class="description">${esc(x.message||'Без сообщения')}</p>${x.status==='pending'?`<div class="actions">${incoming?`<button data-request="${x.id}" data-status="accepted">Принять</button><button class="secondary" data-request="${x.id}" data-status="rejected">Отклонить</button>`:`<button class="secondary" data-request="${x.id}" data-status="cancelled">Отменить заявку</button>`}</div>`:''}</div>`).join(''):'<p class="muted">Заявок пока нет.</p>';
  }
  app.innerHTML=`<h1>Заявки на аренду</h1><p class="muted">Здесь можно следить за ответами и рассматривать входящие заявки.</p><section class="panel"><h2>Мои заявки</h2>${rows(false)}</section><section class="panel auth-note"><h2>Заявки на мои объявления</h2>${rows(true)}</section>`;
  document.querySelectorAll('[data-request]').forEach(b=>b.onclick=async()=>{b.disabled=true;try{await api('/requests/'+b.dataset.request,{method:'PATCH',body:JSON.stringify({status:b.dataset.status})});await route();notify('Статус заявки обновлён');}catch(e){notify(e.message);b.disabled=false;}});
}
async function adminPage(params,version) {
  if(!guard())return;if(user.role!=='admin')throw new Error('Требуются права администратора');
  const tab=params.get('tab')==='users'?'users':'listings', page=Number(params.get('page')||1);
  const [stats,result]=await Promise.all([api('/admin/summary'),api(`/admin/${tab}?page=${page}`)]);if(version!==routeVersion)return;
  app.innerHTML=`<h1>Панель администратора</h1><p class="muted">Управление объявлениями и доступом пользователей.</p><div class="stats"><div class="panel">Пользователи<strong>${stats.users}</strong></div><div class="panel">Объявления<strong>${stats.listings}</strong></div><div class="panel">Заявки<strong>${stats.rental_requests}</strong></div></div><div class="tabs"><a class="${tab==='listings'?'active':''}" href="#/admin?tab=listings">Объявления</a><a class="${tab==='users'?'active':''}" href="#/admin?tab=users">Пользователи</a></div><div class="panel table-scroll"><table>${tab==='listings'?`<thead><tr><th>Объявление</th><th>Владелец</th><th>Статус</th><th>Действия</th></tr></thead><tbody>${result.items.map(x=>`<tr><td><a href="#/listing/${x.id}">${esc(x.title)}</a><br><span class="muted">${esc(x.city)} · ${money(x.price)} ₽</span></td><td>${esc(x.owner_name)}</td><td>${labels[x.status]}</td><td><div class="actions"><a href="#/edit/${x.id}">Изменить</a><button class="secondary delete-listing" data-id="${x.id}">Удалить</button></div></td></tr>`).join('')}</tbody>`:`<thead><tr><th>Имя и email</th><th>Роль</th><th>Доступ</th><th>Действия</th></tr></thead><tbody>${result.items.map(x=>`<tr><td>${esc(x.name)}<br><span class="muted">${esc(x.email)}</span></td><td>${x.role==='admin'?'Администратор':'Пользователь'}</td><td>${x.active?'Открыт':'Заблокирован'}</td><td>${x.role==='admin'?'—':`<button class="secondary" data-block="${x.id}" data-active="${x.active?0:1}">${x.active?'Заблокировать':'Разблокировать'}</button>`}</td></tr>`).join('')}</tbody>`}</table>${result.items.length?'':'<p>Записей пока нет.</p>'}</div>${result.total>20?pager(page,result.total,20):''}`;
  document.querySelectorAll('.delete-listing').forEach(b=>b.onclick=()=>confirmDelete(b.dataset.id,route));
  document.querySelectorAll('[data-block]').forEach(b=>b.onclick=async()=>{try{await api('/admin/users/'+b.dataset.block,{method:'PATCH',body:JSON.stringify({active:b.dataset.active==='1'})});await route();notify('Доступ пользователя изменён');}catch(e){notify(e.message)}});
  document.querySelectorAll('[data-page]').forEach(b=>b.onclick=()=>location.hash=`/admin?tab=${tab}&page=${b.dataset.page}`);
}
async function route() {
  const version=++routeVersion;
  const [path,query='']=(location.hash.slice(1)||'/').split('?'), parts=path.split('/').filter(Boolean), params=new URLSearchParams(query);
  app.innerHTML='<p class="muted" role="status">Загрузка…</p>';
  try {
    if(!parts.length)await catalog(params,version);
    else if(parts[0]==='login')auth();
    else if(parts[0]==='register')auth(true);
    else if(parts[0]==='listing' && /^\d+$/.test(parts[1]))await detail(parts[1],version);
    else if(parts[0]==='new')await editor(null,version);
    else if(parts[0]==='edit' && /^\d+$/.test(parts[1]))await editor(parts[1],version);
    else if(parts[0]==='my')await my(version);
    else if(parts[0]==='requests')await requests(version);
    else if(parts[0]==='admin')await adminPage(params,version);
    else throw new Error('Страница не найдена');
  } catch(e) { if(version===routeVersion)app.innerHTML=`<section class="empty"><h1>Не удалось открыть страницу</h1><p>${esc(e.message)}</p><a href="#/">Вернуться в каталог</a></section>`; }
  window.scrollTo(0,0);
}
window.addEventListener('hashchange',route);
(async()=>{try{types=await api('/types');try{user=await api('/auth/me')}catch{}renderNav();await route();}catch(e){app.innerHTML=`<p class="error">Сервис недоступен. ${esc(e.message)}</p>`}})();
