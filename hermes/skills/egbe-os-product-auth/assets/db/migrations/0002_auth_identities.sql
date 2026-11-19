-- External identities are product-owned. Provider subject, not email, is the
-- immutable authority. Idempotent and safe after 0001_auth.sql.
create table if not exists auth_identities (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references users(id) on delete cascade,
  provider      text not null,
  subject       text not null,
  email_at_link text not null,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

create unique index if not exists auth_identities_provider_subject_key
  on auth_identities (provider, subject);
create index if not exists auth_identities_user_id_idx
  on auth_identities (user_id);
