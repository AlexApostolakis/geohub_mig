pro untitled_3
file = 'C:\Andreas\Andreas_Testing\code_v3\SARscape_script_import_Sentinel_1_master_xml.txt'
OPENR, lun, file, /GET_LUN
; Read one line at a time, saving the result into array
array = ''
line = ''
WHILE NOT EOF(lun) DO BEGIN & $
  READF, lun, line & $
  array = [array, line] & $
  ; Close the file and free the file unit


ENDWHILE
  FREE_LUN, lun
FOREACH element, array DO BEGIN
  PRINT, element
  IF name EQ element THEN $
     RETURN, 1 ; accept
     PRINT, element
     
  RETURN, 3 ;; skip
ENDFOREACH
end