BEGIN;
ALTER TABLE public.claims ADD COLUMN IF NOT EXISTS current_version integer NOT NULL DEFAULT 0;
ALTER TABLE public.policies ADD COLUMN IF NOT EXISTS insured_vehicle_plate text;
ALTER TABLE public.policies ADD COLUMN IF NOT EXISTS policy_claim_type text;
ALTER TABLE public.policies ADD COLUMN IF NOT EXISTS source_reference text;
ALTER TABLE public.policies ADD COLUMN IF NOT EXISTS verified_at timestamptz;
ALTER TABLE public.policies ADD COLUMN IF NOT EXISTS terms jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE public.preliminary_analyses ADD COLUMN IF NOT EXISTS analysis_payload jsonb NOT NULL DEFAULT '{}'::jsonb;
CREATE TABLE IF NOT EXISTS public.claim_revisions(
 claim_number text NOT NULL,claim_version integer NOT NULL,payload jsonb NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(claim_number,claim_version),CHECK(claim_version>=0));
INSERT INTO public.claim_revisions(claim_number,claim_version,payload)
 SELECT claim_number,0,jsonb_build_object('legacy_snapshot',true,'claim_number',claim_number,'policy_number',policy_number,'claim_type',claim_type,'accident_date',accident_date,'vehicle_plate',vehicle_plate,'incident_description',incident_description)
 FROM public.claims WHERE current_version=0 ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS public.review_resolution_events(
 event_id text PRIMARY KEY,case_id text NOT NULL,claim_version integer NOT NULL,payload jsonb NOT NULL,created_at timestamptz DEFAULT now());
CREATE OR REPLACE FUNCTION public.insurance_review_task_state() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE resolved integer;
BEGIN
 SELECT max(e.claim_version) INTO resolved FROM public.review_resolution_events e WHERE e.case_id=NEW.claim_id;
 IF resolved>NEW.claim_version THEN NEW.review_status:='CANCELLED';
 ELSIF resolved=NEW.claim_version THEN NEW.review_status:='RESOLVED'; END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS insurance_review_task_state_trigger ON public.review_tasks;
CREATE TRIGGER insurance_review_task_state_trigger BEFORE INSERT ON public.review_tasks FOR EACH ROW EXECUTE FUNCTION public.insurance_review_task_state();
CREATE OR REPLACE FUNCTION public.insurance_record_claim(data jsonb)
RETURNS TABLE(id bigint,claim_number varchar,status varchar,created_at timestamptz) LANGUAGE plpgsql AS $$
DECLARE prior jsonb; requested integer;
BEGIN
 requested:=(data->>'claim_version')::integer;
 IF requested<1 THEN RAISE EXCEPTION 'Invalid claim version'; END IF;
 PERFORM pg_advisory_xact_lock(hashtext(data->>'claim_number'));
 SELECT r.payload INTO prior FROM public.claim_revisions r WHERE r.claim_number=data->>'claim_number' AND r.claim_version=requested;
 IF prior IS NOT NULL AND prior IS DISTINCT FROM data THEN RAISE EXCEPTION 'Immutable claim revision conflict'; END IF;
 INSERT INTO public.claim_revisions(claim_number,claim_version,payload) VALUES(data->>'claim_number',requested,data) ON CONFLICT DO NOTHING;
 INSERT INTO public.claims AS c(claim_number,policy_number,claim_type,accident_date,vehicle_plate,incident_description,current_version)
 VALUES(data->>'claim_number',data->>'policy_number',data->>'claim_type',(data->>'accident_date')::date,data->>'vehicle_plate',data->>'incident_description',requested)
 ON CONFLICT ON CONSTRAINT claims_claim_number_key DO UPDATE SET
 policy_number=EXCLUDED.policy_number,claim_type=EXCLUDED.claim_type,accident_date=EXCLUDED.accident_date,
 vehicle_plate=EXCLUDED.vehicle_plate,incident_description=EXCLUDED.incident_description,current_version=EXCLUDED.current_version
 WHERE c.current_version<=EXCLUDED.current_version;
 RETURN QUERY SELECT c.id,c.claim_number,c.status,c.created_at FROM public.claims c WHERE c.claim_number=data->>'claim_number';
END $$;
CREATE OR REPLACE FUNCTION public.insurance_save_analysis(data jsonb)
RETURNS SETOF public.preliminary_analyses LANGUAGE plpgsql AS $$
DECLARE old public.preliminary_analyses;
BEGIN
 SELECT * INTO old FROM public.preliminary_analyses p WHERE p.job_id=data->>'job_id';
 IF FOUND AND (old.claim_id IS DISTINCT FROM data->>'claim_id' OR old.claim_version IS DISTINCT FROM (data->>'claim_version')::integer) THEN RAISE EXCEPTION 'Analysis identity conflict'; END IF;
 INSERT INTO public.preliminary_analyses(job_id,claim_id,claim_version,analysis_type,analysis_status,summary,findings,missing_information,recommendation,requires_human_review,analysis_payload)
 VALUES(data->>'job_id',data->>'claim_id',(data->>'claim_version')::integer,data->>'analysis_type',data->>'analysis_status',data->>'summary',COALESCE(data->'findings','[]'::jsonb),COALESCE(data->'missing_information','[]'::jsonb),'REFER_TO_HUMAN_REVIEW',true,data)
 ON CONFLICT(job_id) DO NOTHING;
 RETURN QUERY SELECT * FROM public.preliminary_analyses p WHERE p.job_id=data->>'job_id';
END $$;
CREATE OR REPLACE FUNCTION public.insurance_resolve_review(data jsonb)
RETURNS TABLE(event_id text,status text) LANGUAGE plpgsql AS $$
DECLARE old jsonb;
BEGIN
 IF data->>'decision' NOT IN ('approve','reject') OR length(trim(COALESCE(data->>'note','')))=0 THEN RAISE EXCEPTION 'Invalid review event'; END IF;
 SELECT e.payload INTO old FROM public.review_resolution_events e WHERE e.event_id=data->>'event_id';
 IF FOUND AND old IS DISTINCT FROM data THEN RAISE EXCEPTION 'Review event conflict'; END IF;
 INSERT INTO public.review_resolution_events(event_id,case_id,claim_version,payload) VALUES(data->>'event_id',data->>'case_id',(data->>'claim_version')::integer,data) ON CONFLICT DO NOTHING;
 UPDATE public.review_tasks t SET review_status='RESOLVED' WHERE t.claim_id=data->>'case_id' AND t.claim_version=(data->>'claim_version')::integer AND t.review_status IN ('PENDING','IN_PROGRESS');
 UPDATE public.review_tasks t SET review_status='CANCELLED' WHERE t.claim_id=data->>'case_id' AND t.claim_version<(data->>'claim_version')::integer AND t.review_status IN ('PENDING','IN_PROGRESS');
 RETURN QUERY SELECT data->>'event_id','synced'::text;
END $$;
COMMIT;
