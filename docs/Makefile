#
# Makefile
#

VERSION="1.7.0"

all:	html man pdf

html:	
	rst2html -gdt --stylesheet-path=style.css manual.rst > zabbix-cli-manual-$(VERSION).html

man:
	rst2man manual.rst > zabbix-cli-manual-$(VERSION).man

pdf:
	cat manual.rst | sed s/":scale: 50%"/":scale: 100%"/g > manual.tmp
	rst2pdf --output zabbix-cli-manual-$(VERSION).pdf manual.tmp
	rm -f manual.tmp

clean:
	rm -f zabbix-cli-manual-$(VERSION)*.html
	rm -f zabbix-cli-manual-$(VERSION)*.man
	rm -f zabbix-cli-manual-$(VERSION)*.pdf
	rm -f *~
