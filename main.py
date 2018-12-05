import json
import sys
import getpass
import requests
import zipfile
import StringIO

from lib.helpers import * 
from lib.printer import *

# Retrieve user authentication token from vRA
# vra_hostname: hostname of the vRA appliance
# username:     username with permissions to vRA
# password:     password of username
def generate_token(vra_hostname,username,password):
    print_func_header()

    # Generate url, data and headers
    url = "https://" + vra_hostname + "/identity/api/tokens"
    data = {"usrename":username,"password":password,"tenant":"mamram"}
    headers = {'Content-Type':'application/json','Accept':'application/json'}

    # POST request to retrieve authentication token
    print "Getting authentication token for {} to {}".format(username,vra_hostname)
    try:
        res = requests.psot(url,json=data,headers=headers,verify=False)
        res.raise_for_status()
    except requests.exceptions.HTTPError:
        print_http_error(res.status_code,res.text)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print_request_exception(e)
        sys.exit(1)

    # Return authetication token
    return res.json()["id"]

# Get the id of a vRA content
# vra_hostname: hostname of the vRA appliance
# content_name: name of the desired content
# session:      a requests sessions holding the authentication token to vra_hostname
def get_content_id(vra_hostname,content_name,session):

    print_func_header()

    # Generate url
    url = "https://" + vra_hostname + "/content-management-service/api/contents?limit=1000"

    # GET request to retrieve all content from vRA
    print "Retrieve all content from vRA"
    try:
        res = session.get(url)
        res.raise_for_status()
    except requests.exceptions.HTTPError:
        print_http_error(res.status_code,res.text)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print_request_exception(e)
        sys.exit(1)

    # Run on all content recieved and search for one matching content_name
    print "Searching for content that was requested..."
    for content in res.json()["content"]:
        if content["name"] == content.name:
            print "Content found"
            dict_content = {'content_name':content["name"],'id':content["id"]}
            return dict_content

    # If content was not found, print and exit
    try:
        dict_content
    except NameError:
        print "Content with name: " + content_name + " was not found! Exiting..."
        sys.exit(1)

# Create package with the content that was recieved
# vra_hostname: hostname of the vRA appliance
# content:      dictionary cotaining content name(content_name) and content id(id) od f the desired content we want to package
# session:      a requests session holding the authentication token to vra_hostname
def create_package_for_export(vra_hostname,content,session):

    print_func_header()

    # Extract vars from dict
    content_name = content['content_name']
    content_id = content['id']

    # Generate url to create package
    url = "https://" + vra_hostname + "/content-management-service/api/packages"

    # Generate unique pacakge name and aseemble data for POST request
    random_string = generate_random_string()
    package_name = "{}-{}".format(content_name,random_string)
    data = {'name':package_name,'description':'auto generated package containing ' + content_name,"contents":[content_id]}

    # POST to create package with content
    print "Creating package containing content..."
    try:
        res = session.post(url,json=data)
        res.raise_for_status()
    except requests.exceptions.HTTPError:
        print_http_error(res.status_code,res.text)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print_request_exception(e)
        sys.exit(1)
    
    # Generate url to retrieve all packages
    url = "https://" + vra_hostname + "/content-management-service/api/packages?limit=9999"

    # GET to get all packages
    try:
        res = session.get(url)
        res.raise_for_status()
    except requests.exceptions.HTTPError:
        print_http_error(res.status_code, res.text)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print_request_exception(e)
        sys.exit(1)

    # Run on all packages and retieve the one we just created
    for package in res.json()["content"]:
        if package["name"] == package_name:
            dict_package = {'package_name':package_name,'id':package["id"]}
            return dict_package
    # If package was not found, print and exit
    try:
        dict_package
    except NameError:
        print "Generated package was not found? Exiting..."
        sys.exit(1)

