pro testcliargs
  compile_opt idl2

  RESTORE, 'loadini.sav'
  jsonini_st=loadini()
  params=JSON_PARSE(jsonini_st)
  jsonini_st=loadpaths(params['pathconfig'])

  CLI_args=COMMAND_LINE_ARGS()
  
  file = params['pathconfig']+'_test1'
  OPENW, lun, file, /GET_LUN
  PRINT, "Args:", CLI_args[0]
  if CLI_args[0] NE "" then begin
    PRINTF, lun, "Args:", CLI_args[0]
  endif else begin
     PRINTF, lun, "No Args"
  endelse
  FREE_LUN, lun

  n=SIZE(CLI_args, /N_ELEMENTS)
  if CLI_args[0] EQ "" then begin
    PRINT, "no args"
  endif else begin
    PRINT, n," args", CLI_args
  endelse
  
  rootpath=GETENV('GEOHUBROOT')
  PRINT, rootpath
  Print,'STEP SUCCESS...... '
  WAIT, 120

end