
FUNCTION loadini_test
  rootpath='D:\data\geohub\'

  ;pythonconfig = '..\ifgconfig.ini'
  ;OPENR, lun, pythonconfig, /GET_LUN
  ;line=''
  ;WHILE NOT EOF(lun) DO BEGIN
  ;  READF, lun, line
  ;  confvar=strsplit(line,":", /EXTRACT)
  ;  if strmatch(line,"rootpath*") EQ 1 then begin
  ;    rootpath=strtrim(strmid(line,STRPOS(line,":")+1),2)
  ;    break
  ;  endif
  ;ENDWHILE
  ;FREE_LUN, lun
    
  idlinifile = rootpath+'config\autoifg_python_idl.ini'
  OPENR, lun, idlinifile, /GET_LUN
  ;Read one line at a time, saving the result into array
  jsonconfig=''
  line=''
  WHILE NOT EOF(lun) DO BEGIN 
     READF, lun, line 
     jsonconfig=jsonconfig+line
  ENDWHILE
  ; Close the file and free the file unit
  FREE_LUN, lun
  RETURN, jsonconfig
END

FUNCTION loadpaths, pathsini
  ;pathsini = 'C:\GeoHub\config\pathconfig.ini'
  jsonconfig=''
  PRINT, pathsini
  if FILE_TEST(pathsini) then begin
    OPENR, lun, pathsini, /GET_LUN
    ;Read one line at a time, saving the result into array
    jsonconfig=''
    line=''
    WHILE NOT EOF(lun) DO BEGIN
      READF, lun, line
      jsonconfig=jsonconfig+line
    ENDWHILE
    ; Close the file and free the file unit
    FREE_LUN, lun
    FILE_DELETE, pathsini
  endif
  RETURN, jsonconfig
END

pro XMLREAD_test
  jsonini_st=loadini_test()
  params=JSON_PARSE(jsonini_st)
  PRINT, params['pathconfig']
  jsonini_st=loadpaths(params['pathconfig'])
  paths=JSON_PARSE(jsonini_st)
  PRINT, paths
  PRINT, paths[params['pathmaster']]
  PRINT, paths[params['pathslave']]

end
