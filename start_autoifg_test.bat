@ECHO OFF
set GEOHUBROOT=Z:\data\alexis\GeoHub_test_run\
set GEOHUBARCHROOT=Z:\data\alexis\GeoHub_test_archive\
set GEOHUBDB=autoifg
IF EXIST "%GEOHUBROOT%logs/server_running.nfo" (
	ECHO Server is already running or stopped ubnormally
) ELSE (
	ECHO Starting Server...
	start /b C:\Python27\ArcGIS10.3\pythonw.exe C:\Users\arcgisadmin\eclipse_projects\autoifg\autoifgsrv.py
	C:\Python27\ArcGIS10.3\python.exe C:\Users\arcgisadmin\eclipse_projects\autoifg\manage_srv.py check
)
pause
