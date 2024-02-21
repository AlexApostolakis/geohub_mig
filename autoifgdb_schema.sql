--
-- PostgreSQL database dump
--

-- Dumped from database version 9.6.5
-- Dumped by pg_dump version 9.6.5

-- Started on 2023-12-15 12:46:30

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SET check_function_bodies = false;
SET client_min_messages = warning;
SET row_security = off;

--
-- TOC entry 3713 (class 1262 OID 20305)
-- Name: autoifg_prod; Type: DATABASE; Schema: -; Owner: postgres
--

CREATE DATABASE autoifg_prod WITH TEMPLATE = template0 ENCODING = 'UTF8' LC_COLLATE = 'Greek_Greece.1253' LC_CTYPE = 'Greek_Greece.1253';


ALTER DATABASE autoifg_prod OWNER TO postgres;

\connect autoifg_prod

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SET check_function_bodies = false;
SET client_min_messages = warning;
SET row_security = off;

--
-- TOC entry 1 (class 3079 OID 12387)
-- Name: plpgsql; Type: EXTENSION; Schema: -; Owner: 
--

CREATE EXTENSION IF NOT EXISTS plpgsql WITH SCHEMA pg_catalog;


--
-- TOC entry 3715 (class 0 OID 0)
-- Dependencies: 1
-- Name: EXTENSION plpgsql; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION plpgsql IS 'PL/pgSQL procedural language';


--
-- TOC entry 2 (class 3079 OID 75508)
-- Name: dblink; Type: EXTENSION; Schema: -; Owner: 
--

CREATE EXTENSION IF NOT EXISTS dblink WITH SCHEMA public;


--
-- TOC entry 3716 (class 0 OID 0)
-- Dependencies: 2
-- Name: EXTENSION dblink; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION dblink IS 'connect to other PostgreSQL databases from within a database';


--
-- TOC entry 3 (class 3079 OID 20306)
-- Name: postgis; Type: EXTENSION; Schema: -; Owner: 
--

CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA public;


--
-- TOC entry 3717 (class 0 OID 0)
-- Dependencies: 3
-- Name: EXTENSION postgis; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION postgis IS 'PostGIS geometry, geography, and raster spatial types and functions';


SET search_path = public, pg_catalog;

--
-- TOC entry 202 (class 1259 OID 21779)
-- Name: output_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE output_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE output_id_seq OWNER TO postgres;

--
-- TOC entry 203 (class 1259 OID 21781)
-- Name: product_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE product_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE product_id_seq OWNER TO postgres;

SET default_tablespace = '';

SET default_with_oids = false;

--
-- TOC entry 204 (class 1259 OID 21783)
-- Name: satellite_input; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE satellite_input (
    id integer DEFAULT nextval('product_id_seq'::regclass) NOT NULL,
    product_id character varying(80),
    sensing_start timestamp without time zone,
    sensing_stop timestamp without time zone,
    direction character varying(30),
    orbit character varying(30),
    footprint text,
    footprint_id integer,
    orbit_file text,
    status character varying(20),
    name character varying(120),
    params text
);


ALTER TABLE satellite_input OWNER TO postgres;

--
-- TOC entry 205 (class 1259 OID 21790)
-- Name: seisme_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE seisme_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE seisme_id_seq OWNER TO postgres;

--
-- TOC entry 206 (class 1259 OID 21792)
-- Name: service_output; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE service_output (
    service_id integer,
    inputs text,
    id integer DEFAULT nextval('output_id_seq'::regclass) NOT NULL,
    output_status character varying(20),
    type character varying(20),
    priority integer,
    params text
);


ALTER TABLE service_output OWNER TO postgres;

--
-- TOC entry 207 (class 1259 OID 21799)
-- Name: service_request; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE service_request (
    id integer DEFAULT nextval('seisme_id_seq'::regclass) NOT NULL,
    name character varying(200),
    date timestamp without time zone,
    magnitude real,
    epicenter character varying(100),
    epicenter_depth real,
    status character varying(20),
    request_date timestamp without time zone,
    search_poly geometry(Polygon,4326),
    priority integer,
    request_params text,
    last_check timestamp without time zone
);


ALTER TABLE service_request OWNER TO postgres;

