pro sarscape_script_phase_unwrapping

  compile_opt idl2

  infoRoutine = ROUTINE_INFO('sarscape_script_phase_unwrapping', /SOURCE)

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
    output=paths[params['pathIFG']]
  endif else begin
    output=CLI_args[0]
  endelse

  ; 1) SARscape batch initialization and temporary directory setting
  if (strpos(!prompt,'ENVI') eq -1 ) then begin
    aTmp =  output + PATH_SEP()+params['phase_work_dir']
    FILE_MKDIR,aTmp
    SARscape_Batch_Init,Temp_Directory=aTmp
  endif
  
  interferogram_data = FILE_SEARCH(output, '*'+params['filtering_out']+'_fint') 
  coherence_data = FILE_SEARCH(output, '*'+params['filtering_out']+'_cc') 
  unwrapped_phase_file = output+PATH_SEP()+params['phase_out']
  doppler_rg_poly_degree_xml = 3
  doppler_az_poly_number_xml = 50

  ;*************************************************************************************
  ;*   BATCH STEP 1 DEFINITION FOR PHASE UNWRAPPING                                    *
  ;*************************************************************************************


  ;Create the INSARPHASEUNWRAPPING object
  OB = obj_new('SARscapeBatch',Module='INSARPHASEUNWRAPPING')
  IF (~OBJ_VALID(OB)) THEN BEGIN
    ; The object is not valid then the user must manage the error
    ; Exit from SARscape batch
    SARscape_Batch_Exit
    return
  ENDIF

  ;Fill the Parameters
  OB->Setparam,'infile_name', interferogram_data
  OB->Setparam,'outfile_name', unwrapped_phase_file
  OB->Setparam,'coherencefile_name', coherence_data
  OB->Setparam,'doppler_rg_poly_degree' , doppler_rg_poly_degree_xml
  OB->Setparam,'doppler_az_poly_number' , doppler_az_poly_number_xml
  
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