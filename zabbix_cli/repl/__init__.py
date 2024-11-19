"""This module is based on click-repl (https://github.com/click-contrib/click-repl) @ f08ba39

Click-repl is licensed under the MIT license and has the following copyright notices:
    Copyright (c) 2014-2015 Markus Unterwaditzer & contributors.
    Copyright (c) 2016-2026 Asif Saif Uddin & contributors.

    Permission is hereby granted, free of charge, to any person obtaining a copy of
    this software and associated documentation files (the "Software"), to deal in
    the Software without restriction, including without limitation the rights to
    use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
    of the Software, and to permit persons to whom the Software is furnished to do
    so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.

The module uses the original click-repl code as a basis for providing a REPL
with autocompletion for the application. Several modifications have been made
to adapt the code to the needs of Zabbix-CLI, as well as removing compatibility
with Python 2 and Click < 8.0.

Most prominently, the code has been refactored to take in a Typer app when
starting the REPL, which allows us to pass in more information about the available
commands and options to the REPL.

Furthermore, type annotations have been added to the entire vendored codebase,
and changes have been made in order to make the original code pass type checking.
Among these changes is removing code that adds compatibility with Click < 8.0, which
relied a lot on duck typing and was generally not type-safe.
"""
