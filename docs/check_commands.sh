#!/bin/sh

ZABBIX_CLI=/usr/bin/zabbix-cli

#${ZABBIX_CLI} --use-json-format remove_hostgroup \"AAA-00\"
#${ZABBIX_CLI} --use-json-format remove_hostgroup \"AAA-001\"

# return: error
${ZABBIX_CLI} --use-json-format remove_host \"aaa.000001\"

RETVAL=$?
if [ $RETVAL -eq 1 ]; then
    echo -e  "TEST 1: OK\n"
else
    echo -e  "TEST 1: ERROR\n"
fi

# return: error
${ZABBIX_CLI} --use-json-format create_hostgroup \"\"

RETVAL=$?
if [ $RETVAL -eq 1 ]; then
    echo -e  "TEST 2: OK\n"
else
    echo -e  "TEST 2: ERROR\n"
fi

# return:ok
${ZABBIX_CLI} --use-json-format create_hostgroup \"AAA-001\"

RETVAL=$?
if [ $RETVAL -eq 0 ]; then
    echo -e  "TEST 3: OK\n"
else
    echo -e  "TEST 3: ERROR\n"
fi

# return: ok
${ZABBIX_CLI} --use-json-format create_hostgroup \"AAA-002\"

RETVAL=$?
if [ $RETVAL -eq 0 ]; then
    echo -e  "TEST 4: OK\n"
else
    echo -e  "TEST 4: ERROR\n"
fi

# return: ok 
${ZABBIX_CLI} --use-json-format create_host \"aaa-001.uio.no\" \"\" \"\" \"\"

RETVAL=$?
if [ $RETVAL -eq 0 ]; then
    echo -e  "TEST 5: OK\n"
else
    echo -e  "TEST 5: ERROR\n"
fi


# return: ok
${ZABBIX_CLI} --use-json-format remove_host \"aaa-001.uio.no\"

RETVAL=$?
if [ $RETVAL -eq 0 ]; then
    echo -e  "TEST 6: OK\n"
else
    echo -e  "TEST 6: ERROR\n"
fi

# return: ok
${ZABBIX_CLI} --use-json-format create_host \"aaa-001.uio.no\" \"AAA-001\" \"\" \"\"

RETVAL=$?
if [ $RETVAL -eq 0 ]; then
    echo -e  "TEST 7: OK\n"
else
    echo -e  "TEST 7: ERROR\n"
fi

# return: ok
${ZABBIX_CLI} --use-json-format remove_host \"aaa-001.uio.no\"

RETVAL=$?
if [ $RETVAL -eq 0 ]; then
    echo -e  "TEST 8: OK\n"
else
    echo -e  "TEST 8: ERROR\n"
fi

# return: error
${ZABBIX_CLI} --use-json-format create_host \"aaa-001.uio.no\" \"AAA-0\" \"\" \"\"

RETVAL=$?
if [ $RETVAL -eq 1 ]; then
    echo -e  "TEST 9: OK\n"
else
    echo -e  "TEST 9: ERROR\n"
fi

# return: error
${ZABBIX_CLI} --use-json-format remove_host \"aaa-001.uio.no\"

RETVAL=$?
if [ $RETVAL -eq 1 ]; then
    echo -e  "TEST 10: OK\n"
else
    echo -e  "TEST 10: ERROR\n"
fi

# return: ok
${ZABBIX_CLI} --use-json-format create_host \"aaa-001.uio.no\" \"AAA-001\" \"*.uio.no\" \"\"

RETVAL=$?
if [ $RETVAL -eq 0 ]; then
    echo -e  "TEST 11: OK\n"
else
    echo -e  "TEST 11: ERROR\n"
fi

# return: ok
${ZABBIX_CLI} --use-json-format remove_host \"aaa-001.uio.no\"

RETVAL=$?
if [ $RETVAL -eq 0 ]; then
    echo -e  "TEST 12: OK\n"
else
    echo -e  "TEST 12: ERROR\n"
