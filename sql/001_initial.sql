PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL CHECK(length(name) BETWEEN 2 AND 80),
 email TEXT NOT NULL UNIQUE COLLATE NOCASE, password_hash TEXT NOT NULL,
 role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('user','admin')),
 active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS sessions (
 token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 csrf_token TEXT NOT NULL, expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS property_types (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS listings (
 id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL REFERENCES users(id),
 type_id INTEGER NOT NULL REFERENCES property_types(id), title TEXT NOT NULL,
 description TEXT NOT NULL, city TEXT NOT NULL, address TEXT NOT NULL,
 price INTEGER NOT NULL CHECK(price BETWEEN 1000 AND 10000000),
 rooms INTEGER NOT NULL CHECK(rooms BETWEEN 0 AND 20), area REAL NOT NULL CHECK(area BETWEEN 5 AND 10000),
 phone TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'available' CHECK(status IN ('available','rented')),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS rental_requests (
 id INTEGER PRIMARY KEY, listing_id INTEGER NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
 tenant_id INTEGER NOT NULL REFERENCES users(id), move_in TEXT NOT NULL, message TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','accepted','rejected','cancelled')),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_listings_catalog ON listings(status, city, price);
CREATE INDEX IF NOT EXISTS idx_listings_owner ON listings(owner_id);
CREATE INDEX IF NOT EXISTS idx_requests_tenant ON rental_requests(tenant_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_request_active ON rental_requests(listing_id, tenant_id) WHERE status IN ('pending','accepted');
CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);
PRAGMA user_version = 1;
