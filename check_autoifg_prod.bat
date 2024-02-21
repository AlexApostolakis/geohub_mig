@echo off
set GEOHUBROOT=D:\data\geohub\
set GEOHUBARCHROOT=Y:\geohub_prod_backup\
set GEOHUBDB=autoifg_prod
set PUBLISHROOT=Y:\geohub_publish\events\
C:\Python27\ArcGIS10.3\python.exe C:\Users\arcgisadmin\eclipse_projects\autoifg_prod\manage_srv.py check
pause
