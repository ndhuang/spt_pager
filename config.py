'''
Configuration options for the pager.  See pager_server.py and pager_client.py
for documentation.
'''

##########################################################################
# Network options
server_host = 'localhost'
server_port = 1027
server_timeout = 10
client_timeout = 5

##########################################################################
# Pager control options
pager_interval = 30
watchdog_timeout = 15

##########################################################################
# Internal configuration.  In general, these do not need to be changed.
failure_msg = 'FAIL'
