-- AppHear remote conversation (remoteConversation flag): two phones paired with a QR code.
-- The host types; the viewer sees the text and the Text-to-ASL avatar.
--
-- Apply once in the Supabase dashboard (SQL Editor -> paste -> Run), then enable
-- Authentication -> Sign In / Providers -> "Allow anonymous sign-ins".
-- Safe to re-run: every object is created with IF NOT EXISTS / OR REPLACE.
--
-- Security model:
-- * Clients never write the tables directly except message inserts by the host; everything else goes
--   through SECURITY DEFINER functions that check auth.uid().
-- * Row-level security: only the two members of a conversation can read it or its messages.
-- * Invites: 6-character code (32-symbol alphabet) + 128-bit secret (stored as SHA-256), single use,
--   10-minute expiry. Wrong codes are rate limited per user and globally.
-- * Retention: conversations idle for 30 minutes end; ended conversations and their messages are
--   deleted after 24 hours (pg_cron, every 5 minutes).

create extension if not exists pgcrypto;
create extension if not exists pg_cron;

create table if not exists public.remote_conversations (
    id uuid primary key default gen_random_uuid(),
    host_id uuid not null references auth.users(id) on delete cascade,
    host_name text not null default '' check (char_length(host_name) <= 40),
    viewer_id uuid references auth.users(id) on delete set null,
    viewer_name text not null default '' check (char_length(viewer_name) <= 40),
    invite_code text unique,
    invite_secret_hash bytea,
    invite_expires_at timestamptz,
    viewer_seen_seq bigint not null default 0,
    created_at timestamptz not null default now(),
    last_activity_at timestamptz not null default now(),
    ended_at timestamptz,
    ended_by uuid
);

create table if not exists public.remote_conversation_messages (
    id uuid primary key,
    conversation_id uuid not null references public.remote_conversations(id) on delete cascade,
    seq bigint generated always as identity,
    sender_id uuid not null default auth.uid(),
    body text not null check (char_length(body) between 1 and 500),
    created_at timestamptz not null default now()
);
alter table public.remote_conversations add column if not exists viewer_name text not null default ''
    check (char_length(viewer_name) <= 40);

create index if not exists remote_conversation_messages_order
    on public.remote_conversation_messages (conversation_id, seq);

create table if not exists public.remote_join_attempts (
    user_id uuid,
    ok boolean not null,
    at timestamptz not null default now()
);
create index if not exists remote_join_attempts_at on public.remote_join_attempts (at);

alter table public.remote_conversations enable row level security;
alter table public.remote_conversation_messages enable row level security;
alter table public.remote_join_attempts enable row level security; -- no policies: functions only

drop policy if exists remote_conversations_members_read on public.remote_conversations;
create policy remote_conversations_members_read on public.remote_conversations
    for select to authenticated using (auth.uid() = host_id or auth.uid() = viewer_id);

drop policy if exists remote_messages_members_read on public.remote_conversation_messages;
create policy remote_messages_members_read on public.remote_conversation_messages
    for select to authenticated using (exists (
        select 1 from public.remote_conversations c
        where c.id = conversation_id and (auth.uid() = c.host_id or auth.uid() = c.viewer_id)));

-- Only the host sends, only after a viewer joined, only while the conversation is open.
drop policy if exists remote_messages_host_insert on public.remote_conversation_messages;
create policy remote_messages_host_insert on public.remote_conversation_messages
    for insert to authenticated with check (sender_id = auth.uid() and exists (
        select 1 from public.remote_conversations c
        where c.id = conversation_id and c.host_id = auth.uid()
          and c.viewer_id is not null and c.ended_at is null));

revoke all on public.remote_conversations, public.remote_conversation_messages, public.remote_join_attempts
    from anon, authenticated;
grant select on public.remote_conversations to authenticated;
grant select, insert (id, conversation_id, body) on public.remote_conversation_messages to authenticated;

create or replace function public.remote_touch_on_message() returns trigger
language plpgsql security definer set search_path = public as $$
begin
    update public.remote_conversations set last_activity_at = now() where id = new.conversation_id;
    return new;
end $$;
drop trigger if exists remote_touch_on_message on public.remote_conversation_messages;
create trigger remote_touch_on_message after insert on public.remote_conversation_messages
    for each row execute function public.remote_touch_on_message();

-- New random invite for a conversation row. Retries the rare code collision.
create or replace function public.remote_new_invite(p_id uuid,
    out code text, out secret text, out expires_at timestamptz)
language plpgsql security definer set search_path = public as $$
declare
    alphabet constant text := 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    raw bytea;
begin
    secret := encode(gen_random_bytes(16), 'hex');
    expires_at := now() + interval '10 minutes';
    for attempt in 1..8 loop
        raw := gen_random_bytes(6);
        code := '';
        for i in 0..5 loop
            code := code || substr(alphabet, (get_byte(raw, i) % 32) + 1, 1);
        end loop;
        begin
            update public.remote_conversations
               set invite_code = code, invite_secret_hash = digest(secret, 'sha256'),
                   invite_expires_at = expires_at, last_activity_at = now()
             where id = p_id;
            return;
        exception when unique_violation then
            -- try another code
        end;
    end loop;
    raise exception 'invite_code_exhausted';
end $$;
revoke all on function public.remote_new_invite(uuid) from public, anon, authenticated;

create or replace function public.create_remote_conversation(p_host_name text)
returns table (id uuid, code text, secret text, expires_at timestamptz)
language plpgsql security definer set search_path = public as $$
declare
    uid uuid := auth.uid();
    new_id uuid;
    invite record;