--
-- TOC entry 210 (class 1259 OID 21814)
-- Name: steps_execution; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE steps_execution (
    output_id integer NOT NULL,
    step_id integer NOT NULL,
    start_time timestamp without time zone,
    end_time timestamp without time zone,
    status character varying(20),
    estimate_end timestamp without time zone,
    dyn_params text,
    progress text,
    enabled boolean
);


ALTER TABLE steps_execution OWNER TO postgres;

--
-- TOC entry 213 (class 1259 OID 35008)
-- Name: view_service_output; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW view_service_output AS
 SELECT so.service_id,
    so.id AS output_id,
    sr.name AS event_location,
    sr.date AS event_date,
    s1.orbit,
    s1.direction,
        CASE
            WHEN (s1.sensing_start > COALESCE(s2.sensing_start, s1.sensing_start)) THEN 'pre-seismic'::text
            ELSE 'co-seismic'::text
        END AS outtype,
    s1.sensing_start AS master_sensing,
    s2.sensing_start AS slave_sensing,
    so.priority,
    so.output_status,
    fl.first_step,
    se1.start_time AS out_start,
    fl.last_step,
    se2.end_time AS out_end,
    se2.estimate_end AS out_est_end
   FROM ((((((service_output so
     JOIN service_request sr ON ((sr.id = so.service_id)))
     JOIN ( SELECT sef.first_step,
            sel.last_step,
            so_1.id AS oid
           FROM ((service_output so_1
             LEFT JOIN ( SELECT min(steps_execution.step_id) AS first_step,
                    steps_execution.output_id AS of_id
                   FROM steps_execution
                  WHERE (steps_execution.start_time IS NOT NULL)
                  GROUP BY steps_execution.output_id) sef ON ((so_1.id = sef.of_id)))
             JOIN ( SELECT max(steps_execution.step_id) AS last_step,
                    steps_execution.output_id AS ol_id
                   FROM steps_execution
                  GROUP BY steps_execution.output_id) sel ON ((so_1.id = sel.ol_id)))) fl ON ((so.id = fl.oid)))
     LEFT JOIN steps_execution se1 ON (((so.id = se1.output_id) AND (fl.first_step = se1.step_id))))
     JOIN steps_execution se2 ON (((so.id = se2.output_id) AND (fl.last_step = se2.step_id))))
     JOIN satellite_input s1 ON (((s1.product_id)::text = (regexp_split_to_array(so.inputs, ','::text))[1])))
     LEFT JOIN satellite_input s2 ON (((s2.product_id)::text = (regexp_split_to_array(so.inputs, ','::text))[2])));


ALTER TABLE view_service_output OWNER TO postgres;

--
-- TOC entry 218 (class 1259 OID 59074)
-- Name: failed_outputs; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW failed_outputs AS
 SELECT sa.service_id,
    sa.output_id,
    sa.event_location,
    sa.event_date,
    sa.orbit,
    sa.direction,
    sa.outtype,
    sa.master_sensing,
    sa.slave_sensing,
    sa.priority,
    sa.output_status,
    sa.first_step,
    sa.out_start,
    sa.last_step
   FROM ( SELECT vo.service_id,
            vo.output_id,
            vo.event_location,
            vo.event_date,
            vo.orbit,
            vo.direction,
            vo.outtype,
            vo.master_sensing,
            vo.slave_sensing,
            vo.priority,
            vo.output_status,
            vo.first_step,
            vo.out_start,
            vo.last_step
           FROM view_service_output vo
          WHERE (EXISTS ( SELECT se.step_id
                   FROM steps_execution se
                  WHERE ((se.output_id = vo.output_id) AND ((se.status)::text = 'cancelled'::text))))
        UNION
         SELECT vo.service_id,
            vo.output_id,
            vo.event_location,
            vo.event_date,
            vo.orbit,
            vo.direction,
            vo.outtype,
            vo.master_sensing,
            vo.slave_sensing,
            vo.priority,
            vo.output_status,
            vo.first_step,
            vo.out_start,
            vo.last_step
           FROM view_service_output vo
          WHERE (((vo.output_status)::text <> 'processing'::text) AND (vo.out_end IS NULL))) sa
  ORDER BY sa.event_date DESC;


