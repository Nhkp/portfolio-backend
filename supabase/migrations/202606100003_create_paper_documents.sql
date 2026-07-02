create table if not exists public.paper_documents (
  id uuid primary key default gen_random_uuid(),
  filename text not null unique,
  content_type text not null default 'application/pdf',
  storage_bucket text not null,
  storage_path text not null unique,
  size_bytes integer not null check (size_bytes > 0),
  checksum_sha256 char(64) not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists set_paper_documents_updated_at on public.paper_documents;
create trigger set_paper_documents_updated_at
before update on public.paper_documents
for each row
execute function public.set_updated_at();

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('papers', 'papers', false, 10485760, array['application/pdf'])
on conflict (id) do update set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

insert into public.paper_documents (
  filename,
  content_type,
  storage_bucket,
  storage_path,
  size_bytes,
  checksum_sha256
)
values
  (
    'hyperparameters_analysis.pdf',
    'application/pdf',
    'papers',
    'data/hyperparameters_analysis.pdf',
    2861816,
    '7e7de85a90511db5ffc55b251e097e2fef0d1dcf1db0b1245bf21a0834e6a374'
  ),
  (
    'openradioss_article_v2.pdf',
    'application/pdf',
    'papers',
    'data/openradioss_article_v2.pdf',
    404996,
    '9c68b1b1682d2e0ed4f1d18043797ae4668b5d4cada836a6b4ab874b111f9210'
  )
on conflict (filename) do update set
  content_type = excluded.content_type,
  storage_bucket = excluded.storage_bucket,
  storage_path = excluded.storage_path,
  size_bytes = excluded.size_bytes,
  checksum_sha256 = excluded.checksum_sha256;
