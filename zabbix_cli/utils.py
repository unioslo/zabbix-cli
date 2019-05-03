"""Utility functions."""


def get_ack_status(code):
    """Get ack status from code."""
    ack_status = {0: "No", 1: "Yes"}

    if code in ack_status:
        return ack_status[code] + " (" + str(code) + ")"

    return "Unknown ({})".format(str(code))


def get_event_status(code):
    """Get event status from code."""
    event_status = {0: "OK", 1: "Problem"}

    if code in event_status:
        return event_status[code] + " (" + str(code) + ")"

    return "Unknown ({})".format(str(code))


def get_trigger_severity(code):
    """Get trigger severity from code."""
    trigger_severity = {0: "Not classified", 1: "Information", 2: "Warning", 3: "Average", 4: "High", 5: "Disaster"}

    if code in trigger_severity:
        return trigger_severity[code]

    return "Unknown ({})".format(str(code))


def get_trigger_status(code):
    """Get trigger status from code."""
    trigger_status = {0: "Enable", 1: "Disable"}

    if code in trigger_status:
        return trigger_status[code] + " (" + str(code) + ")"

    return "Unknown ({})".format(str(code))


def get_maintenance_status(code):
    """Get maintenance status from code."""
    maintenance_status = {0: "No maintenance", 1: "In progress"}

    if code in maintenance_status:
        return maintenance_status[code] + " (" + str(code) + ")"

    return "Unknown ({})".format(str(code))


def get_monitoring_status(code):
    """Get monitoring status from code."""
    monitoring_status = {0: "Monitored", 1: "Not monitored"}

    if code in monitoring_status:
        return monitoring_status[code] + " (" + str(code) + ")"

    return "Unknown ({})".format(str(code))


def get_zabbix_agent_status(code):
    """Get zabbix agent status from code."""
    zabbix_agent_status = {1: "Available", 2: "Unavailable"}

    if code in zabbix_agent_status:
        return zabbix_agent_status[code] + " (" + str(code) + ")"

    return "Unknown ({})".format(str(code))


def get_gui_access(code):
    """Get GUI access from code."""
    gui_access = {0: "System default", 1: "Internal", 2: "Disable"}

    if code in gui_access:
        return gui_access[code] + " (" + str(code) + ")"

    return "Unknown ({})".format(str(code))


def get_usergroup_status(code):
    """Get usergroup status from code."""
    usergroup_status = {0: "Enable", 1: "Disable"}

    if code in usergroup_status:
        return usergroup_status[code] + " (" + str(code) + ")"

    return "Unknown ({})".format(str(code))


def get_hostgroup_flag(code):
    """Get hostgroup flag from code."""
    hostgroup_flag = {0: "Plain", 4: "Discover"}

    if code in hostgroup_flag:
        return hostgroup_flag[code] + " (" + str(code) + ")"

    return "Unknown ({})".format(str(code))


def get_hostgroup_type(code):
    """Get hostgroup type from code."""
    hostgroup_type = {0: "Not internal", 1: "Internal"}

    if code in hostgroup_type:
        return hostgroup_type[code] + " (" + str(code) + ")"

    return "Unknown ({})".format(str(code))


def get_user_type(code):
    """Get user type from code."""
    user_type = {1: "User", 2: "Admin", 3: "Super admin"}

    if code in user_type:
        return user_type[code] + " (" + str(code) + ")"

    return "Unknown ({})".format(str(code))


def get_maintenance_type(code):
    """Get maintenance type from code."""
    maintenance_type = {0: "With DC", 1: "Without DC"}

    if code in maintenance_type:
        return maintenance_type[code] + " (" + str(code) + ")"

    return "Unknown ({})".format(str(code))


def get_maintenance_period_type(code):
    """Get maintenance period type from code."""
    maintenance_period_type = {0: "One time", 2: "Daily", 3: "Weekly", 4: "Monthly"}

    if code in maintenance_period_type:
        return maintenance_period_type[code] + " (" + str(code) + ")"

    return "Unknown ({})".format(str(code))


def get_autologin_type(code):
    """Get autologin type from code."""
    autologin_type = {0: "Disable", 1: "Enable"}

    if code in autologin_type:
        return autologin_type[code] + " (" + str(code) + ")"

    return "Unknown ({})".format(str(code))


def get_permission(code):
    """Get permission."""
    permission = {
        0: "deny",
        2: "ro",
        3: "rw"
    }

    return permission.get(code, None)


def get_permission_code(permission):
    """Get permission code."""
    permission_code = {"deny": 0, "ro": 2, "rw": 3}

    if permission in permission_code:
        return permission_code[permission]

    return 0


def get_item_type(code):
    """Get item type from code."""
    item_type = {0: "Zabbix agent",
                 1: "SNMPv1 agent",
                 2: "Zabbix trapper",
                 3: "simple check",
                 4: "SNMPv2 agent",
                 5: "Zabbix internal",
                 6: "SNMPv3 agent",
                 7: "Zabbix agent (active)",
                 8: "Zabbix aggregate",
                 9: "web item",
                 10: "external check",
                 11: "database monitor",
                 12: "IPMI agent",
                 13: "SSH agent",
                 14: "TELNET agent",
                 15: "calculated",
                 16: "JMX agent",
                 17: "SNMP trap"}

    if code in item_type:
        return item_type[code] + " (" + str(code) + ")"

    return "Unknown ({})".format(str(code))
