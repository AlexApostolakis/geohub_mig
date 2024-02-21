pro testcliargs2
  compile_opt idl2

  RESTORE, 'loadini.sav'
  jsonini_st=loadini()
  params=JSON_PARSE(jsonini_st)
  jsonini_st=loadpaths(params['pathconfig'])

  CLI_args=COMMAND_LINE_ARGS()
  
  file = params['pathconfig']+'_test2'
  OPENW, lun, file, /GET_LUN
  PRINT, "Args:", CLI_args[0]
  if CLI_args[0] NE "" then begin
    PRINTF, lun, "Args 2:", CLI_args[0]
  endif else begin
     PRINTF, lun, "No Args 2"
  endelse
  FREE_LUN, lun

  n=SIZE(CLI_args, /N_ELEMENTS)
  if CLI_args[0] EQ "" then begin
    PRINT, "no args"
  endif else begin
    PRINT, n," args", CLI_args
  endelse
  PRINT, "STEP SUCCESS"
  WAIT, 20
end