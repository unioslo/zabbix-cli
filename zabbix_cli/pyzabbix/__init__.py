"""This module is based on PyZabbix (https://github.com/lukecyca/pyzabbix),
which is licensed under the GNU Lesser General Public License (LGPL) according
to its PyPI metadata.

It is unclear which version of PyZabbix was vendored into Zabbix-CLI originally,
but we can assume it's not a version later than 0.7.4, which was the last version
available on PyPI before the majority of the code was vendored, as evidenced by
this git blame: https://github.com/unioslo/zabbix-cli/blame/2.3.2/zabbix_cli/pyzabbix.py

We assume that the copyright years of the original PyZabbix code are from 2013-2015
for that reason. The source code repository contains no LICENSE file, even
though its metadata states that it is LGPL-licensed.

An abbreviated version of the LGPL-3.0 license text is included below:

    Copyright (C) 2013-2015 PyZabbix Contributors
    Modified work Copyright (C) 2022-2024 University of Oslo

    This library is free software: you can redistribute it and/or modify
    it under the terms of the GNU Lesser General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This library is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU Lesser General Public License for more details.

    You should have received a copy of the GNU Lesser General Public License
    along with this library. If not, see <https://www.gnu.org/licenses/>.

Additional Notices:
- This code was originally vendored by Zabbix-CLI from PyZabbix
- Modifications have been made to the original PyZabbix code to adapt it
  for use in this project. It is _very_ different, and it's unclear if
  we should even call it PyZabbix anymore. It's more like a fork.
- The original source code can be found at: https://github.com/lukecyca/pyzabbix
"""

from __future__ import annotations