fi


# return: error
${ZABBIX_CLI} --use-json-format create_host \"aaa-001.uio.no\" \"AAA-001\" \"*.xxxx\" \"\"

RETVAL=$?
if [ $RETVAL -eq 1 ]; then
    echo -e  "TEST 13: OK\n"
else
    echo -e  "TEST 13: ERROR\n"
fi


# return: error
${ZABBIX_CLI} --use-json-format remove_host \"aaa-001.uio.no\"

RETVAL=$?
if [ $RETVAL -eq 1 ]; then
    echo -e  "TEST 14: OK\n"
else
    echo -e  "TEST 14: ERROR\n"
fi


# return: ok
${ZABBIX_CLI} --use-json-format create_host \"aaa-001.uio.no\" \"AAA-001\" \"*.uio.no\" \"0\"

RETVAL=$?
if [ $RETVAL -eq 0 ]; then
    echo -e  "TEST 15: OK\n"
else
    echo -e  "TEST 15: ERROR\n"
fi

# return: ok
${ZABBIX_CLI} --use-json-format remove_host \"aaa-001.uio.no\"

RETVAL=$?
if [ $RETVAL -eq 0 ]; then
    echo -e  "TEST 16: OK\n"
else
    echo -e  "TEST 16: ERROR\n"
fi

# return: ok
${ZABBIX_CLI} --use-json-format create_host \"aaa-001.uio.no\" \"AAA-001\" \"*.uio.no\" \"1\"

RETVAL=$?
if [ $RETVAL -eq 0 ]; then
    echo -e  "TEST 17: OK\n"
else
    echo -e  "TEST 17: ERROR\n"
fi

# return: ok
${ZABBIX_CLI} --use-json-format remove_host \"aaa-001.uio.no\"

RETVAL=$?
if [ $RETVAL -eq 0 ]; then
    echo -e  "TEST 18: OK\n"
else
    echo -e  "TEST 18: ERROR\n"
fi

# return: ok
${ZABBIX_CLI} --use-json-format create_host \"aaa-001.uio.no\" \"AAA-001\" \"*.uio.no\" \"10\"

RETVAL=$?
if [ $RETVAL -eq 0 ]; then
    echo -e  "TEST 19: OK\n"
else
    echo -e  "TEST 19: ERROR\n"
fi

# return: ok
${ZABBIX_CLI} --use-json-format remove_host \"aaa-001.uio.no\"

RETVAL=$?
if [ $RETVAL -eq 0 ]; then
    echo -e  "TEST 20: OK\n"
else
    echo -e  "TEST 20: ERROR\n"
fi

# return: ok
${ZABBIX_CLI} --use-json-format create_host \"aaa-001.uio.no\" \"AAA-001\" \"\" \"\"

RETVAL=$?
if [ $RETVAL -eq 0 ]; then
    echo -e  "TEST 21: OK\n"
else
    echo -e  "TEST 21: ERROR\n"
fi

# return: ok
${ZABBIX_CLI} --use-json-format create_host \"aaa-002.uio.no\" \"AAA-001\" \"\" \"\"

RETVAL=$?
if [ $RETVAL -eq 0 ]; then
    echo -e  "TEST 22: OK\n"
else
    echo -e  "TEST 22: ERROR\n"
fi


# return: ok
${ZABBIX_CLI} --use-json-format add_host_to_hostgroup \" aaa-001.uio.no , aaa-002.uio.no \" \" AAA-001, AAA-002 \"

RETVAL=$?
if [ $RETVAL -eq 0 ]; then
    echo -e  "TEST 23: OK\n"
else
    echo -e  "TEST 23: ERROR\n"
fi

# return: error
${ZABBIX_CLI} --use-json-format add_host_to_hostgroup \" aaa-001.uio.no , aaa-002.uio.no \" \" AAA-001, AAA-002, AAA-0000000 \"

