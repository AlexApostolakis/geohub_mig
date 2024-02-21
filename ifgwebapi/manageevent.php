<?php

//test with
//localhost/ifgwebapi/manageevent.php?login=Sam&command=start&service_id=33
//localhost/ifgwebapi/manageevent.php?login=Sam&command=getcommand
//include($_SERVER['DOCUMENT_ROOT']."/ifgwebapi/api.php");
include("api.php");

if (isset($_GET[$API_LOGIN]) && isset($_GET [$API_COMMAND]))
{
	$APIjsonpath = $API_COMMANDFOLDER.'/'.$API_JSONFILENAME;
	if (($_GET [$API_COMMAND] != $API_GETCOMMAND) && isset($_GET [$API_SERVICEID]))  {
		if (!is_dir($API_COMMANDFOLDER)) {
		   mkdir($API_COMMANDFOLDER, 0777, true);
		}
		$post_data = json_decode(json_encode($_GET));
		//$post_data = json_encode($_GET);
		$fp = fopen($APIjsonpath, 'w');
		fwrite($fp, json_encode($post_data));
		fclose($fp);
		echo '"'.$_GET [$API_COMMAND].'" command initiated for service id '.$_GET [$API_SERVICEID];
	} else if ($_GET [$API_COMMAND] == $API_GETCOMMAND){
		if (file_exists($APIjsonpath)) {
			$strCommand = file_get_contents($APIjsonpath);
			$cmdObj = json_decode($strCommand, true);
			$cmdJSON = json_encode($cmdObj);
			header('Content-Type: application/json');
			echo $cmdJSON;
			unlink($APIjsonpath);
		} else {
			if (!isset($cmdObj)) $cmdObj = new stdClass();
			$cmdObj -> command = "none";
			$cmdObj -> login = "none";
            header('Content-Type: application/json');			
			echo json_encode($cmdObj);
		}
	} else {
		echo "url is invalid";
		http_response_code(404);
	}
} else {
	echo "url is invalid";
	http_response_code(404);
}

?>