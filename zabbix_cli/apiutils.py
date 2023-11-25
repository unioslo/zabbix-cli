"""All functions in this module extend or simplifies common API tasks."""
from packaging.version import Version

def update_usergroup(zapi, usrgrpid, rights=None, userids=None):
    """
    Merge update a usergroup.

    Updating usergroups without replacing current state (i.e. merge update) is hard.
    This function simplifies the process.

    The rights and userids provided are merged into the usergroup.
    """
    usrgrpid = str(usrgrpid)  # Make sure this number is a string
    usergroup = zapi.usergroup.get(filter={"usrgrpid": usrgrpid}, selectRights=["permission", "id"], selectUsers=["userid"])[0]

    if rights:
        # Get the current rights with ids from new rights filtered
        new_rights = [current_right for current_right in usergroup["rights"] if current_right["id"] not in [right["id"] for right in rights]]

        new_rights.extend(rights)

        return zapi.usergroup.update(usrgrpid=usrgrpid, rights=new_rights)

    if userids:
        current_userids = [user["userid"] for user in usergroup["users"]]

        # Make sure we only have unique ids
        new_userids = list(set(current_userids + userids))

        return zapi.usergroup.update(usrgrpid=usrgrpid, userids=new_userids)

    return None

# TODO (pederhan): rewrite these functions as some sort of declarative data
# structure that can be used to determine correct parameters based on version
# if we end up with a lot of these functions. For now, this is fine.

def proxyname_by_version(version: Version) -> str:
    if version.release < (7, 0, 0):
        return "host"
    return "name" # defaults to new parameter name


def username_by_version(version: Version) -> str:
    """Returns the correct username parameter based on Zabbix version."""
    if version.release < (5, 4, 0):
        return 'user'
    return 'username' # defaults to new parameter name