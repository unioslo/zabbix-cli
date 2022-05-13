/*

Sphinx works great for API documentation, but we want to document just the
commands in cli.py without the "do_" prefix from the method names, which can
not be manipulated by the regular Sphinx hooks.

It is kind-of possible with pure CSS along these lines:

.sig-name.descname {
    position: relative;
}

.sig-name.descname::before  {
    content: "do_";
    position: absolute;
    background-color: white;
    color: transparent;
}

...which works in jsfiddle, but not necessarily in browsers with all the extras
provided by Sphinx.  Thus we resort to JavaScript for consistent results.
*/

document.addEventListener("DOMContentLoaded", function() {
    const elements = document.querySelectorAll('[id^="zabbix_cli.cli.zabbixcli.do_"]');

    elements.forEach(item => {
        const pre = item.getElementsByClassName("pre");
        for (const c of pre) {
            const replacement = c.innerText.replace(/^do_/, "");
            c.innerText = replacement;
        };
    });
});
