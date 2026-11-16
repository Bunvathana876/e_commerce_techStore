-- Read-only assertions. Does not fetch application rows or advance sequences.
DO $verify$
DECLARE r text; t text; p text; s text;
BEGIN
  FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
    FOREACH t IN ARRAY ARRAY['users','user_sessions','refresh_tokens'] LOOP
      FOREACH p IN ARRAY ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER','MAINTAIN'] LOOP
        IF has_table_privilege(r,format('public.%I',t),p) THEN
          RAISE EXCEPTION 'FAIL: residual % privilege for % on %',p,r,t;
        END IF;
      END LOOP;
      FOREACH p IN ARRAY ARRAY['SELECT','INSERT','UPDATE','REFERENCES'] LOOP
        IF has_any_column_privilege(r,format('public.%I',t),p) THEN
          RAISE EXCEPTION 'FAIL: residual column privilege for % on %',r,t;
        END IF;
      END LOOP;
    END LOOP;
    FOREACH s IN ARRAY ARRAY['users_id_seq','user_sessions_id_seq','refresh_tokens_id_seq'] LOOP
      FOREACH p IN ARRAY ARRAY['USAGE','SELECT','UPDATE'] LOOP
        IF has_sequence_privilege(r,format('public.%I',s),p) THEN
          RAISE EXCEPTION 'FAIL: residual sequence privilege for % on %',r,s;
        END IF;
      END LOOP;
    END LOOP;
  END LOOP;
  IF EXISTS (SELECT 1 FROM pg_class WHERE oid IN
     ('public.users'::regclass,'public.user_sessions'::regclass,'public.refresh_tokens'::regclass)
     AND (NOT relrowsecurity OR relforcerowsecurity)) THEN
    RAISE EXCEPTION 'FAIL: unexpected RLS flags';
  END IF;
END
$verify$;
