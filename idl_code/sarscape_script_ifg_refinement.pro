pro sarscape_script_ifg_refinement

  compile_opt idl2
  infoRoutine = ROUTINE_INFO('sarscape_script_ifg_refinement', /SOURCE)

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
    inImages_slave=paths[params['pathslave']]
    output=paths[params['pathIFG']]
    xml_file =paths[params['configXML']]
  endif else begin
    inImages_master=CLI_args[0]
    inImages_slave=CLI_args[1]
    output=CLI_args[2]
    xml_file=CLI_args[3]
  endelse

  ; 1) SARscape batch initialization and temporary directory setting
  if (strpos(!prompt,'ENVI') eq -1 ) then begin
    aTmp =  output + PATH_SEP() +params['ifg_refinement_work_dir']
    FILE_MKDIR,aTmp
    SARscape_Batch_Init,Temp_Directory=aTmp
  endif
  
  interferogram_data = FILE_SEARCH(output, '*'+params['filtering_out']+'_fint')
  coherence_data = FILE_SEARCH(output, '*'+params['filtering_out']+'_cc')
  unwrapped_phase_file = FILE_SEARCH(output, '*'+params['phase_out'])
  ingestion_folder_1 = inImages_master+PATH_SEP()+params['import_dir']+PATH_SEP()
  ingestion_folder_2 = inImages_slave +PATH_SEP()+params['import_dir']+PATH_SEP()
  
  inMaster = FILE_SEARCH(ingestion_folder_1, '*VV_slc_list')
  inSlave = FILE_SEARCH(ingestion_folder_2, '*VV_slc_list')
  inDem = inImages_master+PATH_SEP()+params['dem_dir']+PATH_SEP() + params['DEM_file']

  output_root = output+PATH_SEP()+params['refinement_out']
  synth_file = output+PATH_SEP()+'file_result_sint'
  slant_ran_dem = output+PATH_SEP()+'file_result_srdem'
  gcps_ms = output+PATH_SEP()+params['autogcp_out']
  coregistration_with_DEM_flag_tr='OK'

  doppler_rg_poly_degree_xml = 3
  doppler_az_poly_number_xml = 50
  cc_number_res_coeff_range_xml = 2
  cc_number_res_coeff_azimuth_xml = 1
  cc_init_range_win_size_xml = 2048
  cc_init_azimuth_win_size_xml = 4096
  cc_range_win_number_cc_xml = 12
  cc_azimuth_win_number_cc_xml = 3
  cc_azimuth_win_size_cc_xml = 128
  cc_oversampling_cc_xml = 4
  cc_range_win_number_fine_xml = 25
  cc_azimuth_win_number_fine_xml = 8
  rg_looks_nbr_xml = 5
  az_looks_nbr_xml = 1
  
  ;*************************************************************************************
  ;*   BATCH STEP 1 DEFINITION FOR FOR INTERFEROGRAM REFINEMENT                               *
  ;*************************************************************************************


  ;Create the INSARREFINEMENTANDREFLATTENING object
  OB = obj_new('SARscapeBatch',Module='INSARREFINEMENTANDREFLATTENING')
  IF (~OBJ_VALID(OB)) THEN BEGIN
    ; The object is not valid then the user must manage the error
    ; Exit from SARscape batch
    SARscape_Batch_Exit
    return
  ENDIF

  ;Fill the Parameters
  OB->Setparam,'interferogram_file_name', interferogram_data
  OB->Setparam,'input_upha_file_name', unwrapped_phase_file
  OB->Setparam,'coherence_file_name', coherence_data
  OB->Setparam,'input_master_file_name', inMaster
  OB->Setparam,'input_slave_file_name', inSlave
  OB->Setparam,'dem_file_name', inDem
  OB->Setparam,'output_root_name', output_root
  OB->Setparam,'synthetic_file_name', synth_file
  OB->Setparam,'slant_range_dem_file_name', slant_ran_dem
  OB->Setparam,'refinement_gcp_file_name', gcps_ms
  OB->Setparam,'coregistration_with_DEM_flag', coregistration_with_DEM_flag_tr
  OB->Setparam,'doppler_rg_poly_degree', doppler_rg_poly_degree_xml
  ;OB->Setparam,'cc_number_res_coeff_range', cc_number_res_coeff_range_xml
  ;OB->Setparam,'cc_number_res_coeff_azimuth', cc_number_res_coeff_azimuth_xml
  OB->Setparam,'cc_init_range_win_size', cc_init_range_win_size_xml
  OB->Setparam,'cc_init_azimuth_win_size', cc_init_azimuth_win_size_xml
  OB->Setparam,'cc_range_win_number_cc', cc_range_win_number_cc_xml
  OB->Setparam,'cc_azimuth_win_number_cc', cc_azimuth_win_number_cc_xml
  OB->Setparam,'cc_azimuth_win_size_cc', cc_azimuth_win_size_cc_xml
  OB->Setparam,'cc_oversampling_cc', cc_oversampling_cc_xml
  OB->Setparam,'cc_range_win_number_fine', cc_range_win_number_fine_xml
  OB->Setparam,'cc_azimuth_win_number_fine', cc_azimuth_win_number_fine_xml
  ;OB->Setparam,'rg_looks_nbr', rg_looks_nbr_xml
  ;OB->Setparam,'az_looks_nbr', az_looks_nbr_xml
  OB->Setparam,'doppler_az_poly_number', doppler_az_poly_number_xml
  
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
    Print,'STEP  FAIL...... '
    Print, 'ERROR CODE : '+aErrCode
    Print, aOutMsg
    Print,' ************* '
  ENDELSE
  WAIT, 0.1
end