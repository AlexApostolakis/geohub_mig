FUNCTION filter, oNode, parameter
  name = oNode->getNodeName()
  IF name EQ parameter OR name EQ 'modeling_lame_m' THEN $
    RETURN, 1 ; accept
  RETURN, 3 ;; skip
END



PRO xml_read
  oDoc = OBJ_NEW( 'IDLffXMLDOMDocument', $
    FILENAME='C:\Andreas\Andreas_Testing\test_xml\data\sarscape_values_for_sentinel_testing_1.xml' )
  oNodeIterator = oDoc->createNodeIterator( OBJ_NEW(), $
    FILTER_NAME='filter' )
  oNode = oNodeIterator->nextNode()
  WHILE OBJ_VALID( oNode ) DO BEGIN
    ; Assuming only one text node per element
    PRINT, (oNode->GetFirstChild())->getNodeValue()
    ;oNameText = oNode->GetFirstChild()  
    ;oNameText->SetNodeValue, '10' 
    oNode = oNodeIterator->nextNode()
  ENDWHILE
  ;oDoc->Save, FILENAME='C:\Andreas\Andreas_Testing\test_xml\data\sample2.xml'
  PRINT
  OBJ_DESTROY, oDoc

END