pro  SARscape_script_dem_extraction

  compile_opt idl2

  infoRoutine = ROUTINE_INFO('SARscape_script_dem_extraction', /SOURCE)

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
    inImages=paths[params['pathmaster']]
    manifest=inImages+PATH_SEP()+params['uncompressed_dir']+PATH_SEP()+'manifest.safe'
	xml_file=CLI_args[3]
  endif else begin
    inImages = CLI_args[0]
	xml_file=CLI_args[1]
  endelse


  ; 1) SARscape batch initialization and temporary directory setting
  if (strpos(!prompt,'ENVI') eq -1 ) then begin
    aTmp=inImages+PATH_SEP()+params['dem_dir']+PATH_SEP()+params['dem_work_dir']
    FILE_MKDIR,aTmp
    SARscape_Batch_Init,Temp_Directory=aTmp
  endif
  
  ingestion_folder=inImages+PATH_SEP()+params['import_dir']+PATH_SEP()

  ;;create output DEM directory
  DEM = inImages+PATH_SEP()+params['dem_dir']+PATH_SEP()
  FILE_MKDIR,DEM
  input_file = FILE_SEARCH(ingestion_folder, '*VV_slc_list_pwr') 
  output_file_dem = DEM + params['DEM_file']
  
  
  ;*************************************************************************************
  ;*   BATCH STEP 2 DEM EXTRACTION                                                     *
  ;*************************************************************************************

; 3) Create the TOOLSDEMEXTRACTIONSRTM4 object
  OB = obj_new('SARscapeBatch',Module='TOOLSDEMEXTRACTIONSRTM4')
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

  obj_params=params['dem_xml_params']
  obj_params_num=SIZE(obj_params, /N_ELEMENTS)
	i=0
	while i LT obj_params_num do begin
	  oNodeList= oDoc->GetElementsByTagName(obj_params[i])
	  n=oNodeList->GetLength()
	  if oNodeList->GetLength() EQ 1 then begin 
		oNode = oNodeList->Item(0)
		; Assuming only one text node per element
		value_of_var = (oNode->GetFirstChild())->getNodeValue()
		name = oNode->getNodeName()
		;string to set parameter
	  if isa(value_of_var,/NUMBER) EQ 1 then begin
	    st_value_of_var=value_of_var
	  endif else begin
	    st_value_of_var="'"+value_of_var+"'"
	  endelse
		string_to_execute = "OB->Setparam,"+"'"+name+"', "+st_value_of_var
		PRINT, string_to_execute
		void = EXECUTE(string_to_execute)
	  endif
	  i=i+1
	endwhile
	OBJ_DESTROY, oDoc

  ; 4) Fill the Parameters
  OB->Setparam,'output_file_dem_val', output_file_dem
  OB->Setparam,'reference_sr_image_val', input_file
  
  
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
    print,'STEP SUCCESS......  STEP 1 DEM EXTRACTION'
    Print,' ************* '
  ENDIF else begin
    SARscape_ErrorMsg,'STEP FAILED ......  STEP 1 DEM EXTRACTION FAILED'
    return
  ENDELSE
  WAIT, 0.1
  
end