RETVAL=$?
if [ $RETVAL -eq 1 ]; then
    echo -e  "TEST 24: OK\n"
else
    echo -e  "TEST 24: ERROR\n"
fi

# return: error
${ZABBIX_CLI} --use-json-format add_host_to_hostgroup \" aaa-001.uio.no , aaa-002222222.uio.no \" \"AAA-001, AAA-002 \"

RETVAL=$?
if [ $RETVAL -eq 1 ]; then
    echo -e  "TEST 25: OK\n"
else
    echo -e  "TEST 25: ERROR\n"
fi

# return: error
${ZABBIX_CLI} --use-json-format link_template_to_host \" Template AAA-0 \" \"  aaa-001.uio.no , aaa-002.uio.no  \"

RETVAL=$?
if [ $RETVAL -eq 1 ]; then
    echo -e  "TEST 26: OK\n"
else
    echo -e  "TEST 26: ERROR\n"
fi

# return: error
${ZABBIX_CLI} --use-json-format link_template_to_host \" Template AAA-001 \" \"  aaa-0011111.uio.no , aaa-002.uio.no  \"

RETVAL=$?
if [ $RETVAL -eq 1 ]; then
    echo -e  "TEST 27: OK\n"
else
    echo -e  "TEST 27: ERROR\n"
fi

# return: ok
${ZABBIX_CLI} --use-json-format link_template_to_host \" Template AAA-001 , Template AAA-002 \" \"  aaa-001.uio.no , aaa-002.uio.no  \"

RETVAL=$?
if [ $RETVAL -eq 0 ]; then
    echo -e  "TEST 28: OK\n"
else
    echo -e  "TEST 28: ERROR\n"
fi

# return: error
${ZABBIX_CLI} --use-json-format unlink_template_from_host \" Template AAA-0 \" \"  aaa-001.uio.no , aaa-002.uio.no  \"

RETVAL=$?
if [ $RETVAL -eq 1 ]; then
    echo -e  "TEST 29: OK\n"
else
    echo -e  "TEST 29: ERROR\n"
fi

# return error
${ZABBIX_CLI} --use-json-format unlink_template_from_host \" Template AAA-001 \" \"  aaa-0011111.uio.no , aaa-002.uio.no  \"

RETVAL=$?
if [ $RETVAL -eq 1 ]; then
    echo -e  "TEST 30: OK\n"
else
    echo -e  "TEST 30: ERROR\n"
fi

# return: ok
${ZABBIX_CLI} --use-json-format unlink_template_from_host \" Template AAA-001 , Template AAA-002\" \"  aaa-001.uio.no , aaa-002.uio.no  \"

RETVAL=$?
if [ $RETVAL -eq 0 ]; then
    echo -e  "TEST 31: OK\n"
else
    echo -e  "TEST 31: ERROR\n"
fi

# return: error
${ZABBIX_CLI} --use-json-format remove_host_from_hostgroup \" aaa-001.uio.no , aaa-002222222.uio.no \" \"AAA-001, AAA-002 \"

RETVAL=$?
if [ $RETVAL -eq 1 ]; then
    echo -e  "TEST 32: OK\n"
else
    echo -e  "TEST 32: ERROR\n"
fi

# return: error
${ZABBIX_CLI} --use-json-format remove_host_from_hostgroup \" aaa-001.uio.no , aaa-002.uio.no \" \" AAA-001, AAA-002, AAA-0000000 \"

RETVAL=$?
if [ $RETVAL -eq 1 ]; then
    echo -e  "TEST 33: OK\n"
else
    echo -e  "TEST 33: ERROR\n"
fi

# return: ok
${ZABBIX_CLI} --use-json-format remove_host_from_hostgroup \" aaa-001.uio.no , aaa-002.uio.no \" \" AAA-001, AAA-002 \"

RETVAL=$?
if [ $RETVAL -eq 0 ]; then
    echo -e  "TEST 34: OK\n"
else
    echo -e  "TEST 34: ERROR\n"
