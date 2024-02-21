pro  SARscape_script_import_Sentinel_1_slave

  compile_opt idl2

  infoRoutine = ROUTINE_INFO('SARscape_script_import_Sentinel_1_slave', /SOURCE)

  CATCH, error
  if error ne 0 then begin
    PRINT, !error_state.msg
    return
  endif

  RESTORE, 'loadini.sav'
  jsonini_st=loadini()
  params=JSON_PARSE(jsonini_st)
  jsonini_st=loadpaths(params['pathconfig'])
  paths=JSON_PARSE(jsonini_st)

  inImages=paths[params['pathslave']]
  manifest=inImages+PATH_SEP()+params['uncompressed_dir']+PATH_SEP()+'manifest.safe'
  inOrbits = paths[params['pathorbitslave']] + PATH_SEP()+ paths[params['fileorbitslave']]

  
  ; 1) SARscape batch initialization and temporary directory setting
  if (strpos(!prompt,'ENVI') eq -1 ) then begin
    aTmp=inImages+PATH_SEP()+params['ingestion_work_dir']
    FILE_MKDIR,aTmp
    SARscape_Batch_Init,Temp_Directory=aTmp
  endif

  outName=inImages+PATH_SEP()+params['import_dir']+PATH_SEP()
  
  ;*************************************************************************************
  ;*   BATCH STEP 2 IMPORT DATA                                                        *
  ;*************************************************************************************


  ; 3) Create the IMPORTSENTINEL1FORMAT object
  OB = obj_new('SARscapeBatch',Module='IMPORTSENTINEL1FORMAT')
  IF (~OBJ_VALID(OB)) THEN BEGIN
    if (aEnviRun eq 0) then  SARscape_ErrorMsg, 'The object is not valid then the user must manage the error'
    if (aEnviRun eq 0) and (aMake_BatchfileOnly eq 0) then SARscape_Batch_Exit
    return

  ENDIF


  ; 4) Fill the Parameters
  OB->Setparam,'input_file_list', manifest
  OB->Setparam,'input_orbit_file_list', inOrbits
  OB->Setparam,'output_file_list', outName
  OB->Setparam,'rename_the_file_using_parameters_flag', 'OK'

  ; 5) Verify the parameters
  ok = OB->VerifyParams(Silent=0)


  IF ~ok THEN BEGIN

    SARscape_ErrorMsg,' Module can not be executed; Some parameters need to be filled '

    return
  ENDIF

  ; 6) execute the process
  if (strpos(!prompt,'ENVI') gt -1 ) then begin
    OK = OB->ExecuteProgress(show_end_dialog='NotOK')
  endif else begin
    OK = OB->Execute();
  endelse

  IF OK THEN BEGIN
    Print,' ************* '
    print,'STEP SUCCESS......  IMPORT SENTINEL-1 DATA'
    Print,' ************* '
  ENDIF else begin
    SARscape_ErrorMsg,'STEP FAILED ......  IMPORT SENTINEL-1 DATA'
    return
  ENDELSE
  
  
end



