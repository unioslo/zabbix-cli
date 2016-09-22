Name: zabbix-cli		
Version: 1.5.4	
Release: 1%{?dist}
Summary: Command-line interface for Zabbix	
Group: System Environment/Base	
License: GPL	
URL: https://github.com/usit-gd/zabbix-cli	
Source0: https://github.com/usit-gd/zabbix-cli/archive/%{version}.tar.gz	
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root

BuildArch: noarch
BuildRequires: python-devel 
BuildRequires: python-setuptools 
Requires: python-requests	
%{?el6:Requires: python-argparse}

%description
Command-line interface for Zabbix monitoring system.

%prep
%setup -q

%build


%install
./setup.py install --root="%{buildroot}"


%files
%defattr(-, root, root, 0755)
%config(noreplace) /etc/zabbix-cli/zabbix-cli.conf
/usr/bin/zabbix-cli
/usr/bin/zabbix-cli-bulk-execution
/usr/bin/zabbix-cli-init
%{python_sitelib}/*



%changelog
* Thu Sep 22 2016 - Fabian Arrotin <arrfab@centos.org> - 1.5.4
- initial spec
