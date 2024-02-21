pro  sarscape_script_displacement_and_geocoding

  compile_opt idl2
  infoRoutine = ROUTINE_INFO('sarscape_script_displacement_and_geocoding', /SOURCE)

  CATCH, error
  if error ne 0 then begin
    PRINT, !error_state.msg
    return
  endif

  CLI_args=COMMAND_LINE_ARGS()
  PRINT, CLI_args
    
  RESTORE, 'loadini.sav'
  jsonini_st=loadini()
  params=JSON_PARSE(jsonini_st)
  jsonini_st=loadpaths(params['pathconfig'])
  
  if CLI_args[0] EQ "" then begin
    paths=JSON_PARSE(jsonini_st)
    inImages_master=paths[params['pathmaster']]
    output=paths[params['pathIFG']]
  endif else begin
    inImages_master=CLI_args[0]
    output=CLI_args[1]
  endelse
  

  ; 1) SARscape batch initialization and temporary directory setting
  if (strpos(!prompt,'ENVI') eq -1 ) then begin
    aTmp =  output + PATH_SEP() +params['displacement_work_dir']
    FILE_MKDIR,aTmp
    SARscape_Batch_Init,Temp_Directory=aTmp
  endif
  
  ;;create output DEM directory
  DEM = inImages_master+PATH_SEP()+params['dem_dir']+PATH_SEP()
  ;inMaster = FILE_SEARCH(ingestion_folder_1, '*VV_slc_list')
  ;inSlave = FILE_SEARCH(ingestion_folder_2, '*VV_slc_list')
  inDem = DEM + params['DEM_file']
  infile = FILE_SEARCH(output, '*'+params['refinement_out']+'_upha') 
  coherence_data = FILE_SEARCH(output, '*'+params['filtering_out']+'_cc')
  output_root = output+PATH_SEP()+params['refinement_out']+params['dispandgeo_out']

  ;*************************************************************************************
  ;*   BATCH STEP 1 DEFINITION FOR DISPLACEMENT AND GEOCODING                                   *
  ;*************************************************************************************


  ;Create the INSARPHASETODISPLACEMENT object
  OB = obj_new('SARscapeBatch',Module='INSARPHASETODISPLACEMENT')
  IF (~OBJ_VALID(OB)) THEN BEGIN
    ; The object is not valid then the user must manage the error
    ; Exit from SARscape batch
    SARscape_Batch_Exit
    return
  ENDIF

  ;Fill the Parameters
  OB->Setparam,'input_file_name', infile
  OB->Setparam,'coherence_file', coherence_data
  OB->Setparam,'dem_file_name', inDem
  OB->Setparam,'output_file', output_root


  ;Verify the parameters
  ok = OB->VerifyParams(Silent=0)


  IF ~ok THEN BEGIN
    Print,' ************************************************************* '
    Print,' Module can not be executed; Some parameters need to be filled '
    Print,' ************************************************************* '
    ; Exit from SARscape batch
    SARscape_Batch_Exit
    return;
  ENDIF

  ; 6) execute the process
  if (strpos(!prompt,'ENVI') gt -1 ) then begin
    OK = OB->ExecuteProgress(show_end_dialog='NotOK')
  endif else begin
    OK = OB->Execute();
  endelse

  IF OK THEN BEGIN
    Print,' ************* '
    Print,'STEP SUCCESS...... '
    Print,' ************* '
  ENDIF else begin
    aErrCode = ''
    ; extract the error message from error file
    aOutMsg = get_SARscape_error_string('NotOK',ERROR_CODE=aErrCode)
    aOutMsg = get_SARscape_error_string('OK',ERROR_CODE=aErrCode)
    Print,' ************* '
    Print,'STEP FAIL...... '
    Print, 'ERROR CODE : '+aErrCode
    Print, aOutMsg
    Print,' ************* '
  ENDELSE
  WAIT, 0.1
end