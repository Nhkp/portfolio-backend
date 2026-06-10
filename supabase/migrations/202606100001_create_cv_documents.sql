create table if not exists public.cv_documents (
  id uuid primary key default gen_random_uuid(),
  filename text not null,
  content_type text not null default 'application/pdf',
  storage_bucket text not null,
  storage_path text not null unique,
  size_bytes integer not null check (size_bytes > 0),
  checksum_sha256 char(64) not null,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists cv_documents_one_active_idx
  on public.cv_documents (is_active)
  where is_active;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists set_cv_documents_updated_at on public.cv_documents;
create trigger set_cv_documents_updated_at
before update on public.cv_documents
for each row
execute function public.set_updated_at();
