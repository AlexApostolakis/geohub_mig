pro  SARscape_script_adapt_filt_coh_gen

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

  ;;set the test directory
  infoRoutine = ROUTINE_INFO('SARscape_script_adapt_filt_coh_gen', /SOURCE)

  ; 1) SARscape batch initialization and temporary directory setting
  if (strpos(!prompt,'ENVI') eq -1 ) then begin
    aTmp =  output + PATH_SEP() +params['adapt_filt_work_dir']
    FILE_MKDIR,aTmp
    SARscape_Batch_Init,Temp_Directory=aTmp
  endif
  
  
  inMaster = FILE_SEARCH(output, '*file_result_master_pwr') 
  inSlave = FILE_SEARCH(output, '*file_result_slave_pwr') 

  FilteringMethod = 'GOLDSTEIN'
  GoldsteinWinsize  = '32'

  inInter = output+PATH_SEP() + params['ifg_out']+'_dint'
  outName = output+PATH_SEP() + params['filtering_out']
  doppler_rg_poly_degree_xml = 3
  doppler_az_poly_number_xml = 50


;*************************************************************************************
;*   BATCH STEP 1 ADAPTIVE FILTER AND COHERENCE GENERATION                           *
;*************************************************************************************


; 8) Create the INSARFILTERANDCOHERENCE object
OB = obj_new('SARscapeBatch',Module='INSARFILTERANDCOHERENCE')
IF (~OBJ_VALID(OB)) THEN BEGIN
  if (aEnviRun eq 0) then  SARscape_ErrorMsg, 'The object is not valid then the user must manage the error'
  if (aEnviRun eq 0) and (aMake_BatchfileOnly eq 0) then SARscape_Batch_Exit
  return

ENDIF


; 9 ) Fill the Parameters
OB->Setparam,'input_master_file_name', inMaster
OB->Setparam,'input_slave_file_name', inSlave
OB->Setparam,'input_interf_file_name',inInter
OB->Setparam,'out_root_file',outName
OB->Setparam,'filtering_method',FilteringMethod
OB->Setparam,'goldstein_winsize',GoldsteinWinsize
OB->Setparam,'doppler_rg_poly_degree' , doppler_rg_poly_degree_xml
OB->Setparam,'doppler_az_poly_number' , doppler_az_poly_number_xml

; 10) Verify the parameters
ok = OB->VerifyParams(Silent=0)


IF ~ok THEN BEGIN

  SARscape_ErrorMsg,' Module can not be executed; Some parameters need to be filled '

  return
ENDIF

; 11) execute the process
if (strpos(!prompt,'ENVI') gt -1 ) then begin
  OK = OB->ExecuteProgress(show_end_dialog='NotOK')
endif else begin
  OK = OB->Execute();
endelse

IF OK THEN BEGIN
  PRINT,'STEP SUCCESS......  STEP 5 ADAPTIVE FILTER AND COHERENCE GENERATION'
ENDIF else begin
  SARscape_ErrorMsg,'STEP FAILED ......  STEP 5 ADAPTIVE FILTER AND COHERENCE GENERATION'
  aOutMsg = get_SARscape_error_string('NotOK',ERROR_CODE=aErrCode)
  PRINT, aOutMsg
ENDELSE
WAIT, 0.1
end