@ECHO OFF
rem set GEOHUBDEBUG=True
set GEOHUBROOT=D:\data\geohub\
set GEOHUBARCHROOT=Y:\geohub_prod_backup\
set GEOHUBDB=autoifg_prod
set PUBLISHROOT=Y:\geohub_publish\events\
IF EXIST "%GEOHUBROOT%logs/server_running.nfo" (
	ECHO Server is already running or stopped ubnormally
) ELSE (
	ECHO Starting Server...
	start /b C:\Python27\ArcGIS10.3\pythonw.exe C:\Users\arcgisadmin\eclipse_projects\autoifg_prod\autoifgsrv.py
	C:\Python27\ArcGIS10.3\python.exe C:\Users\arcgisadmin\eclipse_projects\autoifg_prod\manage_srv.py check
)
pause
