import ldap3

def login(domain, username, password):
    # content on the form "SEDC19~DC=company,DC=com"
    machine,base = open('conf/ldap-%s.data'%domain).read().strip().split('~')
    server = ldap3.Server(machine)
    connection = ldap3.Connection(server, user=username, password=password)
    assert connection.bind()
    connection.search(search_base=base, search_filter='(&(objectClass=user)(userPrincipalName='+username+'))', search_scope='SUBTREE', attributes='*')
    attrs = connection.response[0]['attributes']
    return attrs['displayName'], attrs['memberOf']
