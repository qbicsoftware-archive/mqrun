#!/usr/bin/env python

import xml.etree.ElementTree as ET
import sys
from io import BytesIO


def sort_xml(xml_root):
    for elem in xml_root.iter():
        children = elem.getchildren()
        attrib, text = elem.attrib, elem.text
        elem.clear()
        elem.attrib, elem.text = attrib, text
        elem.extend(sorted(children, key=lambda e: e.tag))


def xml_to_str(xml_root):
    out = BytesIO()
    tree = ET.ElementTree(xml_root)
    tree.write(out)
    return out.getvalue().decode()


if __name__ == '__main__':
    tree = ET.parse(sys.argv[1])
    root = tree.getroot()
    sort_xml(root)
    sys.stdout.write(xml_to_str(root))
