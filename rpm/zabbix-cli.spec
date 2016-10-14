%if 0%{?rhel} && 0%{?rhel} <= 6
%{!?__python2: %global __python2 /usr/bin/python2}
%{!?python2_sitelib: %global python2_sitelib %(%{__python2} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%{!?python2_sitearch: %global python2_sitearch %(%{__python2} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib(1))")}
%endif
%{!?pybasever: %define pybasever %(%{__python2} -c "import sys;print(sys.version[0:3])")}

Name: zabbix-cli		
Version: 1.5.4	
Release: 4%{?dist}
Summary: Command-line interface for Zabbix	

Group: System Environment/Base	
License: GPLv3	
URL: https://github.com/usit-gd/zabbix-cli	
Source0: https://github.com/usit-gd/zabbix-cli/archive/%{version}.tar.gz	

BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root

Requires:	python2, python-setuptools, python-argparse, python-requests
BuildRequires:	python2-devel, python-setuptools
BuildArch:      noarch

%description
Command-line interface for Zabbix monitoring system.

%prep
%setup -n zabbix-cli-%{version} -q

%build		
%{__python2} setup.py build

%install
%{__python2} setup.py install -O1 --skip-build --root %{buildroot}

%files
%defattr(-, root, root, 0755)
%{python2_sitelib}/zabbix_cli-%{version}-py%{pybasever}.egg-info/
%{python2_sitelib}/zabbix_cli/
%{_bindir}/zabbix-cli*
%config(noreplace) %{_sysconfdir}/zabbix-cli/zabbix-cli.conf

%changelog
* Fri Oct 14 2016 Rafael Martinez Guerrero <r.m.guerrero@usit.uio.no> - 1.5.4-4
- Merge internal UiO spec file with Fabians file 

* Thu Sep 22 2016 - Fabian Arrotin <arrfab@centos.org> - 1.5.4
- initial spec
