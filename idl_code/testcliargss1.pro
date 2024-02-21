pro testcliargss1
  compile_opt idl2

 

  CLI_args=COMMAND_LINE_ARGS()
  

  n=SIZE(CLI_args, /N_ELEMENTS)
  if CLI_args[0] EQ "" then begin
    PRINT, "no args"
  endif else begin
    PRINT, n," args", CLI_args
  endelse
  PRINT, "STEP SUCCESS"
  WAIT, 20
end