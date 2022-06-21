# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.

import os
import sys
import re

# Add the parent directory on PYTHONPATH.
sys.path.insert(0, os.path.abspath('..'))


# -- Project information -----------------------------------------------------

project = 'zabbix-cli'
copyright = '2022, University of Oslo'
author = 'University of Oslo'

# The full version, including alpha/beta/rc tags
release = '2.3.0'


# -- General configuration ---------------------------------------------------

root_doc = "manual"

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'alabaster'

html_theme_options = {
    "nosidebar": True,
}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

html_css_files = [
    'css/manual.css',
]

html_js_files = [
    'js/manual.js',
]

# -- Extension configuration -------------------------------------------------

# Select only members with "do_" prefix.
def autodoc_skip_member_handler(app, what, name, obj, skip, options):
    return not name.startswith("do_")

# Hide the Python function signature description.
def autodoc_process_signature_handler(app, what, name, obj, options, signature, return_annotation):
    return "", None

def autodoc_process_docstring_handler(app, what, name, obj, options, lines):
    """
    Remove all DESCRIPTION.
    Change all COMMAND: to be rendered as code blocks.
    Sections don't work in docstrings, so change them to .. rubric::.
    """
    new_lines = []
    for idx in range(len(lines)):
        line = lines[idx]
        desc = re.match("^DESCRIPTION:?(.+)?", line)
        if desc:
            if desc[1] is not None:
                # Take 'foo' from 'DESCRIPTION: foo'.
                new_lines.append(desc[1])
            continue
        command = re.match("^COMMAND:(.+)?$", line)
        if command:
            new_lines.append("::")
            new_lines.append("")
            # Handle 'COMMAND: foo [bar]'.
            if command[1] is not None:
                new_lines.append("  " + command[1])
            # Modify the next items ahead of time.  We need to figure out
            # how many arguments (if any), and indent each line.
            lines_to_indent = 0
            for i in range(idx + 1, len(lines)):
                # Stop at the first empty line
                next_line = lines[i]
                if len(next_line) > 0:
                    lines_to_indent += 1
                else:
                    break
            for i in range(lines_to_indent):
                lines[idx+1+i] = "  " + lines[idx+1+i]
            continue
        section = re.match("^-+$", line)
        if section:
            # For sections, remove the --- markers and instead add
            # .. rubric:: to the previous line, plus a blank line.
            old = new_lines[-1]
            new = ".. rubric:: " + old
            new_lines[-1] = new
            new_lines.append("")
            continue
        new_lines.append(line)

    lines.clear()
    lines += new_lines

def setup(app):
    app.connect('autodoc-process-docstring', autodoc_process_docstring_handler)
    app.connect('autodoc-process-signature', autodoc_process_signature_handler)
    app.connect('autodoc-skip-member', autodoc_skip_member_handler)
