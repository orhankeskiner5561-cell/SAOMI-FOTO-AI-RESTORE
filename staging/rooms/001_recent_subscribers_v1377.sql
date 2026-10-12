-- MELEHAT TELSİZ v1.3.77 — authenticated new-subscriber directory
-- Read-only recent membership, with server-observed online status.
create or replace function public.melehat_recent_subscribers()
returns table(user_id uuid, full_name text, created_at_ms bigint, online boolean)
language sql stable security definer set search_path = pg_catalog, public
as $function$
 select p.user_id,
   coalesce(nullif(btrim(p.full_name), ''), 'Üye')::text,
   floor(extract(epoch from p.created_at)*1000)::bigint,
   (
    exists(select 1 from public.melehat_p2p_native_presence n
      where n.user_id=p.user_id and n.last_seen_at>now()-interval '15 seconds')
    or exists(select 1 from public.melehat_live_room_presence l
      where l.user_id=p.user_id and l.last_seen_at>now()-interval '20 seconds')
    or exists(select 1 from public.melehat_video_online_presence v
      where v.user_id=p.user_id and v.last_seen_at>now()-interval '20 seconds')
   )::boolean
 from public.profiles p
 where auth.uid() is not null
   and exists(select 1 from public.profiles me where me.user_id=auth.uid())
 order by p.created_at desc, p.user_id
 limit 200;
$function$;
revoke all on function public.melehat_recent_subscribers() from public, anon;
grant execute on function public.melehat_recent_subscribers() to authenticated;
