__author__ = 'sshnaidm'


import sys
import xml.etree.ElementTree as et

with open(sys.argv[1]) as f:
    xml = f.read()
exml = et.fromstring(xml)

fails = [i.attrib["classname"] + "." + i.attrib["name"]
         for i in exml.getchildren()
         for z in i.getchildren()
         if i.getchildren()
         if "failure" in z.tag]
print "\n".join(fails)