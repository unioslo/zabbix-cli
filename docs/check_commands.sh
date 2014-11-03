#!/bin/sh

ZABBIX_CLI=/usr/bin/zabbix-cli

${ZABBIX_CLI} --use-json-format remove_hostgroup \"AAA-00\"
${ZABBIX_CLI} --use-json-format remove_hostgroup \"AAA-001\"

${ZABBIX_CLI} --use-json-format remove_host \"aaa.000001\"
${ZABBIX_CLI} --use-json-format remove_host \"aaa-001.uio.no\"
${ZABBIX_CLI} --use-json-format remove_host \"aaa-002.uio.no\"
${ZABBIX_CLI} --use-json-format remove_host \"aaa-003.uio.no\"
${ZABBIX_CLI} --use-json-format remove_host \"aaa-004.uio.no\"
${ZABBIX_CLI} --use-json-format remove_host \"aaa-005.uio.no\"
${ZABBIX_CLI} --use-json-format remove_host \"aaa-006.uio.no\"
${ZABBIX_CLI} --use-json-format remove_host \"aaa-007.uio.no\"
${ZABBIX_CLI} --use-json-format remove_host \"aaa-008.uio.no\"

${ZABBIX_CLI} --use-json-format create_hostgroup \"\"
${ZABBIX_CLI} --use-json-format create_hostgroup \"AAA-001\"
${ZABBIX_CLI} --use-json-format create_hostgroup \"AAA-002\"

${ZABBIX_CLI} --use-json-format create_host \"aaa-001.uio.no\" \"\" \"\" \"\"
${ZABBIX_CLI} --use-json-format create_host \"aaa-002.uio.no\" \"AAA-001\" \"\" \"\"
${ZABBIX_CLI} --use-json-format create_host \"aaa-003.uio.no\" \"AAA-0\" \"\" \"\"
${ZABBIX_CLI} --use-json-format create_host \"aaa-004.uio.no\" \"AAA-001\" \"*.uio.no\" \"\"
${ZABBIX_CLI} --use-json-format create_host \"aaa-005.uio.no\" \"AAA-001\" \"*.xxxx\" \"\"
${ZABBIX_CLI} --use-json-format create_host \"aaa-006.uio.no\" \"AAA-001\" \"*.uio.no\" \"0\"
${ZABBIX_CLI} --use-json-format create_host \"aaa-007.uio.no\" \"AAA-001\" \"*.uio.no\" \"1\"
${ZABBIX_CLI} --use-json-format create_host \"aaa-008.uio.no\" \"AAA-001\" \"*.uio.no\" \"10\"

${ZABBIX_CLI} --use-json-format add_host_to_hostgroup \" aaa-001.uio.no , aaa-002.uio.no \" \" AAA-001, AAA-002 \"
${ZABBIX_CLI} --use-json-format add_host_to_hostgroup \" aaa-001.uio.no , aaa-002.uio.no \" \" AAA-001, AAA-002, AAA-0000000 \"
${ZABBIX_CLI} --use-json-format add_host_to_hostgroup \" aaa-001.uio.no , aaa-002222222.uio.no \" \"AAA-001, AAA-002 \"

${ZABBIX_CLI} --use-json-format link_template_to_host \" Template AAA-0 \" \"  aaa-001.uio.no , aaa-002.uio.no  \"
${ZABBIX_CLI} --use-json-format link_template_to_host \" Template AAA-001 \" \"  aaa-0011111.uio.no , aaa-002.uio.no  \"

${ZABBIX_CLI} --use-json-format link_template_to_host \" Template AAA-001 , Template AAA-002 \" \"  aaa-001.uio.no , aaa-002.uio.no  \"

${ZABBIX_CLI} --use-json-format unlink_template_from_host \" Template AAA-0 \" \"  aaa-001.uio.no , aaa-002.uio.no  \"
${ZABBIX_CLI} --use-json-format unlink_template_from_host \" Template AAA-001 \" \"  aaa-0011111.uio.no , aaa-002.uio.no  \"

${ZABBIX_CLI} --use-json-format unlink_template_from_host \" Template AAA-001 , Template AAA-002\" \"  aaa-001.uio.no , aaa-002.uio.no  \"








