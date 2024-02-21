--
-- PostgreSQL database dump
--

-- Dumped from database version 9.6.5
-- Dumped by pg_dump version 9.6.5

-- Started on 2018-10-11 19:26:16

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SET check_function_bodies = false;
SET client_min_messages = warning;
SET row_security = off;

SET search_path = public, pg_catalog;

SET default_tablespace = '';

SET default_with_oids = false;

--
-- TOC entry 208 (class 1259 OID 19444)
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
-- TOC entry 3523 (class 0 OID 19444)
-- Dependencies: 208
-- Data for Name: steps; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY steps (id, name, command, params, type, prereq_steps, resource, activated, meantime) FROM stdin;
8	Download Orbit file for master 	searchimages.OrbitFileDownloader	{\r\n     "system": "python", \r\n     "dyn_params": "#Path Orbit Master# #File Orbit Master#"\r\n}	ifg	\N	internet	f	00:00:17.367
16	Delete master zip	del	{\r\n     "system": "os", \r\n     "dyn_params": "#Path Master#\\\\#File Master#.zip"\r\n}	ifg	15	server	f	00:00:27.268
18	Download Orbit file for Slave	searchimages.OrbitFileDownloader	{\r\n     "system": "python", \r\n     "dyn_params": "#Path Orbit Slave# #File Orbit Slave#"\r\n}	ifg	\N	internet	f	00:00:05.45
20	Download slave	searchimages.ProductDownloader	{\r\n     "system": "python", \r\n     "dyn_params": "#SlaveId#"\r\n}	ifg	\N	internet	f	00:01:58.985
25	Uncompress slave	searchimages.ProductUnzipper	{\r\n     "system": "python", \r\n     "dyn_params": "#SlaveId#"\r\n}	ifg	20	server	f	00:08:12.703
105	Automatic GCP computation	C:\\Program Files\\Exelis\\IDL85\\bin\\bin.x86_64\\idl.exe	{\r\n     "system": "os",\r\n     "dyn_params": "-e sarscape_script_automatic_gcp_computation -args #Path Master# #Path IFG# #XML Configuration#",\r\n     "parser": "parseIDLscriptout"\r\n}	ifg	100	server	f	00:01:16.144
110	Interferogram refinement	C:\\Program Files\\Exelis\\IDL85\\bin\\bin.x86_64\\idl.exe	{\r\n     "system": "os",\r\n     "dyn_params": "-e sarscape_script_ifg_refinement -args #Path Master# #Path Slave# #Path IFG# #XML Configuration#",\r\n     "parser": "parseIDLscriptout"\r\n}	ifg	105	server	f	00:02:43.284667
31	Delete master uncompressed	rmdir	{\r\n     "system": "os", \r\n     "dyn_params": "/S /Q #Path Master#\\\\#uncompressed#"\r\n}	ifg	30	server	f	00:00:12.594
130	Phase unwrapping Export to kml	C:\\Program Files\\Exelis\\IDL85\\bin\\bin.x86_64\\idl.exe	{\r\n     "system": "os",\r\n     "dyn_params": "-e sarscape_script_phase_export_to_kml -args #Path IFG#",\r\n     "parser": "parseIDLscriptout"\r\n}	ifg	120	server	f	00:05:00
95	Publish	publishing.Publish	{\r\n     "system": "python",\r\n     "dyn_params": "#Path IFG# #publish#"\r\n}	ifg	\N	server	t	00:00:18.375
10	Download master	searchimages.ProductDownloader	{\r\n     "system": "python", \r\n     "dyn_params": "#MasterId#"\r\n}	ifg	\N	internet	f	00:17:31.234
26	Delete slave zip	del	{\r\n     "system": "os", \r\n     "dyn_params": "#Path Slave#\\\\#File Slave#.zip"\r\n}	ifg	25	server	f	00:00:11.268
50	Interferogram creation	C:\\Program Files\\Exelis\\IDL85\\bin\\bin.x86_64\\idl.exe	{\r\n     "system": "os",\r\n     "dyn_params": "-e sarscape_script_interferogram -args  #Path Master# #Path Slave# #Path IFG# #XML Configuration#",\r\n     "parser": "parseIDLscriptout"\r\n}	ifg	35,40	server	f	03:03:02.324556
60	Baseline estimation	C:\\Program Files\\Exelis\\IDL85\\bin\\bin.x86_64\\idl.exe	{\r\n     "system": "os",\r\n     "dyn_params": "-e sarscape_script_baseline_estimation -args  #Path Master# #Path Slave# #Path IFG# #XML Configuration#",\r\n     "parser": "parseIDLscriptout"\r\n}	ifg	30,40	server	f	00:05:49.107889
41	Delete slave uncompressed	rmdir	{\r\n     "system": "os", \r\n     "dyn_params": "/S /Q #Path Slave#\\\\#uncompressed#"\r\n}	ifg	40	server	f	00:00:13.0785
1	test process	ping.exe	{\r\n     "system": "os",\r\n     "dyn_params": "127.0.0.1 -n 15 -l #OutputId#",\r\n     "parser": "parsping"\r\n}	ifg	\N	server	f	00:05:00
6	test_idl 2	C:\\Program Files\\Exelis\\IDL85\\bin\\bin.x86_64\\idl.exe	{\r\n     "system": "os",\r\n     "dyn_params": "-e testcliargss2 -args #Path Master# #Path Slave# #Path IFG# #XML Configuration#",\r\n     "parser": "parseIDLscriptout"\r\n}	ifg	\N	server	f	00:05:00
35	DEM creation	C:\\Program Files\\Exelis\\IDL85\\bin\\bin.x86_64\\idl.exe	{\r\n     "system": "os",\r\n     "dyn_params": "-e SARscape_script_dem_extraction -args #Path Master#",\r\n     "parser": "parseIDLscriptout"\r\n}	ifg	30	server	f	00:08:22.844
40	Ingestion slave	C:\\Program Files\\Exelis\\IDL85\\bin\\bin.x86_64\\idl.exe	{\r\n     "system": "os",\r\n     "dyn_params": "-e SARscape_script_import_Sentinel_1 -args #Path Slave# #Path Orbit Slave# #File Orbit Slave#",\r\n     "parser": "parseIDLscriptout"\r\n}	ifg	25,18	server	f	00:55:07.484
70	Interferogram filtering	C:\\Program Files\\Exelis\\IDL85\\bin\\bin.x86_64\\idl.exe	{\r\n     "system": "os",\r\n     "dyn_params": "-e SARscape_script_adapt_filt_coh_gen -args  #Path Master# #Path Slave# #Path IFG# #XML Configuration#",\r\n     "parser": "parseIDLscriptout"\r\n}	ifg	50	server	f	00:20:49.039889
5	test_idl	C:\\Program Files\\Exelis\\IDL85\\bin\\bin.x86_64\\idl.exe	{\r\n     "system": "os",\r\n     "dyn_params": "-e testcliargs -args #Path Master# #Path Slave# #Path IFG# #XML Configuration#",\r\n     "parser": "parseIDLscriptout"\r\n}\r\n	ifg	\N	server	f	00:01:29.73
15	Uncompress master	searchimages.ProductUnzipper	{\r\n     "system": "python", \r\n     "dyn_params": "#MasterId#"\r\n}	ifg	10	server	f	00:01:59.219
30	Ingestion master	C:\\Program Files\\Exelis\\IDL85\\bin\\bin.x86_64\\idl.exe	{\r\n     "system": "os",\r\n     "dyn_params": "-e SARscape_script_import_Sentinel_1 -args #Path Master# #Path Orbit Master# #File Orbit Master#",\r\n     "parser": "parseIDLscriptout"\r\n}	ifg	15,8	server	f	00:54:19.172
80	Interferogram geocoding	C:\\Program Files\\Exelis\\IDL85\\bin\\bin.x86_64\\idl.exe	{\r\n     "system": "os",\r\n     "dyn_params": "-e sarscape_script_geocoding_rad_cal -args  #Path Master# #Path Slave# #Path IFG# #XML Configuration#",\r\n     "parser": "parseIDLscriptout"\r\n}	ifg	70	server	f	00:11:29.371444
90	Interferogram export to kml	C:\\Program Files\\Exelis\\IDL85\\bin\\bin.x86_64\\idl.exe	{\r\n     "system": "os",\r\n     "dyn_params": "-e sarscape_script_EXPORTING_TO_KML -args  #Path IFG#",\r\n     "parser": "parseIDLscriptout"\r\n}	ifg	80	server	f	00:01:08.107667
120	Displacement and geocoding	C:\\Program Files\\Exelis\\IDL85\\bin\\bin.x86_64\\idl.exe	{\r\n     "system": "os",\r\n     "dyn_params": "-e sarscape_script_displacement_and_geocoding -args #Path Master# #Path IFG#",\r\n     "parser": "parseIDLscriptout"\r\n}	ifg	110	server	f	00:18:20.131125
100	Phase unwrapping	C:\\Program Files\\Exelis\\IDL85\\bin\\bin.x86_64\\idl.exe	{\r\n     "system": "os",\r\n     "dyn_params": "-e sarscape_script_phase_unwrapping -args  #Path IFG#",\r\n     "parser": "parseIDLscriptout"\r\n}	ifg	70	server	f	00:27:46.481
\.


--
-- TOC entry 3395 (class 2606 OID 19473)
-- Name: steps steps_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY steps
    ADD CONSTRAINT steps_pkey PRIMARY KEY (id);


-- Completed on 2018-10-11 19:26:18

--
-- PostgreSQL database dump complete
--

