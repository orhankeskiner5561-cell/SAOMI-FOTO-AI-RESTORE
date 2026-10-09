-- MELEHAT channel rooms schema, staging only. Review and apply to Supabase after
-- validating actual auth/profile schema. NOT applied automatically by Android CI.
create table if not exists public.melehat_rooms (
  id uuid primary key default gen_random_uuid(),
  name text not null check (char_length(name) between 3 and 80),
  owner_id uuid not null references auth.users(id),
  listed boolean not null default true,
  created_at timestamptz not null default now()
);
create table if not exists public.melehat_room_members (
  room_id uuid not null references public.melehat_rooms(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null default 'member' check (role in ('owner','member')),
  joined_at timestamptz not null default now(),
  primary key(room_id,user_id)
);
create table if not exists public.melehat_room_requests (
  id uuid primary key default gen_random_uuid(),
  room_id uuid not null references public.melehat_rooms(id) on delete cascade,
  requester_id uuid not null references auth.users(id) on delete cascade,
  status text not null default 'pending' check (status in ('pending','approved','rejected')),
  created_at timestamptz not null default now(),
  reviewed_at timestamptz,
  reviewed_by uuid references auth.users(id),
  unique(room_id,requester_id)
);
create index if not exists melehat_room_requests_owner_idx on public.melehat_room_requests(room_id,status);
alter table public.melehat_rooms enable row level security;
alter table public.melehat_room_members enable row level security;
alter table public.melehat_room_requests enable row level security;
-- Deny access by default until policies and security-definer RPCs are reviewed.
-- Never grant direct INSERT/UPDATE on members or requests to anonymous clients.
-- Backend must atomically verify owner, approve request, and insert membership.
-- LiveKit token endpoint must verify room membership independently.