ALTER TABLE failed_outputs OWNER TO postgres;

--
-- TOC entry 209 (class 1259 OID 21808)
-- Name: steps; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE steps (
    id integer NOT NULL,
    name character varying(100),
    command character varying(150),
    params text,
    type character varying(20),
    prereq_steps character varying(30),
    resource character varying(20),
    activated boolean,
    meantime interval
);


ALTER TABLE steps OWNER TO postgres;

--
-- TOC entry 220 (class 1259 OID 59101)
-- Name: steps_exec; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW steps_exec AS
 SELECT o.service_id AS event_id,
    sr.name AS event,
    se.output_id,
    (to_timestamp("substring"((i1.name)::text, 18, 15), 'YYYYMMDD HH24MISS'::text))::timestamp without time zone AS "Master sensing",
    (to_timestamp("substring"((i2.name)::text, 18, 15), 'YYYYMMDD HH24MISS'::text))::timestamp without time zone AS "Slave sensing",
    i1.orbit,
    i1.direction,
    se.step_id,
    s.name,
    se.start_time,
    se.end_time,
    (se.end_time - se.start_time) AS duration,
    se.status,
    se.estimate_end,
    se.progress,
    se.enabled,
    o.priority
   FROM (((((steps_execution se
     LEFT JOIN steps s ON ((se.step_id = s.id)))
     JOIN ( SELECT service_output.id,
            service_output.service_id,
            service_output.priority,
            regexp_split_to_array(service_output.inputs, ','::text) AS inp
           FROM service_output) o ON ((o.id = se.output_id)))
     JOIN satellite_input i1 ON (((i1.product_id)::text = o.inp[1])))
     LEFT JOIN satellite_input i2 ON (((i2.product_id)::text = o.inp[2])))
     JOIN service_request sr ON ((sr.id = o.service_id)))
  ORDER BY se.output_id, se.step_id;


ALTER TABLE steps_exec OWNER TO postgres;

--
-- TOC entry 222 (class 1259 OID 59129)
-- Name: failed_outputs_steps; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW failed_outputs_steps AS
 SELECT steps_exec.event_id,
    steps_exec.event,
    steps_exec.output_id,
    steps_exec."Master sensing",
    steps_exec."Slave sensing",
    steps_exec.orbit,
    steps_exec.direction,
    steps_exec.step_id,
    steps_exec.name,
    steps_exec.start_time,
    steps_exec.end_time,
    steps_exec.duration,
    steps_exec.status,
    steps_exec.estimate_end,
    steps_exec.progress,
    steps_exec.enabled,
    steps_exec.priority
   FROM steps_exec
  WHERE (steps_exec.output_id IN ( SELECT failed_outputs.output_id
           FROM failed_outputs))
  ORDER BY steps_exec.output_id DESC, steps_exec.step_id;


ALTER TABLE failed_outputs_steps OWNER TO postgres;

--
-- TOC entry 219 (class 1259 OID 59086)
-- Name: finished_ok_outputs; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW finished_ok_outputs AS
 SELECT view_service_output.service_id,
    view_service_output.output_id,
    view_service_output.event_location,
    view_service_output.event_date,
    view_service_output.orbit,
    view_service_output.direction,
    view_service_output.outtype,
    view_service_output.master_sensing,
    view_service_output.slave_sensing,
    view_service_output.priority,
    view_service_output.output_status,
    view_service_output.first_step,
    view_service_output.out_start,
    view_service_output.last_step,
    view_service_output.out_end
   FROM view_service_output
  WHERE ((view_service_output.out_est_end IS NULL) AND (view_service_output.out_end IS NOT NULL))
  ORDER BY view_service_output.event_date DESC, view_service_output.out_end DESC;


ALTER TABLE finished_ok_outputs OWNER TO postgres;

--
-- TOC entry 214 (class 1259 OID 41215)
-- Name: view_service_requests; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW view_service_requests AS
 SELECT service_request.id,
    service_request.name,
    service_request.date,
    service_request.magnitude,
    service_request.epicenter,
    service_request.epicenter_depth,
    service_request.status,
    service_request.request_date,
    service_request.search_poly,
    service_request.priority,
    service_request.request_params,
    service_request.last_check,
    st_astext(service_request.search_poly) AS st_astext
   FROM service_request;


