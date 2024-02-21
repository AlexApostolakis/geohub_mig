pro  sarscape_script_baseline_estimation

  compile_opt idl2

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
  
  if CLI_args[0] EQ '' and jsonini_st NE '' then begin
    paths=JSON_PARSE(jsonini_st)
    inImages_master=paths[params['pathmaster']]
    inImages_slave=paths[params['pathslave']]
    output=paths[params['pathIFG']]
    xml_file =paths[params['configXML']]
  endif else begin
    inImages_master=CLI_args[0]
    inImages_slave=CLI_args[1]
    output=CLI_args[2]
    xml_file=CLI_args[3]
  endelse

  ; Close the file and free the file unit

  ;;set the test directory
  infoRoutine = ROUTINE_INFO('sarscape_script_baseline_estimation', /SOURCE)

  ; 1) SARscape batch initialization and temporary directory setting
  if (strpos(!prompt,'ENVI') eq -1 ) then begin
    aTmp =  output + PATH_SEP() + params['baseline_work_dir']
    FILE_MKDIR,aTmp
    SARscape_Batch_Init,Temp_Directory=aTmp
  endif
  

  ingestion_folder_1 = inImages_master+PATH_SEP()+params['import_dir']+PATH_SEP()
  ingestion_folder_2 = inImages_slave+PATH_SEP()+params['import_dir']+PATH_SEP()
  
  inMaster = FILE_SEARCH(ingestion_folder_1, '*VV_slc_list') 
  inSlave = FILE_SEARCH(ingestion_folder_2, '*VV_slc_list') 

  output_1 = output + PATH_SEP()+params['baseline_out1']
  output_2 = output + PATH_SEP()+params['baseline_out2']


  ;*************************************************************************************
  ;*   BATCH STEP 1 DEFINITION FOR BASELINE ESTIMATION                                 *
  ;*************************************************************************************


  ;Create the INSARBASELINEESTIMATION object
  OB = obj_new('SARscapeBatch',Module='INSARBASELINEESTIMATION')
  IF (~OBJ_VALID(OB)) THEN BEGIN
    ; The object is not valid then the user must manage the error
    ; Exit from SARscape batch
    SARscape_Batch_Exit
    return
  ENDIF

  ;Fill the Parameters
  OB->Setparam,'input_master_file', inMaster
  OB->Setparam,'input_slave_file', inSlave
  OB->Setparam,'output_file', output_1
  OB->Setparam,'output_be_file', output_2


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

end