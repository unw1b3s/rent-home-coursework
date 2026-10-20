"""python -m app.seed — добавить демонстрационные данные в пустую базу."""
from app.db import init_db, connect, ROOT
from app.security import hash_password

def seed():
    init_db()
    with connect() as db:
        if db.execute('SELECT COUNT(*) FROM users').fetchone()[0]:
            print('База содержит пользователей. Seed пропущен, данные сохранены.')
            return
        for name, email, role in [('Администратор','admin@example.com','admin'),
                                   ('Анна','owner@example.com','user'),
                                   ('Иван','tenant@example.com','user')]:
            db.execute('INSERT INTO users(name,email,password_hash,role) VALUES (?,?,?,?)',
                       (name,email,hash_password('demo12345'),role))
        db.commit()
        # Справочник уже создан миграцией.
        sql = (ROOT / 'sql/seed.sql').read_text().replace('INSERT INTO property_types', 'INSERT OR IGNORE INTO property_types')
        db.executescript(sql)
    print('Созданы 3 учебных пользователя и 8 объявлений. Пароль: demo12345')

if __name__ == '__main__':
    seed()