ALTER TABLE view_service_requests OWNER TO postgres;

--
-- TOC entry 217 (class 1259 OID 59070)
-- Name: processed_events; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW processed_events AS
 SELECT view_service_requests.id,
    view_service_requests.name,
    view_service_requests.date,
    view_service_requests.magnitude,
    view_service_requests.epicenter,
    view_service_requests.epicenter_depth,
    view_service_requests.status,
    view_service_requests.request_date,
    view_service_requests.last_check
   FROM view_service_requests
  WHERE ((view_service_requests.status)::text ~~ 'read%'::text)
  ORDER BY view_service_requests.date DESC;


ALTER TABLE processed_events OWNER TO postgres;

--
-- TOC entry 216 (class 1259 OID 59066)
-- Name: processing_events; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW processing_events AS
 SELECT view_service_requests.id,
    view_service_requests.name,
    view_service_requests.date,
    view_service_requests.magnitude,
    view_service_requests.epicenter,
    view_service_requests.epicenter_depth,
    view_service_requests.status,
    view_service_requests.request_date,
    view_service_requests.last_check
   FROM view_service_requests
  WHERE ((view_service_requests.status)::text ~~ 'proc%'::text)
  ORDER BY view_service_requests.date;


ALTER TABLE processing_events OWNER TO postgres;

--
-- TOC entry 225 (class 1259 OID 62009)
-- Name: processing_events_outputs; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW processing_events_outputs AS
 SELECT view_service_output.service_id,
    view_service_output.output_id,
    view_service_output.event_location,
    view_service_output.event_date,
    view_service_output.orbit,
    view_service_output.direction,
    view_service_output.outtype,
    view_service_output.master_sensing,
    view_service_output.slave_sensing,
    view_service_output.priority,
    view_service_output.output_status,
    view_service_output.first_step,
    view_service_output.out_start,
    view_service_output.last_step,
    view_service_output.out_end,
    view_service_output.out_est_end
   FROM view_service_output
  WHERE (view_service_output.service_id IN ( SELECT processing_events.id
           FROM processing_events))
  ORDER BY view_service_output.event_date, view_service_output.priority;


ALTER TABLE processing_events_outputs OWNER TO postgres;

--
-- TOC entry 221 (class 1259 OID 59109)
-- Name: processing_events_steps; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW processing_events_steps AS
 SELECT steps_exec.event_id,
    steps_exec.event,
    steps_exec.output_id,
    steps_exec."Master sensing",
    steps_exec."Slave sensing",
    steps_exec.orbit,
    steps_exec.direction,
    steps_exec.step_id,
    steps_exec.name,
    steps_exec.start_time,
    steps_exec.end_time,
    steps_exec.duration,
    steps_exec.status,
    steps_exec.estimate_end,
    steps_exec.progress,
    steps_exec.enabled,
    steps_exec.priority
   FROM steps_exec
  WHERE (steps_exec.event_id IN ( SELECT processing_events.id
           FROM processing_events))
  ORDER BY steps_exec.event_id, (steps_exec.priority * steps_exec.output_id), steps_exec.step_id;


ALTER TABLE processing_events_steps OWNER TO postgres;

--
-- TOC entry 223 (class 1259 OID 59180)
-- Name: processing_steps; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW processing_steps AS
 SELECT steps_exec.event_id,
    steps_exec.event,
    steps_exec.output_id,
    steps_exec."Master sensing",
    steps_exec."Slave sensing",
    steps_exec.orbit,
    steps_exec.direction,
    steps_exec.step_id,
    steps_exec.name,
    steps_exec.start_time,
    steps_exec.estimate_end,
    steps_exec.progress,
    steps_exec.priority
   FROM steps_exec
  WHERE ((steps_exec.status)::text = 'processing'::text);


ALTER TABLE processing_steps OWNER TO postgres;

--
-- TOC entry 229 (class 1259 OID 113548)
-- Name: serveralive; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE serveralive (
    lastupdate timestamp without time zone,
    lastcheck timestamp without time zone
);


ALTER TABLE serveralive OWNER TO postgres;

