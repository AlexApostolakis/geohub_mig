pro  SARscape_script_interferogram_test

compile_opt idl2

;*************************************************************************************
;*   BATCH STEP 3 INTERFEROGRAM GENERATION                                           *
;*************************************************************************************


CATCH, error
if error ne 0 then begin
  PRINT, !error_state.msg
  return
endif

infoRoutine = ROUTINE_INFO('SARscape_script_interferogram_test', /SOURCE)


;**********************************************************
; Config paths etc.
;**********************************************************

CLI_args=COMMAND_LINE_ARGS()
PRINT, CLI_args
  
RESTORE, 'loadini_test.sav'
jsonini_st=loadini_test()
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
  aTmp =  output+PATH_SEP()+params['interferogram_work_dir']
  FILE_MKDIR,aTmp
  SARscape_Batch_Init,Temp_Directory=aTmp
endif

; 3) Create the INSARINTERFEROGRAMGENERATION object
OB = obj_new('SARscapeBatch',Module='INSARINTERFEROGRAMGENERATION')
IF (~OBJ_VALID(OB)) THEN BEGIN
  if (aEnviRun eq 0) then  SARscape_ErrorMsg, 'The object is not valid then the user must manage the error'
  if (aEnviRun eq 0) and (aMake_BatchfileOnly eq 0) then SARscape_Batch_Exit
  return

ENDIF


  ;**********************************************************
  ;     take values from xml
  ;**********************************************************

oDoc = OBJ_NEW( 'IDLffXMLDOMDocument', $
  FILENAME=xml_file )

ifg_params=params['interferogram_xml_params']
ifg_params_num=SIZE(ifg_params, /N_ELEMENTS)
i=0
while i LT ifg_params_num do begin
  oNodeList= oDoc->GetElementsByTagName(ifg_params[i])
  n=oNodeList->GetLength()
  if oNodeList->GetLength() EQ 1 then begin 
    oNode = oNodeList->Item(0)
    ; Assuming only one text node per element
    value_of_var = (oNode->GetFirstChild())->getNodeValue()
    name = oNode->getNodeName()
    ;string to set parameter
    string_to_execute = "OB->Setparam,"+"'"+name+"', "+value_of_var
    PRINT, string_to_execute
    void = EXECUTE(string_to_execute)
  endif
  i=i+1
endwhile
  OBJ_DESTROY, oDoc
  
ingestion_folder_1 = inImages_master+PATH_SEP()+params['import_dir']+PATH_SEP()
ingestion_folder_2 = inImages_slave +PATH_SEP()+params['import_dir']+PATH_SEP()

;;create output DEM directory
DEM = inImages_master+PATH_SEP()+params['dem_dir']+PATH_SEP()
inMaster = FILE_SEARCH(ingestion_folder_1, '*VV_slc_list')
inSlave = FILE_SEARCH(ingestion_folder_2, '*VV_slc_list')

inDem = DEM + params['DEM_file']
outName = output+PATH_SEP()+ params['ifg_out']
outName1 = output+PATH_SEP()+ 'file_result_par'
coregistration_with_DEM_flag_tr='OK'

; 4) Fill the Parameters
OB->Setparam,'input_master_file_name', inMaster
OB->Setparam,'input_slave_file_name', inSlave
OB->Setparam,'output_root_file_name', outName
OB->Setparam,'dem_file_name', inDem
OB->Setparam,'coregistration_with_DEM_flag', coregistration_with_DEM_flag_tr


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
  print,'STEP SUCCESS......  STEP 3 INTERFEROGRAM GENERATION'
  Print,' ************* '
ENDIF else begin
  SARscape_ErrorMsg,'STEP FAILED ......  STEP 3 INTERFEROGRAM GENERATION'
  return
ENDELSE
WAIT, 0.1
end