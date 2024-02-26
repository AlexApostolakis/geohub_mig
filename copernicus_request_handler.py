import requests
import json
import time

'''
def get_access_token(username, password):
    data = {
        "client_id": "cdse-public",
        "username": username,
        "password": password,
        "grant_type": "password",
    }

    try:
        response = requests.post(
            "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
            data=data,
            verify=False
        )
        response.raise_for_status()
        return response.json()["access_token"]
    except requests.exceptions.RequestException as e:
        print(e)
        raise Exception("Access token creation failed. Error: {}".format(e))
'''
    

def get_saved_token_data(token_file):
    try:
        with open(token_file, 'r') as file:
            return json.load(file)
    except IOError:
        return None


def save_token_data(access_token, expires_in, token_file):
    token_data = {
        "access_token": access_token,
        "expires_at": time.time() + expires_in
    }
    with open(token_file, 'w') as file:
        json.dump(token_data, file)


def is_token_valid(token_data):
    if token_data and "expires_at" in token_data:
        return time.time() < token_data["expires_at"]
    return False

def get_new_token(username, password):
    data = {
        "client_id": "cdse-public",
        "username": username,
        "password": password,
        "grant_type": "password",
    }
    try:
        response = requests.post(
            "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
            data=data,
            verify=False
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(e)
        raise Exception("Access token creation failed. Error: {}".format(e))

    token_info = response.json()
    return token_info["access_token"], token_info["expires_in"]

def get_access_token(username, password, token_file):    
    token_data = get_saved_token_data(token_file)
    if token_data and is_token_valid(token_data):
        token = token_data["access_token"]
    else:
        token, expires_in = get_new_token(username, password)
        save_token_data(token, expires_in, token_file)
    return token


def fetch_metadata(url, endpoint, access_token, session, query=None, max_retries=2):
    headers = {'Authorization': 'Bearer {}'.format(access_token)}
    err = ''
    url = url + endpoint
    for attempt in range(max_retries):
        # ODATA
        if query == None:
                # TODO: Unsafe fix for SSL verificaiton, need to check CA on this system
                # print(url)
                response = session.get(url, headers=headers, verify=False)
                # print(response.json()['Checksum'])
                response.raise_for_status()
                err += "\nMetadata fetched successfully on attempt {}".format(attempt + 1)
                return response.json()['Checksum']
        
        try:
            # TODO: Unsafe fix for SSL verificaiton, need to check CA on this system
            response = session.get(url + query, headers=headers, verify=False)
            #print(url + query)
            response.raise_for_status()
            err += "\nMetadata fetched successfully on attempt {}".format(attempt + 1)
            return response.json()

        except requests.exceptions.RequestException as e:
            err += "\nMetadata fetch attempt {} failed. Retrying...\n{}".format(attempt + 1, e)
    
    err += '\nMax metadata fetch retries reached. Fetch failed.'
    
    return url + query

def download_file(urls, output_file_path, access_token, session, max_retries=2, chunk_size=8192, names=[]):
    try:
        
        for attempt in range(max_retries):
            try:
                for i, url in enumerate(urls):
                    response = session.get(url, headers={'Authorization': 'Bearer {}'.format(access_token)}, stream=True)
                    with open(output_file_path + names[i], "wb") as file:
                        for chunk in response.iter_content(chunk_size):
                            if chunk:
                                file.write(chunk)
                print("Download attempt {} succeeded.".format(attempt + 1))
                return
    
            except requests.exceptions.RequestException as err:
                #self.log.info("Download Failed: {}".format(err))
                pass
    except Exception as e:
        print("Download attempt {} failed. Retrying...\n{}".format(attempt + 1, e))
        print('Max download retries reached. Download failed.')

def explore_json(obj):
    if isinstance(obj, dict):
        return {k: explore_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [explore_json(item) for item in obj]
    else:
        return obj