--
-- TOC entry 230 (class 1259 OID 121299)
-- Name: so_view_epidist; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW so_view_epidist AS
 SELECT so.service_id,
    so.id AS output_id,
    sr.name AS event_location,
    sr.date AS event_date,
    s1.orbit,
    s1.direction,
        CASE
            WHEN (s1.sensing_start > COALESCE(s2.sensing_start, s1.sensing_start)) THEN 'pre-seismic'::text
            ELSE 'co-seismic'::text
        END AS outtype,
    s1.sensing_start AS master_sensing,
    s2.sensing_start AS slave_sensing,
    so.priority,
    ((so.params)::json ->> 'epicenter distance'::text) AS epidist,
    so.output_status,
    fl.first_step,
    se1.start_time AS out_start,
    fl.last_step,
    se2.end_time AS out_end,
    se2.estimate_end AS out_est_end
   FROM ((((((service_output so
     JOIN service_request sr ON ((sr.id = so.service_id)))
     JOIN ( SELECT sef.first_step,
            sel.last_step,
            so_1.id AS oid
           FROM ((service_output so_1
             LEFT JOIN ( SELECT min(steps_execution.step_id) AS first_step,
                    steps_execution.output_id AS of_id
                   FROM steps_execution
                  WHERE (steps_execution.start_time IS NOT NULL)
                  GROUP BY steps_execution.output_id) sef ON ((so_1.id = sef.of_id)))
             JOIN ( SELECT max(steps_execution.step_id) AS last_step,
                    steps_execution.output_id AS ol_id
                   FROM steps_execution
                  GROUP BY steps_execution.output_id) sel ON ((so_1.id = sel.ol_id)))) fl ON ((so.id = fl.oid)))
     LEFT JOIN steps_execution se1 ON (((so.id = se1.output_id) AND (fl.first_step = se1.step_id))))
     JOIN steps_execution se2 ON (((so.id = se2.output_id) AND (fl.last_step = se2.step_id))))
     JOIN satellite_input s1 ON (((s1.product_id)::text = (regexp_split_to_array(so.inputs, ','::text))[1])))
     LEFT JOIN satellite_input s2 ON (((s2.product_id)::text = (regexp_split_to_array(so.inputs, ','::text))[2])));


ALTER TABLE so_view_epidist OWNER TO postgres;

--
-- TOC entry 208 (class 1259 OID 21806)
-- Name: step_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE step_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE step_id_seq OWNER TO postgres;

--
-- TOC entry 211 (class 1259 OID 21825)
-- Name: steps_log; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE steps_log (
    output_id integer NOT NULL,
    step_id integer NOT NULL,
    logtime timestamp without time zone NOT NULL,
    message text,
    status character varying(20)
);


ALTER TABLE steps_log OWNER TO postgres;

--
-- TOC entry 226 (class 1259 OID 70441)
-- Name: steps_log_archive_2018; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE steps_log_archive_2018 (
    output_id integer,
    step_id integer,
    logtime timestamp without time zone,
    message text,
    status character varying(20)
);


ALTER TABLE steps_log_archive_2018 OWNER TO postgres;

--
-- TOC entry 231 (class 1259 OID 147642)
-- Name: steps_log_archive_2019; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE steps_log_archive_2019 (
    output_id integer,
    step_id integer,
    logtime timestamp without time zone,
    message text,
    status character varying(20)
);


ALTER TABLE steps_log_archive_2019 OWNER TO postgres;

--
-- TOC entry 232 (class 1259 OID 196371)
-- Name: steps_log_archive_2020; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE steps_log_archive_2020 (
    output_id integer,
    step_id integer,
    logtime timestamp without time zone,
    message text,
    status character varying(20)
);


ALTER TABLE steps_log_archive_2020 OWNER TO postgres;

--
-- TOC entry 233 (class 1259 OID 196379)
-- Name: steps_log_archive_2021; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE steps_log_archive_2021 (
    output_id integer,
    step_id integer,
    logtime timestamp without time zone,
    message text,
    status character varying(20)
);


ALTER TABLE steps_log_archive_2021 OWNER TO postgres;

--
-- TOC entry 228 (class 1259 OID 75560)
-- Name: steps_prod_back; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE steps_prod_back (
    id integer,
    name character varying(100),
    command character varying(150),
    params text,
    type character varying(20),
    prereq_steps character varying(30),
    resource character varying(20),
    activated boolean,
    meantime interval
);


