pro  sarscape_script_geocoding_rad_cal

  compile_opt idl2


  CATCH, error
  if error ne 0 then begin
    if n_elements(tlb) eq 1 then widget_control, tlb,/DESTROY
    k = dialog_message(!error_state.msg,/ERROR)
    return
  endif

  ;;set the test directory
  infoRoutine = ROUTINE_INFO('sarscape_script_geocoding_rad_cal', /SOURCE)
  theTestDir = FILE_DIRNAME(infoRoutine.PATH) +PATH_SEP()+'data'

  ;;create output directory
  output = theTestDir+PATH_SEP() + 'results'
  FILE_MKDIR,output


  ;SARscape batch initialization and temporary directory setting
  if (strpos(!prompt,'ENVI') eq -1 ) then begin
    aTmp = theTestDir+PATH_SEP()+'temp'
    FILE_MKDIR,aTmp
    SARscape_Batch_Init,Temp_Directory=aTmp
  endif
  
  
;*************************************************************************************
;*      PARAMETERS DEFINITION FOR GEOCODING AND RADIOMETRIC CALIBRATION              *
;*************************************************************************************

  inRasterName_data = output+PATH_SEP()+'newtestInterf_fint';
  outRasterName = output+PATH_SEP()+'output'+PATH_SEP()+'newtestInterf_fint_geo';
  inRasterName_dem = theTestDir+'\DEM\' + 'start_dem._dem'
  aGridSize = 20.0
  
  aTemp = aTmp+PATH_SEP()+'step'


;*************************************************************************************
;*   BATCH STEP 1 GEOCODING AND RADIOMETRIC CALIBRATION                              *
;*************************************************************************************


  ;Create the BasicGeocoding object
  OB = obj_new('SARscapeBatch',Module='BasicGeocoding')
  IF (~OBJ_VALID(OB)) THEN BEGIN
    ; The object is not valid then the user must manage the error
    ; Exit from SARscape batch
    SARscape_Batch_Exit
    return
  ENDIF

  ;Fill the Parameters
  aInList = [inRasterName_data]
  OB->Setparam,'input_file_list', aInList
  aOutList = [outRasterName]
  OB->Setparam,'output_file_list', aOutList
  OB->Setparam,'dem_file_name', inRasterName_dem
  OB->Setparam,'geocode_grid_size_y', strcompress(string(aGridSize),/remove_all)
  OB->Setparam,'geocode_grid_size_x', strcompress(string(aGridSize),/remove_all)
  
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