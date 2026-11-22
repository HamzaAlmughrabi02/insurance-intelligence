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

SET default_tablespace = '';

SET default_table_access_method = heap;

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
    created_at timestamp with time zone DEFAULT now() NOT NULL
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
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


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
-- PostgreSQL database dump complete
--