ALTER TABLE steps_prod_back OWNER TO postgres;

--
-- TOC entry 215 (class 1259 OID 59039)
-- Name: upcoming_outputs; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW upcoming_outputs AS
 SELECT view_service_output.service_id,
    view_service_output.output_id,
    view_service_output.event_location,
    view_service_output.event_date,
    view_service_output.orbit,
    view_service_output.direction,
    view_service_output.outtype,
    view_service_output.master_sensing,
    view_service_output.slave_sensing,
    view_service_output.priority,
    view_service_output.output_status,
    view_service_output.first_step,
    view_service_output.out_start,
    view_service_output.last_step,
    view_service_output.out_est_end
   FROM view_service_output
  WHERE ((view_service_output.out_est_end IS NOT NULL) AND ((view_service_output.output_status)::text ~~ 'proc%'::text))
  ORDER BY view_service_output.out_est_end;


ALTER TABLE upcoming_outputs OWNER TO postgres;

--
-- TOC entry 224 (class 1259 OID 59184)
-- Name: upcoming_outputs_steps; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW upcoming_outputs_steps AS
 SELECT steps_exec.event_id,
    steps_exec.event,
    steps_exec.output_id,
    steps_exec."Master sensing",
    steps_exec."Slave sensing",
    steps_exec.orbit,
    steps_exec.direction,
    steps_exec.step_id,
    steps_exec.name,
    steps_exec.start_time,
    steps_exec.end_time,
    steps_exec.duration,
    steps_exec.status,
    steps_exec.estimate_end,
    steps_exec.progress,
    steps_exec.enabled,
    steps_exec.priority
   FROM steps_exec
  WHERE (steps_exec.output_id IN ( SELECT upcoming_outputs.output_id
           FROM upcoming_outputs))
  ORDER BY steps_exec.event_id, steps_exec.priority, steps_exec.step_id;


ALTER TABLE upcoming_outputs_steps OWNER TO postgres;

--
-- TOC entry 212 (class 1259 OID 21831)
-- Name: users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE users (
    name character varying(40),
    email character varying(40) NOT NULL,
    notifications text,
    registered boolean
);


ALTER TABLE users OWNER TO postgres;

--
-- TOC entry 3554 (class 2606 OID 21838)
-- Name: satellite_input satellite_input_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY satellite_input
    ADD CONSTRAINT satellite_input_pkey PRIMARY KEY (id);


--
-- TOC entry 3556 (class 2606 OID 21840)
-- Name: satellite_input satellite_input_product_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY satellite_input
    ADD CONSTRAINT satellite_input_product_id_key UNIQUE (product_id);


--
-- TOC entry 3558 (class 2606 OID 21842)
-- Name: service_output service_output_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY service_output
    ADD CONSTRAINT service_output_pkey PRIMARY KEY (id);


--
-- TOC entry 3560 (class 2606 OID 21844)
-- Name: service_request service_request_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY service_request
    ADD CONSTRAINT service_request_pkey PRIMARY KEY (id);


--
-- TOC entry 3566 (class 2606 OID 21846)
-- Name: steps_execution steps_execution_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY steps_execution
    ADD CONSTRAINT steps_execution_pkey PRIMARY KEY (output_id, step_id);


--
-- TOC entry 3568 (class 2606 OID 21848)
-- Name: steps_log steps_log_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY steps_log
    ADD CONSTRAINT steps_log_pkey PRIMARY KEY (logtime);


--
-- TOC entry 3564 (class 2606 OID 21850)
-- Name: steps steps_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY steps
    ADD CONSTRAINT steps_pkey PRIMARY KEY (id);


--
-- TOC entry 3562 (class 2606 OID 35005)
-- Name: service_request unique_event; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY service_request
    ADD CONSTRAINT unique_event UNIQUE (name, date);


--
-- TOC entry 3570 (class 2606 OID 21854)
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY users
    ADD CONSTRAINT users_pkey PRIMARY KEY (email);


-- Completed on 2023-12-15 12:46:32

--
-- PostgreSQL database dump complete
--

