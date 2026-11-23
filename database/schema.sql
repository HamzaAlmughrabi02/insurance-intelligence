--
-- PostgreSQL database dump
--


-- Dumped from database version 17.12 (Debian 17.12-1.pgdg13+1)
-- Dumped by pg_dump version 17.12 (Debian 17.12-1.pgdg13+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: insurance_record_claim(jsonb); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.insurance_record_claim(data jsonb) RETURNS TABLE(id bigint, claim_number character varying, status character varying, created_at timestamp with time zone)
    LANGUAGE plpgsql
    AS $$
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


--
-- Name: insurance_resolve_review(jsonb); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.insurance_resolve_review(data jsonb) RETURNS TABLE(event_id text, status text)
    LANGUAGE plpgsql
    AS $$
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


--
-- Name: insurance_review_task_state(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.insurance_review_task_state() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE resolved integer;
BEGIN
 SELECT max(e.claim_version) INTO resolved FROM public.review_resolution_events e WHERE e.case_id=NEW.claim_id;
 IF resolved>NEW.claim_version THEN NEW.review_status:='CANCELLED';
 ELSIF resolved=NEW.claim_version THEN NEW.review_status:='RESOLVED'; END IF;
 RETURN NEW;
END $$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: preliminary_analyses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.preliminary_analyses (
    id bigint NOT NULL,
    job_id character varying(100) NOT NULL,
    claim_id character varying(100) NOT NULL,
    claim_version integer NOT NULL,
    analysis_type character varying(60) NOT NULL,
    analysis_status character varying(30) NOT NULL,
    summary text,
    findings jsonb DEFAULT '[]'::jsonb NOT NULL,
    missing_information jsonb DEFAULT '[]'::jsonb NOT NULL,
    recommendation character varying(100),
    requires_human_review boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    analysis_payload jsonb DEFAULT '{}'::jsonb NOT NULL
);


--
-- Name: insurance_save_analysis(jsonb); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.insurance_save_analysis(data jsonb) RETURNS SETOF public.preliminary_analyses
    LANGUAGE plpgsql
    AS $$
DECLARE old public.preliminary_analyses;
BEGIN
 SELECT * INTO old FROM public.preliminary_analyses p WHERE p.job_id=data->>'job_id';
 IF FOUND AND (old.claim_id IS DISTINCT FROM data->>'claim_id' OR old.claim_version IS DISTINCT FROM (data->>'claim_version')::integer) THEN RAISE EXCEPTION 'Analysis identity conflict'; END IF;
 INSERT INTO public.preliminary_analyses(job_id,claim_id,claim_version,analysis_type,analysis_status,summary,findings,missing_information,recommendation,requires_human_review,analysis_payload)
 VALUES(data->>'job_id',data->>'claim_id',(data->>'claim_version')::integer,data->>'analysis_type',data->>'analysis_status',data->>'summary',COALESCE(data->'findings','[]'::jsonb),COALESCE(data->'missing_information','[]'::jsonb),'REFER_TO_HUMAN_REVIEW',true,data)
 ON CONFLICT(job_id) DO NOTHING;
 RETURN QUERY SELECT * FROM public.preliminary_analyses p WHERE p.job_id=data->>'job_id';
END $$;


--
-- Name: claim_ai_analysis; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.claim_ai_analysis (
    id bigint NOT NULL,
    claim_id character varying(100) NOT NULL,
    analysis_summary text NOT NULL,
    missing_information jsonb NOT NULL,
    coverage_verified boolean DEFAULT false NOT NULL,
    requires_supervisor_review boolean DEFAULT true NOT NULL,
    recommended_next_action text NOT NULL,
    validation_status character varying(30) DEFAULT 'passed'::character varying NOT NULL,
    approval_status character varying(30) DEFAULT 'pending_supervisor'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_ai_no_coverage_approval CHECK ((coverage_verified = false)),
    CONSTRAINT chk_ai_pending_approval CHECK (((approval_status)::text = 'pending_supervisor'::text)),
    CONSTRAINT chk_ai_review_required CHECK ((requires_supervisor_review = true)),
    CONSTRAINT chk_ai_validation CHECK (((validation_status)::text = 'passed'::text)),
    CONSTRAINT chk_missing_information_array CHECK ((jsonb_typeof(missing_information) = 'array'::text))
);


--
-- Name: claim_ai_analysis_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.claim_ai_analysis_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: claim_ai_analysis_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.claim_ai_analysis_id_seq OWNED BY public.claim_ai_analysis.id;


--
-- Name: claim_revisions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.claim_revisions (
    claim_number text NOT NULL,
    claim_version integer NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT claim_revisions_claim_version_check CHECK ((claim_version >= 0))
);


--
-- Name: claims; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.claims (
    id bigint NOT NULL,
    claim_number character varying(100) NOT NULL,
    policy_number character varying(100) NOT NULL,
    claim_type character varying(50) NOT NULL,
    accident_date date NOT NULL,
    vehicle_plate character varying(50) NOT NULL,
    incident_description text NOT NULL,
    status character varying(50) DEFAULT 'Draft'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    current_version integer DEFAULT 0 NOT NULL
);


--
-- Name: claims_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.claims_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: claims_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.claims_id_seq OWNED BY public.claims.id;


--
-- Name: policies; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.policies (
    id bigint NOT NULL,
    policy_number character varying(100) NOT NULL,
    insurer_name character varying(200) NOT NULL,
    effective_date date NOT NULL,
    expiry_date date NOT NULL,
    policy_status character varying(30) DEFAULT 'UNVERIFIED'::character varying NOT NULL,
    source_verified boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    insured_vehicle_plate text,
    policy_claim_type text,
    source_reference text,
    verified_at timestamp with time zone,
    terms jsonb DEFAULT '{}'::jsonb NOT NULL,
    CONSTRAINT test_policy_dates_valid CHECK ((expiry_date >= effective_date)),
    CONSTRAINT test_policy_status_valid CHECK (((policy_status)::text = ANY ((ARRAY['UNVERIFIED'::character varying, 'ACTIVE'::character varying, 'EXPIRED'::character varying, 'CANCELLED'::character varying])::text[])))
);


--
-- Name: policies_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.policies_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: policies_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.policies_id_seq OWNED BY public.policies.id;


--
-- Name: preliminary_analyses_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.preliminary_analyses_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: preliminary_analyses_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.preliminary_analyses_id_seq OWNED BY public.preliminary_analyses.id;


--
-- Name: review_resolution_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.review_resolution_events (
    event_id text NOT NULL,
    case_id text NOT NULL,
    claim_version integer NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: review_tasks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.review_tasks (
    id bigint NOT NULL,
    claim_id character varying(100) NOT NULL,
    claim_version integer NOT NULL,
    job_id character varying(100) NOT NULL,
    correlation_id character varying(100),
    review_type character varying(100) NOT NULL,
    review_status character varying(30) DEFAULT 'PENDING'::character varying NOT NULL,
    policy_number character varying(100),
    review_reasons jsonb DEFAULT '[]'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    resolved_at timestamp with time zone,
    CONSTRAINT review_task_status_valid CHECK (((review_status)::text = ANY ((ARRAY['PENDING'::character varying, 'IN_PROGRESS'::character varying, 'RESOLVED'::character varying, 'CANCELLED'::character varying])::text[]))),
    CONSTRAINT review_task_version_valid CHECK ((claim_version > 0))
);


--
-- Name: review_tasks_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.review_tasks_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: review_tasks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.review_tasks_id_seq OWNED BY public.review_tasks.id;


--
-- Name: system_test; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.system_test (
    id integer NOT NULL,
    test_message text NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: claim_ai_analysis id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.claim_ai_analysis ALTER COLUMN id SET DEFAULT nextval('public.claim_ai_analysis_id_seq'::regclass);


--
-- Name: claims id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.claims ALTER COLUMN id SET DEFAULT nextval('public.claims_id_seq'::regclass);


--
-- Name: policies id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.policies ALTER COLUMN id SET DEFAULT nextval('public.policies_id_seq'::regclass);


--
-- Name: preliminary_analyses id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.preliminary_analyses ALTER COLUMN id SET DEFAULT nextval('public.preliminary_analyses_id_seq'::regclass);


--
-- Name: review_tasks id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.review_tasks ALTER COLUMN id SET DEFAULT nextval('public.review_tasks_id_seq'::regclass);


--
-- Name: claim_ai_analysis claim_ai_analysis_claim_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.claim_ai_analysis
    ADD CONSTRAINT claim_ai_analysis_claim_id_key UNIQUE (claim_id);


--
-- Name: claim_ai_analysis claim_ai_analysis_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.claim_ai_analysis
    ADD CONSTRAINT claim_ai_analysis_pkey PRIMARY KEY (id);


--
-- Name: claim_revisions claim_revisions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.claim_revisions
    ADD CONSTRAINT claim_revisions_pkey PRIMARY KEY (claim_number, claim_version);


--
-- Name: claims claims_claim_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.claims
    ADD CONSTRAINT claims_claim_number_key UNIQUE (claim_number);


--
-- Name: claims claims_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.claims
    ADD CONSTRAINT claims_pkey PRIMARY KEY (id);


--
-- Name: policies policies_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.policies
    ADD CONSTRAINT policies_pkey PRIMARY KEY (id);


--
-- Name: policies policies_policy_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.policies
    ADD CONSTRAINT policies_policy_number_key UNIQUE (policy_number);


--
-- Name: preliminary_analyses preliminary_analyses_job_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.preliminary_analyses
    ADD CONSTRAINT preliminary_analyses_job_id_key UNIQUE (job_id);


--
-- Name: preliminary_analyses preliminary_analyses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.preliminary_analyses
    ADD CONSTRAINT preliminary_analyses_pkey PRIMARY KEY (id);


--
-- Name: review_resolution_events review_resolution_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.review_resolution_events
    ADD CONSTRAINT review_resolution_events_pkey PRIMARY KEY (event_id);


--
-- Name: review_tasks review_task_unique_job; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.review_tasks
    ADD CONSTRAINT review_task_unique_job UNIQUE (job_id, review_type);


--
-- Name: review_tasks review_tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.review_tasks
    ADD CONSTRAINT review_tasks_pkey PRIMARY KEY (id);


--
-- Name: system_test system_test_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.system_test
    ADD CONSTRAINT system_test_pkey PRIMARY KEY (id);


--
-- Name: review_tasks insurance_review_task_state_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER insurance_review_task_state_trigger BEFORE INSERT ON public.review_tasks FOR EACH ROW EXECUTE FUNCTION public.insurance_review_task_state();


--
-- PostgreSQL database dump complete
--


