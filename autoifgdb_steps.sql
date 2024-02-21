--
-- PostgreSQL database dump
--

-- Dumped from database version 9.6.5
-- Dumped by pg_dump version 9.6.5

-- Started on 2023-12-15 12:52:24

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
-- TOC entry 3636 (class 0 OID 21808)
-- Dependencies: 209
-- Data for Name: steps; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY steps (id, name, command, params, type, prereq_steps, resource, activated, meantime) FROM stdin;
90	Interferogram export to kml	C:\\Program Files\\Exelis\\IDL85\\bin\\bin.x86_64\\idl.exe	{\r\n     "system": "os",\r\n     "dyn_params": "-e sarscape_script_EXPORTING_TO_KML -args  #Path IFG#",\r\n     "parser": "parseIDLscriptout",\r\n     "priority": 1\r\n}	ifg	80	idl	t	00:01:05.796667
105	Automatic GCP computation	C:\\Program Files\\Exelis\\IDL85\\bin\\bin.x86_64\\idl.exe	{\r\n     "system": "os",\r\n     "dyn_params": "-e sarscape_script_automatic_gcp_computation -args #Path Master# #Path IFG# #XML Configuration#",\r\n     "parser": "parseIDLscriptout",\r\n     "priority": 2\r\n}	ifg	100	idl	t	00:01:02.891
55	Delete master slave zip files	del	{\r\n     "system": "os", \r\n     "dyn_params": "#Path Master#\\\\#File Master#.zip #Path Slave#\\\\#File Slave#.zip",\r\n     "priority": 1\r\n}	ifg	50	server	t	00:01:33.04675
120	Displacement and geocoding	C:\\Program Files\\Exelis\\IDL85\\bin\\bin.x86_64\\idl.exe	{\r\n     "system": "os",\r\n     "dyn_params": "-e sarscape_script_displacement_and_geocoding -args #Path Master# #Path IFG#",\r\n     "parser": "parseIDLscriptout",\r\n     "priority": 2\r\n}	ifg	110	idl	t	00:15:41.188
130	Phase unwrapping Export to kml	C:\\Program Files\\Exelis\\IDL85\\bin\\bin.x86_64\\idl.exe	{\r\n     "system": "os",\r\n     "dyn_params": "-e sarscape_script_phase_export_to_kml -args #Path IFG#",\r\n     "parser": "parseIDLscriptout",\r\n     "priority": 2\r\n}	ifg	120	idl	f	00:05:00
91	Delete Ingestion Master	deleteutils	{\r\n     "system": "python", \r\n     "dyn_params": "#Path Master# *_slc walk master",\r\n     "priority":1\r\n}	ifg	80	server	f	00:00:26.532
30	Ingestion master	C:\\Program Files\\Exelis\\IDL85\\bin\\bin.x86_64\\idl.exe	{\r\n     "system": "os",\r\n     "dyn_params": "-e SARscape_script_import_Sentinel_1 -args #Path Master# #Path Orbit Master# #File Orbit Master#",\r\n     "parser": "parseIDLscriptout",\r\n     "priority":1\r\n}	ifg	15,8	idl	f	01:26:51.857
8	Download Orbit file for master 	searchimages.OrbitFileDownloader	{\r\n     "system": "python", \r\n     "dyn_params": "#Path Orbit Master# #File Orbit Master#",\r\n     "priority":1\r\n}	ifg	\N	internet	f	00:01:46.062
92	Delete Ingestion Slave	deleteutils	{\r\n     "system": "python", \r\n     "dyn_params": "#Path Slave# *_slc walk slave",\r\n     "priority":1\r\n}	ifg	80	server	f	00:00:14.187
15	Uncompress master	searchimages.ProductUnzipper	{\r\n     "system": "python", \r\n     "dyn_params": "#MasterId#",\r\n     "priority":1\r\n}	ifg	10	idl	t	00:03:44.051455
41	Ingestion slave no orbit	C:\\Program Files\\Exelis\\IDL85\\bin\\bin.x86_64\\idl.exe	{\r\n     "system": "os",\r\n     "dyn_params": "-e SARscape_script_import_Sentinel_1_noorbit -args #Path Slave#",\r\n     "parser": "parseIDLscriptout",\r\n     "priority":1\r\n}	ifg	25	idl	t	00:16:04.235833
140	Publish Unwrapping	publishing.Publish	{\r\n     "system": "python",\r\n     "dyn_params": "#Event ID# #Path IFG# #publish# unw",\r\n     "priority": 2\r\n}	ifg	120	server	t	00:00:39.094
96	Coherence geocoding	C:\\Program Files\\Exelis\\IDL85\\bin\\bin.x86_64\\idl.exe	{\r\n     "system": "os",\r\n     "dyn_params": "-e sarscape_script_geocoding_rad_cal_cc -args  #Path Master# #Path Slave# #Path IFG# #XML Configuration#",\r\n     "parser": "parseIDLscriptout",\r\n     "priority": 1\r\n}	ifg	70	idl	f	00:04:11.094
97	Delete Ingestion Master	del	{\r\n     "system": "os", \r\n     "dyn_params": "/s /q #Path Master#\\\\*_slc",\r\n     "priority": 1\r\n}	ifg	80	server	f	00:00:13.42175
31	Ingestion master no orbit	C:\\Program Files\\Exelis\\IDL85\\bin\\bin.x86_64\\idl.exe	{\r\n     "system": "os",\r\n     "dyn_params": "-e SARscape_script_import_Sentinel_1_noorbit -args #Path Master#",\r\n     "parser": "parseIDLscriptout",\r\n     "priority":1\r\n}	ifg	15	idl	t	00:14:34.145909
10	Download master	searchimages.ProductDownloader	{\r\n     "system": "python", \r\n     "dyn_params": "#MasterId#",\r\n     "priority":1\r\n}	ifg	20	internet	t	00:01:42.506667
80	Interferogram geocoding	C:\\Program Files\\Exelis\\IDL85\\bin\\bin.x86_64\\idl.exe	{\r\n     "system": "os",\r\n     "dyn_params": "-e sarscape_script_geocoding_rad_cal -args  #Path Master# #Path Slave# #Path IFG# #XML Configuration#",\r\n     "parser": "parseIDLscriptout",\r\n     "priority": 1\r\n}	ifg	70	idl	t	00:05:43.365
18	Download Orbit file for Slave	searchimages.OrbitFileDownloader	{\r\n     "system": "python", \r\n     "dyn_params": "#Path Orbit Slave# #File Orbit Slave#",\r\n     "priority":1\r\n}	ifg	\N	internet	f	00:00:36.313
50	Interferogram creation	C:\\Program Files\\Exelis\\IDL85\\bin\\bin.x86_64\\idl.exe	{\r\n     "system": "os",\r\n     "dyn_params": "-e sarscape_script_interferogram -args  #Path Master# #Path Slave# #Path IFG# #XML Configuration#",\r\n     "parser": "parseIDLscriptout",\r\n     "priority":1\r\n}	ifg	31,35,41	idl	t	02:38:20.213857
110	Interferogram refinement	C:\\Program Files\\Exelis\\IDL85\\bin\\bin.x86_64\\idl.exe	{\r\n     "system": "os",\r\n     "dyn_params": "-e sarscape_script_ifg_refinement -args #Path Master# #Path Slave# #Path IFG# #XML Configuration#",\r\n     "parser": "parseIDLscriptout",\r\n     "priority": 2\r\n}	ifg	105	idl	t	00:01:40.328
93	Delete Intermediate files	del	{\r\n     "system": "os", \r\n     "dyn_params": "#Path IFG#\\\\file_name_be_* #Path IFG#\\\\file_result_az_* #Path IFG#\\\\file_result_rg_* #Path IFG#\\\\file_result_master_* #Path IFG#\\\\file_result_slave_*",\r\n     "priority": 1\r\n}	ifg	80	server	f	00:00:10.281
35	DEM creation	C:\\Program Files\\Exelis\\IDL85\\bin\\bin.x86_64\\idl.exe	{\r\n     "system": "os",\r\n     "dyn_params": "-e SARscape_script_dem_extraction -args #Path Master# #XML Configuration#",\r\n     "parser": "parseIDLscriptout",\r\n     "priority":1\r\n}	ifg	31	idl	t	00:02:16.274364
58	Delete slave uncompressed	rmdir	{\r\n     "system": "os", \r\n     "dyn_params": "/S /Q #Path Slave#\\\\#uncompressed#",\r\n     "priority": 1\r\n}	ifg	50,56	server	t	00:00:53.83225
40	Ingestion slave	C:\\Program Files\\Exelis\\IDL85\\bin\\bin.x86_64\\idl.exe	{\r\n     "system": "os",\r\n     "dyn_params": "-e SARscape_script_import_Sentinel_1 -args #Path Slave# #Path Orbit Slave# #File Orbit Slave#",\r\n     "parser": "parseIDLscriptout",\r\n     "priority":1\r\n}	ifg	25,18	idl	f	00:43:33.734
60	Baseline estimation	C:\\Program Files\\Exelis\\IDL85\\bin\\bin.x86_64\\idl.exe	{\r\n     "system": "os",\r\n     "dyn_params": "-e sarscape_script_baseline_estimation -args  #Path Master# #Path Slave# #Path IFG# #XML Configuration#",\r\n     "parser": "parseIDLscriptout",\r\n     "priority": 1\r\n}	ifg	31,41	idl	t	00:06:08.3115
95	Publish Interferogram	publishing.Publish	{\r\n     "system": "python",\r\n     "dyn_params": "#Event ID# #Path IFG# #publish# ifg",\r\n     "priority": 1\r\n}	ifg	80,90	server	t	00:01:40.255333
20	Download slave	searchimages.ProductDownloader	{\r\n     "system": "python", \r\n     "dyn_params": "#SlaveId#",\r\n     "priority":1\r\n}	ifg	\N	internet	t	00:00:37.321429
57	Delete slave zip	del	{\r\n     "system": "os", \r\n     "dyn_params": "#Path Slave#\\\\#File Slave#.zip",\r\n     "priority": 1\r\n}	ifg	50,56	server	f	00:00:34.218
100	Phase unwrapping	C:\\Program Files\\Exelis\\IDL85\\bin\\bin.x86_64\\idl.exe	{\r\n     "system": "os",\r\n     "dyn_params": "-e sarscape_script_phase_unwrapping -args  #Path IFG#",\r\n     "parser": "parseIDLscriptout",\r\n     "priority": 2\r\n}	ifg	70	idl	t	01:47:22.815
56	Delete master uncompressed	rmdir	{\r\n     "system": "os", \r\n     "dyn_params": "/S /Q #Path Master#\\\\#uncompressed#",\r\n     "priority": 1\r\n}	ifg	50,55	server	t	00:01:09.703
70	Interferogram filtering	C:\\Program Files\\Exelis\\IDL85\\bin\\bin.x86_64\\idl.exe	{\r\n     "system": "os",\r\n     "dyn_params": "-e SARscape_script_adapt_filt_coh_gen -args  #Path Master# #Path Slave# #Path IFG# #XML Configuration#",\r\n     "parser": "parseIDLscriptout",\r\n     "priority": 1\r\n}	ifg	50	idl	t	00:13:19.865667
25	Uncompress slave	searchimages.ProductUnzipper	{\r\n     "system": "python", \r\n     "dyn_params": "#SlaveId#",\r\n     "priority":1\r\n}	ifg	20	idl	t	00:02:12.161333
\.


--
-- TOC entry 3497 (class 2606 OID 21850)
-- Name: steps steps_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY steps
    ADD CONSTRAINT steps_pkey PRIMARY KEY (id);


-- Completed on 2023-12-15 12:52:24

--
-- PostgreSQL database dump complete
--

