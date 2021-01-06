# cg-partial-mesh-tool
Creates partial mesh domains with site tags


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
