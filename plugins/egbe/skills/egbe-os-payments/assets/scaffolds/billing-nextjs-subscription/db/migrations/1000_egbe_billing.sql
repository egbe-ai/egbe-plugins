-- Canonical subscription foundation. Product-specific usage and quota tables
-- belong in later migrations.

create table if not exists billing_provider_bindings (
  plan_key            text primary key,
  provider_product_id text not null unique,
  provider_price_id   text not null unique,
  catalog_digest      text not null,
  synced_at           timestamptz not null default now()
);

create table if not exists account_billing (
  account_id               uuid primary key references users(id) on delete cascade,
  plan_key                 text not null default 'free',
  subscription_status      text not null default 'free',
  provider_customer_id     text unique,
  provider_subscription_id text unique,
  provider_price_id        text,
  current_period_end       timestamptz,
  cancel_at_period_end     boolean not null default false,
  last_event_id            text,
  last_event_created       bigint not null default 0,
  updated_at               timestamptz not null default now(),
  check (subscription_status in ('free', 'trialing', 'active', 'past_due', 'canceling', 'paused', 'canceled'))
);

create table if not exists billing_checkout_attempts (
  id                  uuid primary key default gen_random_uuid(),
  account_id          uuid not null references users(id) on delete cascade,
  plan_key            text not null,
  idempotency_key     text not null unique default gen_random_uuid()::text,
  return_path         text not null,
  attribution         jsonb not null default '{}'::jsonb,
  status              text not null default 'pending',
  provider_session_id text,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now(),
  check (status in ('pending', 'created', 'completed', 'abandoned', 'failed'))
);

create unique index if not exists billing_checkout_attempts_active_key
  on billing_checkout_attempts (account_id, plan_key)
  where status in ('pending', 'created');

create table if not exists processed_payment_events (
  event_id     text primary key,
  event_type   text not null,
  event_created bigint not null,
  account_id   uuid references users(id) on delete set null,
  processed_at timestamptz not null default now()
);

create table if not exists entitlement_grants (
  id          uuid primary key default gen_random_uuid(),
  account_id  uuid not null references users(id) on delete cascade,
  capability  text not null,
  source      text not null,
  active_from timestamptz not null default now(),
  active_until timestamptz,
  revoked_at  timestamptz,
  created_at  timestamptz not null default now(),
  unique (account_id, capability, source)
);

create index if not exists entitlement_grants_account_capability_idx
  on entitlement_grants (account_id, capability);