begin
    if uid is null then raise exception 'not_signed_in'; end if;
    -- One open conversation per host: starting a new one ends the old one.
    update public.remote_conversations c set ended_at = now(), ended_by = uid
     where c.host_id = uid and c.ended_at is null;
    insert into public.remote_conversations (host_id, host_name)
    values (uid, left(coalesce(trim(p_host_name), ''), 40)) returning remote_conversations.id into new_id;
    select * into invite from public.remote_new_invite(new_id);
    return query select new_id, invite.code, invite.secret, invite.expires_at;
end $$;

create or replace function public.renew_remote_invite(p_id uuid)
returns table (code text, secret text, expires_at timestamptz)
language plpgsql security definer set search_path = public as $$
begin
    if not exists (select 1 from public.remote_conversations c
                    where c.id = p_id and c.host_id = auth.uid()
                      and c.viewer_id is null and c.ended_at is null) then
        raise exception 'not_allowed';
    end if;
    return query select * from public.remote_new_invite(p_id);
end $$;

-- Returns a status instead of raising so failed attempts stay recorded for the rate limit.
-- status: joined | invalid | rate_limited | own_invite | not_signed_in
drop function if exists public.join_remote_conversation(text, text);
create or replace function public.join_remote_conversation(p_code text, p_secret text default null,
    p_viewer_name text default '')
returns table (status text, id uuid, host_name text)
language plpgsql security definer set search_path = public as $$
declare
    uid uuid := auth.uid();
    normalized text := upper(regexp_replace(coalesce(p_code, ''), '[^A-Za-z0-9]', '', 'g'));
    target public.remote_conversations%rowtype;
begin
    if uid is null then return query select 'not_signed_in', null::uuid, null::text; return; end if;
    if (select count(*) from public.remote_join_attempts a
         where a.user_id = uid and not a.ok and a.at > now() - interval '1 minute') >= 5
       or (select count(*) from public.remote_join_attempts a
            where not a.ok and a.at > now() - interval '1 minute') >= 60 then
        return query select 'rate_limited', null::uuid, null::text; return;
    end if;
    select * into target from public.remote_conversations c
     where c.invite_code = normalized and c.invite_expires_at > now()
       and c.ended_at is null and c.viewer_id is null
     for update;
    if not found or (p_secret is not null and target.invite_secret_hash <> digest(p_secret, 'sha256')) then
        insert into public.remote_join_attempts (user_id, ok) values (uid, false);
        return query select 'invalid', null::uuid, null::text; return;
    end if;
    if target.host_id = uid then
        return query select 'own_invite', null::uuid, null::text; return;
    end if;
    update public.remote_conversations c
       set viewer_id = uid, viewer_name = left(coalesce(trim(p_viewer_name), ''), 40), invite_code = null, invite_secret_hash = null, invite_expires_at = null,
           last_activity_at = now()
     where c.id = target.id;
    insert into public.remote_join_attempts (user_id, ok) values (uid, true);
    return query select 'joined', target.id, target.host_name;
end $$;

-- Keeps an open conversation alive and reports whether it has ended. Members only.
create or replace function public.touch_remote_conversation(p_id uuid)
returns boolean
language plpgsql security definer set search_path = public as $$
declare ended timestamptz;
begin
    update public.remote_conversations c set last_activity_at = now()
     where c.id = p_id and (c.host_id = auth.uid() or c.viewer_id = auth.uid()) and c.ended_at is null;
    select c.ended_at into ended from public.remote_conversations c
     where c.id = p_id and (c.host_id = auth.uid() or c.viewer_id = auth.uid());
    return not found or ended is not null;
end $$;

create or replace function public.mark_remote_seen(p_id uuid, p_seq bigint)
returns void
language sql security definer set search_path = public as $$
    update public.remote_conversations c
       set viewer_seen_seq = greatest(c.viewer_seen_seq, p_seq), last_activity_at = now()
     where c.id = p_id and c.viewer_id = auth.uid() and c.ended_at is null;
$$;

create or replace function public.end_remote_conversation(p_id uuid)
returns void
language sql security definer set search_path = public as $$
    update public.remote_conversations c set ended_at = now(), ended_by = auth.uid()
     where c.id = p_id and (c.host_id = auth.uid() or c.viewer_id = auth.uid()) and c.ended_at is null;
$$;

revoke all on function public.create_remote_conversation(text), public.renew_remote_invite(uuid),
    public.join_remote_conversation(text, text, text), public.touch_remote_conversation(uuid),
    public.mark_remote_seen(uuid, bigint), public.end_remote_conversation(uuid) from public, anon;
grant execute on function public.create_remote_conversation(text), public.renew_remote_invite(uuid),
    public.join_remote_conversation(text, text, text), public.touch_remote_conversation(uuid),
    public.mark_remote_seen(uuid, bigint), public.end_remote_conversation(uuid) to authenticated;

-- Live updates: new messages and conversation changes (viewer joined, seen, ended) reach members only (RLS).
do $$ begin
    alter publication supabase_realtime add table public.remote_conversations;
exception when duplicate_object then null; end $$;
do $$ begin
    alter publication supabase_realtime add table public.remote_conversation_messages;
exception when duplicate_object then null; end $$;

-- Cleanup every 5 minutes.
select cron.unschedule(jobid) from cron.job where jobname = 'remote-conversation-cleanup';
select cron.schedule('remote-conversation-cleanup', '*/5 * * * *', $cron$
    update public.remote_conversations set ended_at = now()
     where ended_at is null and last_activity_at < now() - interval '30 minutes';
    delete from public.remote_conversations where ended_at < now() - interval '24 hours';
    delete from public.remote_join_attempts where at < now() - interval '1 hour';
$cron$);