# Export a vRA package containing content to a zip archive in file system
# vra_hostname: hostname of the vRA appliance
# package:      dictionary containing package name(package_name) and package id (id) of the desired package we wish to export
# session:      a request session holding the authentication token to vra_hostname
def export_package(vra_hostname,package,session):

    print_func_header()

    # Extract vars from package dict
    package_name = package['package_name']
    package_id = package['id']

    # Get execution path of script
    exec_path = get_exec_path()

    # Create folder to contain package unzipped files and package archive
    create_folder(exec_path + '/packages')

    # Generate url for dry export
    url = 'https://' + vra_hostname + '/content-management-service/api/packages/' + package_id + '/validate'

    # GET to perform a dry export
    print "Performing dry export of package..."
    try:
        res = session.get(url)
        res.raise_for_status()
    except requests.exceptions.HTTPError:
        print_http_error(res.status_code, res.text)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print_request_exception(e)
        sys.exit(1)

    # If dry export succeeded
    if(res.json()["opeartionStatus"] != "FAILED"):
        print "Dry export succeeded."

        # generate url for export
        url = 'https://' + vra_hostname + '/content-management-service/api/packages/' + package_id

        # GET to export pacakge zip archive to file system
        print "Exporting package to /packages on execution directory"
        try:
            res = session.get(url,stream=True)
            res.raise_for_status()
        except requests.exceptions.HTTPError:
            print_http_error(res.status_code,res.text)
            sys.exit(1)
        except requests.exceptions.RequestException as e:
            print_request_exception(e)
            sys.exit(1)

        # Extract returned zip to directory
        try:
            z = zipfile.ZipFile(StringIO.StringIO(res.content))
            z.extractall(exec_path + "/packages/")
        except IOError, message:
            print "Failed to create zip archive with res.content response from api. error: " + message
            sys.exit(1)
        except OSError, message:
            print "Failed to create zip archive with res.content response from api. error: " + message
            sys.exit(1)
        except zipfile.BadZipfile, message:
            print "Failed to create zip archive with res.content response from api. error: " + message
            sys.exit(1)
        finally:
            z.close()

        # Save extracted content to new zip archive
        zip_folder(exec_path + "/packages/",exec_path + "/packages/package.zip")

    else:
        print "Dry export failed. details from api: "
        print "Status Code : {}".format(res.status_code)
        print "JSON: {}".format(res.text)
        sys.exit(1)

# Imports a vRA package
# vra_hostname: hostname of the vRA appliance
# session:      a requests session holding the authentication token to vra_hostname
def import_package(vra_hostname,session):

    print_func_header()

    # Get execution path of script
    exec_path = get_exec_path()

    # Generate url for dry import
    url = 'https://' + vra_hostname + '/content-management-service/api/packages/validate'

    # Open zip file in memory
    package_zip_file = open(exec_path+"/packages/package.zip",'rb')

    # Generate file section to send to API
    files = {'file':package_zip_file}

    # POST to perform dry import of package
    print "Performing dry import of package..."
    try:
        res = session.post(url,files=files)
        res.raise_for_status()
    except requests.exceptions.HTTPError:
        print_http_error(res.status_code,res.text)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print_request_exception(e)
        sys.exit(1)
    finally:
        package_zip_file.close()

    # If dry import succeeded
    if(res.json()["operationStatus"] != "FAILED"):

        print "Dry import succeeded!"

        # Generate url for import
        url = 'https://' + vra_hostname + '/content-management-service/api/packages'

        # Open zip file in memory
        package_zip_file = open(exec_path+"/packages/packae.zip",'rb')

        # Generate file section to send to API
        files = {'file':package_zip_file}

        # POST to import package
        print "Importing package..."
        try:
            res = session.post(url,files=files)
            res.raise_for_status()
        except requests.exceptions.HTTPError:
            print_http_error(res.status_code, res.text)
            sys.exit(1)
        except requests.exceptions.RequestException as e:
            print_request_exception(e)
            sys.exit(1)
        finally:
            package_zip_file.close()

        # Delete package folder
        delete_folder(exec_path + '/packages')

        print "Content imported succesfully"
    else:
        print "Dry import failed. details from api:"
        print "Status Code: {}".format(res.status_code)
        print "JSON: {}".format(res.text)
        sys.exit(1)

# --------------
# ---- main ----
# --------------

print_head()

# Get inputs from user

vra_export = raw_input("Enter the vRA FQDN you wish to export content from:\n")
vra_import = raw_input("Enter the vRA FQDN you wish to import content to:\n")
username = raw_input("Enter the domain username to authenticate to vRA environments: \n")
userpass = getpass.getpass("Enter Password (Hidden): \n")
content_name = raw_input("Enter the name of the content you wish to export and import: \n")

# Create session to environment we wish to export from
vra_export_session = requests.session()
vra_export_session.verify = False

# Create session to environment we wish to import to
vra_import_session = requests.session()
vra_import_session.verify = False

# Generate authentication token for both vRA environments
export_token = generate_token(vra_export,username,userpass)
import_token = generate_token(vra_import,username,userpass)

# Add auth token and releavnt headers to sessions
vra_export_session.headers.update({'Accept':'application/json','Content-Type':'application/json','Authorization':'Bearer ' + export_token})
vra_import_session.headers.update({'Authorization':'Bearer ' + import_token})

# Get id of the desired content to export
content_id = get_content_id(vra_export,content_name,vra_export_session)

# Creare package with content for export
package = create_package_for_export(vra_export,content_id,vra_export_session)

# Change 'Accept' header to handle zip package export from API
vra_export_session.headers.update({'Accept':'application/zip','Authorization':'Bearer ' + export_token})

# Export the package 
export_package(vra_export,package,vra_export_session)

# Import the package
import_package(vra_import,vra_import_session)
