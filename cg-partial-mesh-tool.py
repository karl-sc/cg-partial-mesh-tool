#!/usr/bin/env python
PROGRAM_NAME = "cg-partial-mesh-tool.py"
PROGRAM_DESCRIPTION = """
CloudGenix Partial Mesh Script Tool
---------------------------------------

This tool creates partial mesh domains by leveraging per site tags.
Simply define an arbitraty partial mesh domain tag by tagging a site
with a new tag using the prefix "AUTO-MESH_". For example branches
with the tag "AUTO-MESH_corporate" will have branch to branch tunnels
created between them.

A topology may include multiple mesh domains so long as the suffix
to the tag is unique among them. A site may have multiple domain tags
and be a member of multiple full mesh domains.

If a site already has a branch to branch mesh link to another site,
the WAN interfaces API call to create the link will fail but the script
will continue to proceed making it safe to run again.

This script will not remove Secure Fabric links between sites so be 
warned of creating too many links.

Before creation of the new topology, the planned mesh config will be
shown. Confirm the accuracy of the topology before confirmed with "yes"

"""

####Library Imports
from cloudgenix import API, jd
import os
import sys
import argparse


def parse_arguments():
    CLIARGS = {}
    parser = argparse.ArgumentParser(
        prog=PROGRAM_NAME,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=PROGRAM_DESCRIPTION
            )
    parser.add_argument('--token', '-t', metavar='"MYTOKEN"', type=str, 
                    help='specify an authtoken to use for CloudGenix authentication')
    parser.add_argument('--authtokenfile', '-f', metavar='"MYTOKENFILE.TXT"', type=str, 
                    help='a file containing the authtoken')
    args = parser.parse_args()
    CLIARGS.update(vars(args))
    return CLIARGS

def authenticate(CLIARGS):
    print("AUTHENTICATING...")
    user_email = None
    user_password = None
    
    sdk = API()    
    ##First attempt to use an AuthTOKEN if defined
    if CLIARGS['token']:                    #Check if AuthToken is in the CLI ARG
        CLOUDGENIX_AUTH_TOKEN = CLIARGS['token']
        print("    ","Authenticating using Auth-Token in from CLI ARGS")
    elif CLIARGS['authtokenfile']:          #Next: Check if an AuthToken file is used
        tokenfile = open(CLIARGS['authtokenfile'])
        CLOUDGENIX_AUTH_TOKEN = tokenfile.read().strip()
        print("    ","Authenticating using Auth-token from file",CLIARGS['authtokenfile'])
    elif "X_AUTH_TOKEN" in os.environ:              #Next: Check if an AuthToken is defined in the OS as X_AUTH_TOKEN
        CLOUDGENIX_AUTH_TOKEN = os.environ.get('X_AUTH_TOKEN')
        print("    ","Authenticating using environment variable X_AUTH_TOKEN")
    elif "AUTH_TOKEN" in os.environ:                #Next: Check if an AuthToken is defined in the OS as AUTH_TOKEN
        CLOUDGENIX_AUTH_TOKEN = os.environ.get('AUTH_TOKEN')
        print("    ","Authenticating using environment variable AUTH_TOKEN")
    else:                                           #Next: If we are not using an AUTH TOKEN, set it to NULL        
        CLOUDGENIX_AUTH_TOKEN = None
        print("    ","Authenticating using interactive login")
    ##ATTEMPT AUTHENTICATION
    if CLOUDGENIX_AUTH_TOKEN:
        sdk.interactive.use_token(CLOUDGENIX_AUTH_TOKEN)
        if sdk.tenant_id is None:
            print("    ","ERROR: AUTH_TOKEN login failure, please check token.")
            sys.exit()
    else:
        while sdk.tenant_id is None:
            sdk.interactive.login(user_email, user_password)
            # clear after one failed login, force relogin.
            if not sdk.tenant_id:
                user_email = None
                user_password = None            
    print("    ","SUCCESS: Authentication Complete")
    return sdk

def logout(sdk):
    print("Logging out")
    sdk.get.logout()


