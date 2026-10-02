-- JobBot schema. Safe to re-run (IF NOT EXISTS everywhere).

CREATE TABLE IF NOT EXISTS users (
    chat_id       BIGINT PRIMARY KEY,
    username      TEXT,
    first_name    TEXT,
    status        TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending', 'active', 'paused', 'blocked')),
    is_admin      BOOLEAN NOT NULL DEFAULT FALSE,
    ng_quota      SMALLINT NOT NULL DEFAULT 4 CHECK (ng_quota BETWEEN 0 AND 10),
    global_quota  SMALLINT NOT NULL DEFAULT 6 CHECK (global_quota BETWEEN 0 AND 10),
    invite_code   TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS invites (
    code        TEXT PRIMARY KEY,
    created_by  BIGINT,
    max_uses    INTEGER NOT NULL DEFAULT 1,
    uses        INTEGER NOT NULL DEFAULT 0,
    expires_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS profiles (
    chat_id     BIGINT PRIMARY KEY REFERENCES users(chat_id) ON DELETE CASCADE,
    data        JSONB NOT NULL DEFAULT '{}'::jsonb,
    cv_text     TEXT,
    cv_file_id  TEXT,
    built_at    TIMESTAMPTZ,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Cache of jobs that were sent to someone (needed for Tailor + feedback re-ranking).
CREATE TABLE IF NOT EXISTS jobs (
    id           TEXT PRIMARY KEY,
    source       TEXT NOT NULL,
    url          TEXT NOT NULL,
    title        TEXT NOT NULL,
    company      TEXT NOT NULL,
    description  TEXT NOT NULL DEFAULT '',
    location     TEXT NOT NULL DEFAULT '',
    remote       BOOLEAN NOT NULL DEFAULT FALSE,
    region       TEXT NOT NULL CHECK (region IN ('NG', 'GLOBAL')),
    posted_at    TIMESTAMPTZ,
    embedding    REAL[],
    fetched_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sent (
    chat_id     BIGINT NOT NULL REFERENCES users(chat_id) ON DELETE CASCADE,
    job_id      TEXT NOT NULL,
    dedupe_key  TEXT NOT NULL,
    score       REAL,
    sent_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (chat_id, job_id)
);
CREATE INDEX IF NOT EXISTS sent_chat_key_idx ON sent (chat_id, dedupe_key);
CREATE INDEX IF NOT EXISTS sent_at_idx ON sent (sent_at);

CREATE TABLE IF NOT EXISTS feedback (
    chat_id     BIGINT NOT NULL REFERENCES users(chat_id) ON DELETE CASCADE,
    job_id      TEXT NOT NULL,
    action      TEXT NOT NULL CHECK (action IN ('save', 'dismiss')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (chat_id, job_id)
);

CREATE TABLE IF NOT EXISTS runs (
    id           BIGSERIAL PRIMARY KEY,
    slot         TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'running',
    started_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at  TIMESTAMPTZ,
    stats        JSONB,
    error        TEXT
);

-- Simple migration bookkeeping.
CREATE TABLE IF NOT EXISTS schema_migrations (
    name        TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
