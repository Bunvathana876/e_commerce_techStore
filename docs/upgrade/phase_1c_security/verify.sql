-- Run only after apply, through verified protected owner libpq service.
-- This is read-only. EXPLAIN without ANALYZE never executes writes or reads rows.
\set ON_ERROR_STOP on
BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout='10s';
SET LOCAL lock_timeout='2s';
\ir deny_assertions.sql
DO $negative$
DECLARE r text; t text; q text;
BEGIN
  FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
    EXECUTE format('SET LOCAL ROLE %I',r);
    FOREACH t IN ARRAY ARRAY['users','user_sessions','refresh_tokens'] LOOP
      FOREACH q IN ARRAY ARRAY[
        format('SELECT * FROM public.%I LIMIT 0',t),
        format('EXPLAIN SELECT * FROM public.%I LIMIT 0',t),
        format('EXPLAIN INSERT INTO public.%I DEFAULT VALUES',t),
        format('EXPLAIN UPDATE public.%I SET id=id WHERE false',t),
        format('EXPLAIN DELETE FROM public.%I WHERE false',t)
      ] LOOP
        BEGIN
          EXECUTE q;
          RAISE EXCEPTION 'FAIL: role % unexpectedly allowed statement on %',r,t;
        EXCEPTION WHEN insufficient_privilege THEN NULL;
        END;
      END LOOP;
    END LOOP;
    RESET ROLE;
  END LOOP;
END
$negative$;
SELECT 'PASS: all API roles denied SELECT and DML planning; no records accessed' AS result;
ROLLBACK;
