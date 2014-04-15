#!/usr/bin/env python

import xml.etree.ElementTree as ET
import sys
from io import BytesIO

if __name__ == '__main__':
    tree = ET.parse(sys.argv[1])
    root = tree.getroot()
    for elem in tree.iter():
        children = elem.getchildren()
        attrib, text = elem.attrib, elem.text
        elem.clear()
        elem.attrib, elem.text = attrib, text
        elem.extend(sorted(children, key=lambda e: e.tag))

    out = BytesIO()
    tree.write(out)
    sys.stdout.write(out.getvalue().decode())
