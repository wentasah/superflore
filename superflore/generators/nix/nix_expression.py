# -*- coding: utf-8 -*-
#
# Copyright (c) 2016 David Bensoussan, Synapticon GmbH
# Copyright (c) 2019 Open Source Robotics Foundation, Inc.
#
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal  in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.
#
from operator import attrgetter
import os
from textwrap import dedent
from time import gmtime, strftime
from typing import Iterable, Set
import urllib.parse

from superflore.utils import get_license


def _escape_nix_string(string: str):
    return '"{}"'.format(string.replace("\\", "\\\\")
                               .replace("${", r"\${")
                               .replace('"', r"\""))


class NixLicense:
    """
    Converts a ROS license to the correct Nix license attribute.
    """

    _LICENSE_MAP = {
        '3-Clause-BSD': 'bsd3',
        'AGPL-3.0-only': 'agpl3Only',
        'AGPLv3': 'agpl3Only',
        'ASL 2.0': 'asl20',
        'Apache-2': 'asl20',
        'Apache-2.0': 'asl20',
        'Apache-2.0-License': 'apl20',
        'Apache-Licence-2.0': 'asl20',
        'Apache-license-2.0': 'asl20',
        'BSD': 'bsdOriginal',
        'BSD-2': 'bsd2',
        'BSD-2-Clause': 'bsd2',
        'BSD-2-clause': 'bsd2',
        'BSD-3-Clause': 'bsd3',
        'BSD-3-Clause-License': 'bsd3',
        'BSD-3-clause': 'bsd3',
        'BSD-Clause-3': 'bsd3', # Used in rqt_gauges
        'BSD-License-2.0': 'bsd3', # In teleop_twist_keyboard, BSD-License-2.0 is almost exactly bsd3. The only difference is use of "copyright owner" instead of "copyright holder".
        'BSL-1.0': 'boost',
        'Boost-1.0': 'boost',
        'CC-BY-NC-ND-4.0': 'cc-by-nc-nd-40',
        'CC-BY-NC-SA-3.0': 'cc-by-nc-sa-30',
        'CC-BY-NC-SA-4.0': 'cc-by-nc-sa-40',
        'CC-BY-SA-4.0': 'cc-by-sa-40',
        'CC0': 'cc0',
        'CC0-1.0': 'cc0',
        'EPL-2.0': 'epl20',
        'Eclipse-Distribution-License-1.0': 'bsd3', # see https://www.eclipse.org/org/documents/edl-v10/
        'GPL-1': 'gpl1',
        'GPL-2': 'gpl2',
        'GPL-2.0-only': 'gpl2Only',
        'GPL-2.0-or-later': 'gpl2Plus',
        'GPL-3': 'gpl3',
        'GPL-3.0': "gpl3",
        'GPL-3.0-only': 'gpl3Only',
        'GPLv2-license': 'gpl2Only',
        'HPND': 'hpnd',
        'LGPL-2': 'lgpl2',
        'LGPL-2.1': 'lgpl21',
        'LGPL-2.1-only': 'lgpl21Only',
        'LGPL-2.1-or-later': 'lgpl21Plus',
        'LGPL-3': 'lgpl3',
        'LGPL-3.0': 'lgpl3Only',
        'LGPL-3.0-only': 'lgpl3Only',
        'LGPL-v3': 'lgpl3Only',
        'MIT': 'mit',
        'MIT-0': 'mit0',
        'MPL-1.0': 'mpl10',
        'MPL-1.1': 'mpl11',
        'MPL-2.0': 'mpl20',
        'MPL-2.0-license': 'mpl20',
        'Mozilla-Public-License-2.0': 'mpl20',
        'PD': 'publicDomain',
        'Zlib': 'zlib',
        'Zlib-License': 'zlib',
        'apache-2.0': 'asl20',
    }

    def __init__(self, name):
        try:
            name = get_license(name)
            self.name = self._LICENSE_MAP[name]
            self.custom = False
        except KeyError:
            self.name = name
            self.custom = True

    @property
    def nix_code(self) -> str:
        if self.custom:
            return _escape_nix_string(self.name)
        else:
            return self.name


