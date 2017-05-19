%if 0%{?rhel} && 0%{?rhel} == 6
%{!?__python2: %global __python2 /usr/bin/python2}
%{!?python2_sitelib: %global python2_sitelib %(%{__python2} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%{!?python2_sitearch: %global python2_sitearch %(%{__python2} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib(1))")}
%endif
%{!?pybasever: %global pybasever %(%{__python2} -c "import sys;print(sys.version[0:3])")}

Name: zabbix-cli
Version: 1.7.0
Release: 1%{?dist}
Summary: Command-line interface for Zabbix

Group: System Environment/Base
License: GPLv3+
URL: https://github.com/usit-gd/zabbix-cli
Source0: https://github.com/usit-gd/zabbix-cli/archive/%{version}.tar.gz

BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root

Requires: python-argparse, python-requests, python-ipaddr
BuildRequires: python2-devel, python-setuptools
BuildArch: noarch

%description
Command-line interface for Zabbix monitoring system.

%prep
%setup -q

%build
%{__python2} setup.py build

%install
%{__python2} setup.py install -O1 --skip-build --root %{buildroot}
mkdir -p %{buildroot}%{_defaultdocdir}/zabbix-cli-%{version}

%files
%defattr(-, root, root, 0755)
%{python2_sitelib}/zabbix_cli-%{version}-py%{pybasever}.egg-info/
%{python2_sitelib}/zabbix_cli/
%{_bindir}/zabbix-cli*
%dir %{_datadir}/zabbix-cli/
%dir %{_defaultdocdir}/zabbix-cli-%{version}
%{_datadir}/zabbix-cli/zabbix-cli.conf
%doc LICENSE docs/manual.rst

%changelog
* Fri May 19 2017 Rafael Martinez Guerrero <r.m.guerrero@usit.uio.no> - 1.7.0-1
- New version 1.7.0

* Mon Dec 12 2016 Rafael Martinez Guerrero <r.m.guerrero@usit.uio.no> - 1.6.1-1
- New version 1.6.1

* Wed Nov 30 2016 Rafael Martinez Guerrero <r.m.guerrero@usit.uio.no> - 1.6.0-1
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

* Thu Sep 22 2016 - Fabian Arrotin <arrfab@centos.org> - 1.5.4
- initial spec