fi


# return: ok
${ZABBIX_CLI} --use-json-format remove_host \"aaa-001.uio.no\"

RETVAL=$?
if [ $RETVAL -eq 0 ]; then
    echo -e  "TEST 35: OK\n"
else
    echo -e  "TEST 35: ERROR\n"
fi

# return: ok
${ZABBIX_CLI} --use-json-format remove_host \"aaa-002.uio.no\"

RETVAL=$?
if [ $RETVAL -eq 0 ]; then
    echo -e  "TEST 36: OK\n"
else
    echo -e  "TEST 36: ERROR\n"
fi


# return: error
${ZABBIX_CLI} --use-json-format create_usergroup \"\" \"\"

RETVAL=$?
if [ $RETVAL -eq 1 ]; then
    echo -e  "TEST 37: OK\n"
else
    echo -e  "TEST 37: ERROR\n"
fi


# return: ok
${ZABBIX_CLI} --use-json-format create_usergroup \"AAA-usergroup\" \"\" \"\"

RETVAL=$?
if [ $RETVAL -eq 0 ]; then
    echo -e  "TEST 38: OK\n"
else
    echo -e  "TEST 38: ERROR\n"
fi

# return: ok
${ZABBIX_CLI} --use-json-format create_usergroup \"BBB-usergroup\" \"0\" \"0\"

RETVAL=$?
if [ $RETVAL -eq 0 ]; then
    echo -e  "TEST 39: OK\n"
else
    echo -e  "TEST 39: ERROR\n"
fi

# return: ok
${ZABBIX_CLI} --use-json-format create_user \"AAA-user\" \"AAA\" \"user\" \"\" \"\" \"\" \"\" \"13\" 

RETVAL=$?
if [ $RETVAL -eq 0 ]; then
    echo -e  "TEST 40: OK\n"
else
    echo -e  "TEST 40: ERROR\n"
fi

# return: ok
${ZABBIX_CLI} --use-json-format create_user \"BBB-user\" \"BBB\" \"user\" \"\" \"\" \"\" \"\" \"13\" 

RETVAL=$?
if [ $RETVAL -eq 0 ]; then
    echo -e  "TEST 41: OK\n"
else
    echo -e  "TEST 41: ERROR\n"
fi

# return: ok
${ZABBIX_CLI} --use-json-format create_user \"AAA-user\" \"AAA\" \"user\" \"\" \"\" \"\" \"\" \"13\" 

RETVAL=$?
if [ $RETVAL -eq 0 ]; then
    echo -e  "TEST 42: OK\n"
else
    echo -e  "TEST 42: ERROR\n"
fi


# return: error
${ZABBIX_CLI} --use-json-format add_user_to_usergroup \"\" \"AAA-usergroup, BBB-usergroup\"

RETVAL=$?
if [ $RETVAL -eq 1 ]; then
    echo -e  "TEST 43: OK\n"
else
    echo -e  "TEST 43: ERROR\n"
fi

# return: error
${ZABBIX_CLI} --use-json-format add_user_to_usergroup \"AAA-user\" \"\"

RETVAL=$?
if [ $RETVAL -eq 1 ]; then
    echo -e  "TEST 44: OK\n"
else
    echo -e  "TEST 44: ERROR\n"
fi

# return: error
${ZABBIX_CLI} --use-json-format add_user_to_usergroup \"AAA-user\" \"asdsad\"

RETVAL=$?
if [ $RETVAL -eq 1 ]; then
    echo -e  "TEST 45: OK\n"
else
    echo -e  "TEST 45: ERROR\n"
fi

# return: ok
${ZABBIX_CLI} --use-json-format add_user_to_usergroup \"AAA-user, BBB-user \" \"AAA-usergroup, BBB-usergroup\"

RETVAL=$?
if [ $RETVAL -eq 0 ]; then
    echo -e  "TEST 46: OK\n"
else
    echo -e  "TEST 46: ERROR\n"
fi