##########MAIN FUNCTION#############
def go(sdk, CLIARGS):

    ###Get list of service binding maps
    result = sdk.get.sites()
    if result.cgx_status is not True:
        sys.exit("API Error")

    site_list = result.cgx_content.get("items")

    new_anynet_links = []
    meshed_domains = []
    pmesh_topology = {}
    site_dict = {}
    for site in site_list:
        site_name   = site['name']
        site_id     = site['id']
        site_dict[site_id] = site
        if (site['tags'] is not None):
            for tag in site['tags']:
                domain = str(tag).replace("AUTO-MESH_","")
                if str(tag).startswith("AUTO-MESH_") and (len(str(tag)) > 11):# and (domain not in meshed_domains):
                    if domain not in pmesh_topology.keys():
                        pmesh_topology[domain] = []
                    pmesh_topology[domain].append(site_name + " (" + site_id + ")")
                    #Tag must start with AUTO-PMESH,    and have data after the prefix,   and we have not already considered this tag already (dont double-count peers)
                    
                    for sub_site in site_list:
                        
                        subsite_name = sub_site['name']
                        subsite_id = sub_site['id']
                        domain_hash = ''.join(sorted([site_id,subsite_id]))

                        tag_match = False
                        if (sub_site['tags'] is not None) and domain_hash not in meshed_domains:
                            for subsite_tag in sub_site['tags']:
                                if subsite_tag == tag:
                                    if subsite_id is not site_id:
                                        tag_match = True
                        if tag_match == True:
                            meshed_domains.append(domain_hash)
                            new_anynet_links.append({ 
                                                        "domain" : domain,
                                                        "site1": site_id,
                                                        "site1_name": site_name,
                                                        "site2": subsite_id,
                                                        "site2_name": subsite_name
                                                    }  )
    print("========= TOPOLOGY (Meshed Domains) =========")
    print(" ")
    for domain in pmesh_topology.keys():
        print("---- "+ domain + " ----")
        if len(pmesh_topology[domain]) == 0:
            print(" No site members found")
        else:
            count = 0
            for site in pmesh_topology[domain]:
                count += 1
                print( " " + str(count) + ") " + site)
        print(" ")
    if (len(new_anynet_links) == 0):
        print("No partial mesh domains found! Did you add a tag with the prefix 'AUTO-MESH_....' to the sites?")
        return False

    user_input = ""
    while str(user_input).lower() != "yes":
        print("This will create meshed domains consisting of the topology above")
        user_input = input("Proceed? (yes/no) ")
        if str(user_input).lower() == "no":
            return False

    wan_interface_dict = {}         
    for new_link in new_anynet_links:
        mesh_two_sites(new_link['site1'],new_link['site2'],sdk)


def mesh_two_sites(site1_id, site2_id, sdk):
    site1_wans = sdk.get.waninterfaces(site1_id).cgx_content.get("items", None)
    site2_wans = sdk.get.waninterfaces(site2_id).cgx_content.get("items", None)
    for left_wan in site1_wans:
        for right_wan in site2_wans:
            if left_wan['type'] == right_wan['type']: ##WANS must be of same type. I.E. PrivateWAN must connect to Private WAN's
                add_anynet_link(site1_id, left_wan['id'], site2_id, right_wan['id'], sdk  )
        

    
def add_anynet_link( site1, wan1, site2, wan2, sdk):
    ### This function adds a SecureFabric/Anynet link between two sites
    post_data = {'name': None, 'description': None, 'tags': None, 
                        'ep1_site_id': str(site1), 
                            'ep1_wan_if_id': str(wan1), 
                        'ep2_site_id': str(site2), 
                            'ep2_wan_if_id': wan2, 
                    'admin_up': True, 'forced': True, 'type': None}
    result = sdk.post.tenant_anynetlinks(post_data)
    if result.cgx_status == False:
        print("FAILURE:",result.cgx_errors)
    else:
        print("SUCCESS",site1,result.cgx_status)

    
if __name__ == "__main__":
    ###Get the CLI Arguments
    CLIARGS = parse_arguments()
    
    ###Authenticate
    SDK = authenticate(CLIARGS)
    
    ###Run Code
    go(SDK, CLIARGS)

    ###Exit Program
    logout(SDK)
