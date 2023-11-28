Name: zabbix-cli
Version: 2.3.2
Release: 1%{?dist}
Summary: Command-line interface for Zabbix

Group: System Environment/Base
License: GPLv3+
URL: https://github.com/unioslo/zabbix-cli
Source0: https://github.com/unioslo/zabbix-cli/archive/%{version}.tar.gz
BuildArch: noarch
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root

BuildRequires: python3-devel
BuildRequires: python3-setuptools

Provides: uio-zabbix-zabbixcli = %{version}-%{release}
Obsoletes: uio-zabbix-zabbixcli < 1.5.4-2

%if 0%{?rhel} == 7
Requires: python36-requests
Requires: python36-packaging
%else
%{?python_enable_dependency_generator}
%endif

%description
Command-line interface for Zabbix monitoring system.

%prep
%setup -q

%build
%py3_build

%install
%py3_install

%files
%{python3_sitelib}/zabbix_cli-*.egg-info/
%{python3_sitelib}/zabbix_cli/
%{_bindir}/zabbix-cli
%{_bindir}/zabbix-cli-bulk-execution
%{_bindir}/zabbix-cli-init
%dir %{_datadir}/zabbix-cli/
%{_datadir}/zabbix-cli/zabbix-cli.conf
%doc LICENSE

%changelog
* Mon Oct 17 2022 Peder Hovdan Andresen <pederhan@uio.no> - 2.3.2-1
- New version 2.3.2-1
- Zabbix 7.0 compatibility

* Mon Oct 17 2022 Marius Bakke <marius.bakke@usit.uio.no> - 2.3.1-1
- New version 2.3.1-1

* Tue Jun 21 2022 Marius Bakke <marius.bakke@usit.uio.no> - 2.3.0-1
- New version 2.3.0-1
- Zabbix 6 compatibility
- Documentation updates

* Thu Dec 19 2019 Paal Braathen <paal.braathen@usit.uio.no> - 2.2.1-1
- New version 2.2.1-1

* Wed Dec 04 2019 Paal Braathen <paal.braathen@usit.uio.no> - 2.2.0-1
- New version 2.2.0-1

* Wed Nov 20 2019 Paal Braathen <paal.braathen@usit.uio.no> - 2.1.1-3
- New release 2.1.1-3. Convert to python3 package.

* Mon Nov 11 2019 Paal Braathen <paal.braathen@usit.uio.no> - 2.1.1-2
- New release 2.1.1-2. Require python >= 2.7. Abandon RHEL6 and support RHEL8.

* Thu May 09 2019 Paal Braathen <paal.braathen@usit.uio.no> - 2.1.1-1
- New version 2.1.1

* Thu May 02 2019 Paal Braathen <paal.braathen@usit.uio.no> - 2.1.0-1
- New version 2.1.0

* Thu Feb 14 2019 Paal Braathen <paal.braathen@usit.uio.no> - 2.0.1-1
- New version 2.0.1

* Thu Feb 14 2019 Paal Braathen <paal.braathen@usit.uio.no> - 2.0.0-1
- New version 2.0.0

* Fri Jun 02 2017 Rafael Martinez Guerrero <r.m.guerrero@usit.uio.no> - 1.7.0-2
- New version 1.7.0-2. Requires python-ipaddr

* Fri May 19 2017 Rafael Martinez Guerrero <r.m.guerrero@usit.uio.no> - 1.7.0-1
- New version 1.7.0

* Mon Dec 12 2016 Rafael Martinez Guerrero <r.m.guerrero@usit.uio.no> - 1.6.1-1
- New version 1.6.1

* Tue Nov 22 2016 Rafael Martinez Guerrero <r.m.guerrero@usit.uio.no> - 1.6.0-1
- New version 1.6.0

* Sat Oct 29 2016 Volker Froehlich <volker27@gmx.at> - 1.5.4-5
- Match the actual license claimed in the code
- Remove -n from the setup macro, because it was the default
- Own the config directory
- Don't require setuptools
- Replace define with global
- Remove python2 from Requires, as it is probably installed anyway
  and is a dependency of the required modules anyway
- Add license file

* Fri Oct 14 2016 Rafael Martinez Guerrero <r.m.guerrero@usit.uio.no> - 1.5.4-4
- Merge internal UiO spec file with Fabians file

* Thu Oct 13 2016 Rafael Martinez Guerrero <r.m.guerrero@usit.uio.no> - 1.5.4-4
- Delete python-psycopg2 some required package

* Thu Sep 22 2016 - Fabian Arrotin <arrfab@centos.org> - 1.5.4
- initial spec

* Tue Sep 06 2016 Rafael Martinez Guerrero <r.m.guerrero@usit.uio.no> - 1.5.4-3
- Change package name to zabbix-cli. This package takes over uio-zabbix-zabbixcli

* Tue Jun 28 2016 Rafael Martinez Guerrero <r.m.guerrero@usit.uio.no> - 1.5.4
- New version 1.5.4

* Wed May 11 2016 Rafael Martinez Guerrero <r.m.guerrero@usit.uio.no> - 1.5.3
- New version 1.5.3

* Mon Apr 25 2016 Rafael Martinez Guerrero <r.m.guerrero@usit.uio.no> - 1.5.2
- New version 1.5.2

* Thu Apr 14 2016 Rafael Martinez Guerrero <r.m.guerrero@usit.uio.no> - 1.5.1
- New version 1.5.1

* Fri Apr 01 2016 Rafael Martinez Guerrero <r.m.guerrero@usit.uio.no> - 1.5.0
- New version 1.5.0

* Wed Nov 11 2015 Rafael Martinez Guerrero <r.m.guerrero@usit.uio.no> - 1.4.0
- Fix spec file for f23

* Thu Oct 22 2015 Rafael Martinez Guerrero <r.m.guerrero@usit.uio.no> - 1.4.0
- Ny version - 1.4.0

* Thu Aug 27 2015 Rafael Martinez Guerrero <r.m.guerrero@usit.uio.no> - 1.3.1
- Ny version - 1.3.1

* Thu Jun 18 2015 Rafael Martinez Guerrero <r.m.guerrero@usit.uio.no> - 1.3.0
- Ny version - 1.3.0

* Tue Apr 07 2015 Rafael Martinez Guerrero <r.m.guerrero@usit.uio.no> - 1.2.1
- Ny version - 1.2.1

* Wed Mar 25 2015 Rafael Martinez Guerrero <r.m.guerrero@usit.uio.no> - 1.2.0
- Endret til version 1.2.0

* Thu Mar 05 2015 Carl Morten Boger <c.m.boger@usit.uio.no> - 1.1.0
- Endret til version 1.1.0

* Fri Jan 30 2015 Carl Morten Boger <c.m.boger@usit.uio.no> - 1.0
- Initial version of the package
