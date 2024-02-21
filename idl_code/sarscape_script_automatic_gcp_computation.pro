pro sarscape_script_automatic_gcp_computation

  compile_opt idl2

  infoRoutine = ROUTINE_INFO('sarscape_script_automatic_gcp_computation', /SOURCE)

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
    output=CLI_args[1]
    xml_file=CLI_args[2]
  endelse

  ; 1) SARscape batch initialization and temporary directory setting
  if (strpos(!prompt,'ENVI') eq -1 ) then begin
    aTmp =  output + PATH_SEP() + params['gcp_work_dir']
    FILE_MKDIR,aTmp
    SARscape_Batch_Init,Temp_Directory=aTmp
  endif
  
  infile_name = FILE_SEARCH(output, '*file_result_master_pwr') 
  coherencefile_name = FILE_SEARCH(output, '*'+params['filtering_out']+'_cc')
  outfile_name = output + PATH_SEP()+params['autogcp_out']
  min_gcp_number_r = '20';
  inDEM = inImages_master +PATH_SEP()+params['dem_dir']+PATH_SEP()+ params['DEM_file']

  doppler_rg_poly_degree_xml = 3
  doppler_az_poly_number_xml = 50
  
  ;*************************************************************************************
  ;*   PARAMETERS DEFINITION FOR AUTOMATIC GCP COMPUTATION                                      *
  ;*************************************************************************************


  ;Create the TOOLS_AUTOMATIC_GCP_GENERATION object
  OB = obj_new('SARscapeBatch',Module='TOOLS_AUTOMATIC_GCP_GENERATION')
  IF (~OBJ_VALID(OB)) THEN BEGIN
    ; The object is not valid then the user must manage the error
    ; Exit from SARscape batch
    SARscape_Batch_Exit
    return
  ENDIF

  ;Fill the Parameters
  OB->Setparam,'input_file_name', infile_name
  OB->Setparam,'output_root_name', outfile_name
  OB->Setparam,'coherence_file', coherencefile_name
  OB->Setparam,'min_gcp_number', min_gcp_number_r
  OB->Setparam,'dem_file_name', inDEM
  ;OB->Setparam,'doppler_rg_poly_degree' , doppler_rg_poly_degree_xml
 ; OB->Setparam,'doppler_az_poly_number' , doppler_az_poly_number_xml
  
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