class NixExpression:
    def __init__(self, name: str, version: str,
                 src_url: str, src_sha256: str,
                 description: str, licenses: Iterable[NixLicense],
                 distro_name: str,
                 build_type: str,
                 build_inputs: Set[str] = set(),
                 propagated_build_inputs: Set[str] = set(),
                 check_inputs: Set[str] = set(),
                 native_build_inputs: Set[str] = set(),
                 propagated_native_build_inputs: Set[str] = set()
                 ) -> None:
        self.name = name
        self.version = version
        self.src_url = src_url
        self.src_sha256 = src_sha256
        # fetchurl's naming logic cannot account for URL parameters
        self.src_name = os.path.basename(
            urllib.parse.urlparse(self.src_url).path)

        self.description = description
        self.licenses = licenses
        self.distro_name = distro_name
        self.build_type = build_type

        self.build_inputs = build_inputs
        self.propagated_build_inputs = propagated_build_inputs
        self.check_inputs = check_inputs
        self.native_build_inputs = native_build_inputs
        self.propagated_native_build_inputs = \
            propagated_native_build_inputs

    @staticmethod
    def _to_nix_list(it: Iterable[str]) -> str:
        return '[ ' + ' '.join(it) + ' ]'

    @staticmethod
    def _to_nix_parameter(dep: str) -> str:
        return dep.split('.')[0]

    def get_text(self, distributor: str, license_name: str) -> str:
        """
        Generate the Nix expression, given the distributor line
        and the license text.
        """

        ret = []
        ret += dedent('''
        # Copyright {} {}
        # Distributed under the terms of the {} license

        ''').format(
            strftime("%Y", gmtime()), distributor,
            license_name)

        ret += '{ lib, buildRosPackage, fetchurl, ' + \
               ', '.join(sorted(set(map(self._to_nix_parameter,
                                        self.build_inputs |
                                        self.propagated_build_inputs |
                                        self.check_inputs |
                                        self.native_build_inputs |
                                        self.propagated_native_build_inputs)))
                         ) + ' }:'

        ret += dedent('''
        buildRosPackage {{
          pname = "ros-{distro_name}-{name}";
          version = "{version}";

          src = fetchurl {{
            url = "{src_url}";
            name = "{src_name}";
            sha256 = "{src_sha256}";
          }};

          buildType = "{build_type}";
        ''').format(
            distro_name=self.distro_name,
            name=self.name,
            version=self.version,
            src_url=self.src_url,
            src_name=self.src_name,
            src_sha256=self.src_sha256,
            build_type=self.build_type)

        if self.build_inputs:
            ret += "  buildInputs = {};\n" \
                .format(self._to_nix_list(sorted(self.build_inputs)))

        if self.check_inputs:
            ret += "  checkInputs = {};\n" \
                .format(self._to_nix_list(sorted(self.check_inputs)))

        if self.propagated_build_inputs:
            ret += "  propagatedBuildInputs = {};\n" \
                .format(self._to_nix_list(sorted(
                    self.propagated_build_inputs)))

        if self.native_build_inputs:
            ret += "  nativeBuildInputs = {};\n" \
                .format(self._to_nix_list(sorted(self.native_build_inputs)))

        if self.propagated_native_build_inputs:
            ret += "  propagatedNativeBuildInputs = {};\n".format(
                self._to_nix_list(sorted(self.propagated_native_build_inputs)))

        ret += dedent('''
          meta = {{
            description = {};
            license = with lib.licenses; {};
          }};
        }}
        ''').format(_escape_nix_string(self.description),
                    self._to_nix_list(map(attrgetter('nix_code'),
                                          self.licenses)))

        return ''.join(ret)
