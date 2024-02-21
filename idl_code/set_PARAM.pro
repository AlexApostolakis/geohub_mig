pro set_PARAM

  compile_opt idl2


  CATCH, error
  if error ne 0 then begin
    if n_elements(tlb) eq 1 then widget_control, tlb,/DESTROY
    k = dialog_message(!error_state.msg,/ERROR)
    return
  endif

; 4) Fill the Parameters
  OB->Setparam,'input_file_list', inImages
  OB->Setparam,'input_orbit_file_list', inOrbits
  OB->Setparam,'output_file_list', outName
  OB->Setparam,'rename_the_file_using_parameters_flag', 'OK'
  
end